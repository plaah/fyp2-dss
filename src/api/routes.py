import time

from flask import Blueprint, jsonify, request
from src.services import predictor, explainer
from src.services.financial_estimator import FinancialEstimator

api_bp = Blueprint('api', __name__)

_financial_estimator = FinancialEstimator()


def _save_prediction_async(payload: dict) -> None:
    """
    Persist a prediction result to the database in a non-blocking manner.
    If the DB write fails for any reason the API response is not affected.

    Args:
        payload: Combined dict with 'prediction', 'financial', 'recommendation',
                 and 'request_body' keys.
    """
    try:
        from src.models.crud import save_prediction
        save_prediction(payload)
    except Exception:
        pass  # DB failure must never block the API response


@api_bp.route('/health', methods=['GET'])
def health():
    try:
        model_name = predictor.get_model_name()
        loaded     = predictor.is_loaded()
    except Exception:
        model_name = "unknown"
        loaded     = False
    return jsonify({
        "status":       "ok",
        "model_loaded": loaded,
        "model_name":   model_name,
        "version":      "1.0.0",
        "dataset_size": 9887,
    })


@api_bp.route('/predict', methods=['POST'])
def predict():
    raw = request.get_json(silent=True)
    if not raw:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    try:
        result = predictor.predict(raw)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    # SHAP explanation
    try:
        label_enc   = predictor.get_label_encoder()
        classes     = list(label_enc.classes_)
        pred_idx    = classes.index(result["prediction"])
        explanation = explainer.explain(result["features"], predicted_class_idx=pred_idx)
    except Exception as e:
        explanation = [{"feature": "unavailable", "impact": 0.0,
                        "direction": "positive", "error": str(e)}]

    return jsonify({
        "prediction":  result["prediction"],
        "confidence":  result["confidence"],
        "explanation": explanation,
        "model_used":  result["model_used"],
        "status":      "success",
    })


@api_bp.route('/financial-impact', methods=['POST'])
def financial_impact():
    """
    POST /api/v1/financial-impact

    Estimate BPJS reimbursement risk for a claim given its prediction outcome
    and tariff data.

    Request JSON:
        prediction_result (dict): Output of /predict (must contain "prediction" key)
        base_tariff       (float): Official INA-CBGs base rate (IDR)
        actual_tariff     (float): Amount hospital submitted
        kelas             (str):   "kelas_1" | "kelas_2" | "kelas_3"
        inacbg_cbg_code   (str):   INA-CBGs CBG code  (e.g. "Q-5-44-0")
        inacbg_cbg_desc   (str):   CBG description

    Response JSON: full financial assessment dict + cbg_code + cbg_description + status
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    prediction_result = body.get("prediction_result", {})
    if not prediction_result.get("prediction"):
        return jsonify({"status": "error", "message": "prediction_result.prediction is required"}), 400

    claim_data = {
        "base_tariff":   body.get("base_tariff", 0),
        "actual_tariff": body.get("actual_tariff", 0),
        "kelas":         body.get("kelas", "kelas_3"),
    }

    try:
        result = _financial_estimator.estimate(prediction_result, claim_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    result["cbg_code"]        = body.get("inacbg_cbg_code", "")
    result["cbg_description"] = body.get("inacbg_cbg_desc", "")
    result["status"]          = "success"
    return jsonify(result), 200


@api_bp.route('/recommend', methods=['POST'])
def recommend():
    """
    POST /api/v1/recommend

    Generate actionable Casemix coding recommendations by synthesising
    the ML prediction, financial risk assessment, and SHAP explanation.

    Request JSON:
        prediction_result (dict): from /predict
        financial_result  (dict): from /financial-impact
        explanation       (list): SHAP feature list from /predict
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    try:
        from src.services.recommender import RecommendationEngine
        engine = RecommendationEngine()
        result = engine.synthesize(
            prediction_result=body.get("prediction_result", {}),
            financial_result=body.get("financial_result", {}),
            explanation=body.get("explanation", []),
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    result["status"] = "success"
    return jsonify(result), 200


@api_bp.route('/full-assessment', methods=['POST'])
def full_assessment():
    """
    POST /api/v1/full-assessment

    Single unified endpoint that executes the full DSS pipeline:
        1. ML prediction  (/predict logic)
        2. Financial risk  (/financial-impact logic)
        3. Recommendation  (/recommend logic)
    Returns all three results combined.  This is the primary endpoint for
    the frontend dashboard.

    Request JSON: same schema as /predict, plus optional tariff fields:
        base_tariff    (float, default 0)
        actual_tariff  (float, default 0)
        kelas          (str,   default "kelas_3")
        inacbg_cbg_code (str)
        inacbg_cbg_desc (str)
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    t_start = time.time()

    # 1 — Predict
    try:
        pred_result = predictor.predict(body)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Prediction failed: {e}"}), 500

    # 2 — SHAP explanation
    try:
        label_enc   = predictor.get_label_encoder()
        classes     = list(label_enc.classes_)
        pred_idx    = classes.index(pred_result["prediction"])
        explanation = explainer.explain(pred_result["features"], predicted_class_idx=pred_idx)
    except Exception as e:
        explanation = [{"feature": "unavailable", "impact": 0.0,
                        "direction": "positive", "error": str(e)}]

    prediction_payload = {
        "prediction": pred_result["prediction"],
        "confidence": pred_result["confidence"],
        "model_used": pred_result["model_used"],
        "explanation": explanation,
    }

    # 3 — Financial impact
    claim_data = {
        "base_tariff":   body.get("base_tariff", 0),
        "actual_tariff": body.get("actual_tariff", 0),
        "kelas":         body.get("kelas", "kelas_3"),
    }
    try:
        financial_result = _financial_estimator.estimate(prediction_payload, claim_data)
        financial_result["cbg_code"]        = body.get("inacbg_cbg_code", "")
        financial_result["cbg_description"] = body.get("inacbg_cbg_desc", "")
    except Exception as e:
        financial_result = {"error": str(e)}

    # 4 — Recommendations
    try:
        from src.services.recommender import RecommendationEngine
        engine = RecommendationEngine()
        recommendation = engine.synthesize(
            prediction_result=prediction_payload,
            financial_result=financial_result,
            explanation=explanation,
        )
    except Exception as e:
        recommendation = {"error": str(e)}

    elapsed_ms = round((time.time() - t_start) * 1000)

    response_payload = {
        "prediction":         prediction_payload,
        "financial":          financial_result,
        "recommendation":     recommendation,
        "processing_time_ms": elapsed_ms,
        "status":             "success",
    }

    # Persist to DB non-blocking — failure must not affect response
    _save_prediction_async({
        "prediction":    prediction_payload,
        "financial":     financial_result,
        "recommendation": recommendation,
        "request_body":  body,
        "source":        body.get("source", "manual"),
    })

    return jsonify(response_payload), 200


@api_bp.route('/stats', methods=['GET'])
def stats():
    """
    GET /api/v1/stats

    Return aggregated statistics from the predictions table for the
    analytics dashboard.  Includes label distribution, financial risk summary,
    and the last 5 predictions for the recent-predictions widget.
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
