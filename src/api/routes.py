import time

from flask import Blueprint, jsonify, request
from src.services.surrogate_grouper import SurrogateGrouper
from src.services.financial_estimator import FinancialEstimator

api_bp = Blueprint('api', __name__)

_grouper            = SurrogateGrouper()
_financial_estimator = FinancialEstimator()


def _save_prediction_async(payload: dict) -> None:
    """
    Persist a prediction result to the database in a non-blocking manner.
    DB failure must never block the API response.
    """
    try:
        from src.models.crud import save_prediction
        save_prediction(payload)
    except Exception:
        pass


@api_bp.route('/health', methods=['GET'])
def health():
    try:
        _grouper._load()
        model_loaded = True
        model_name   = "SurrogateGrouper (MDC+Severity XGBoost + CBG Lookup)"
    except Exception:
        model_loaded = False
        model_name   = "unavailable"
    return jsonify({
        "status":       "ok",
        "model_loaded": model_loaded,
        "model_name":   model_name,
        "version":      "2.0.0",
        "architecture": "2-stage surrogate INACBG grouper",
    })


@api_bp.route('/predict', methods=['POST'])
def predict():
    """
    POST /api/v1/predict

    Predict CBG code and base tariff from clinical inputs.

    Request JSON (minimal clinical inputs only — no grouper result fields):
        primary_icd10   (str): e.g. "I10"
        icd9_procedure  (str): e.g. "89.09" (optional)
        inacbg_icd10    (str): e.g. "I10" (defaults to primary_icd10)
        care_type       (str): "outp" | "inp" | "emd" | "gp"
        entry_type      (str): "gp" | "outp" | "emd" | "inp" | ...
        kelas           (str): "kelas_1" | "kelas_2" | "kelas_3"
        episodes        (int): default 1

    Response: full surrogate grouper output dict
    """
    raw = request.get_json(silent=True)
    if not raw:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    try:
        result = _grouper.predict(raw)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify(result), 200


@api_bp.route('/financial-impact', methods=['POST'])
def financial_impact():
    """
    POST /api/v1/financial-impact

    Estimate BPJS reimbursement risk using surrogate grouper output.

    Request JSON:
        grouper_result  (dict): Output of /predict
        actual_tariff   (float): Amount hospital will charge
        kelas           (str):  "kelas_1" | "kelas_2" | "kelas_3"
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    grouper_result = body.get("grouper_result") or body.get("prediction_result", {})
    actual_tariff  = float(body.get("actual_tariff", 0) or 0)
    kelas          = str(body.get("kelas", "kelas_3"))

    try:
        result = _financial_estimator.estimate(grouper_result, actual_tariff, kelas)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    result["status"] = "success"
    return jsonify(result), 200


@api_bp.route('/recommend', methods=['POST'])
def recommend():
    """
    POST /api/v1/recommend

    Generate Casemix coding recommendations from grouper + financial results.

    Request JSON:
        grouper_result   (dict): from /predict
        financial_result (dict): from /financial-impact
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    try:
        from src.services.recommender import RecommendationEngine
        engine = RecommendationEngine()
        result = engine.synthesize(
            grouper_result=body.get("grouper_result", {}),
            financial_result=body.get("financial_result", {}),
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    result["status"] = "success"
    return jsonify(result), 200


@api_bp.route('/full-assessment', methods=['POST'])
def full_assessment():
    """
    POST /api/v1/full-assessment

    Unified endpoint: clinical input → CBG prediction + financial risk + recommendation.

    Request JSON (clinical inputs only):
        primary_icd10   (str)
        icd9_procedure  (str, optional)
        inacbg_icd10    (str, optional — defaults to primary_icd10)
        care_type       (str): "outp" | "inp" | "emd" | "gp"
        entry_type      (str)
        kelas           (str): "kelas_1" | "kelas_2" | "kelas_3"
        episodes        (int, default 1)
        actual_tariff   (float): what the hospital plans to charge
        source          (str, default "manual"): "manual" | "neurovi"
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    t_start = time.time()

    # 1 — Surrogate grouper: CBG prediction
    try:
        grouper_result = _grouper.predict(body)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Grouper failed: {e}"}), 500

    # 2 — Financial risk (base_tariff auto-predicted by grouper)
    actual_tariff = float(body.get("actual_tariff", 0) or 0)
    kelas         = str(body.get("kelas", "kelas_3"))
    try:
        financial_result = _financial_estimator.estimate(grouper_result, actual_tariff, kelas)
    except Exception as e:
        financial_result = {"error": str(e), "risk_level": "MEDIUM",
                            "reimbursement_amount": 0, "financial_gap": 0}

    # 3 — Recommendations
    try:
        from src.services.recommender import RecommendationEngine
        engine = RecommendationEngine()
        recommendation = engine.synthesize(
            grouper_result=grouper_result,
            financial_result=financial_result,
        )
    except Exception as e:
        recommendation = {"error": str(e)}

    elapsed_ms = round((time.time() - t_start) * 1000)

    response_payload = {
        "prediction":         grouper_result,
        "financial":          financial_result,
        "recommendation":     recommendation,
        "processing_time_ms": elapsed_ms,
        "status":             "success",
    }

    # Persist to DB (non-blocking)
    _save_prediction_async({
        "prediction":     grouper_result,
        "financial":      financial_result,
        "recommendation": recommendation,
        "request_body":   body,
        "source":         body.get("source", "manual"),
    })

    return jsonify(response_payload), 200


@api_bp.route('/stats', methods=['GET'])
def stats():
    """
    GET /api/v1/stats — aggregated stats for analytics dashboard.
    """
    try:
        from src.models.crud import get_stats_summary, get_prediction_history
        summary = get_stats_summary()
        summary["prediction_history"] = get_prediction_history(days=7)
        summary["status"] = "success"
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route('/feedback', methods=['POST'])
def feedback():
    return jsonify({'status': 'stub'}), 200
