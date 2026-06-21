import time
import threading

from flask import Blueprint, jsonify, request, current_app
from src.services.surrogate_grouper import SurrogateGrouper
from src.services.financial_estimator import FinancialEstimator
from src.services.recommender import RecommendationEngine
from src.services.icd_search import icd_search_service

api_bp = Blueprint('api', __name__)

_grouper             = SurrogateGrouper()
_financial_estimator = FinancialEstimator()
_recommender         = RecommendationEngine()


def _trigger_retraining_async(n_trials: int = 10) -> None:
    """Run execute_retraining in a background thread."""
    from flask import current_app
    app = current_app._get_current_object()
    def _run():
        try:
            from src.services.retrainer import execute_retraining
            with app.app_context():
                execute_retraining(n_trials=n_trials)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("execute_retraining background task failed: %s", e, exc_info=True)
            
    threading.Thread(target=_run, daemon=True).start()



def _save_prediction_async(payload: dict) -> None:
    """
    Persist a prediction result in a true background thread so the API
    response is returned immediately after ML inference completes.
    """
    from flask import current_app
    app = current_app._get_current_object()

    def _run():
        try:
            from src.models.crud import save_prediction
            with app.app_context():
                save_prediction(payload)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("save_prediction failed: %s", e, exc_info=True)

    threading.Thread(target=_run, daemon=True).start()


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

    # ── Normalize multi-ICD payload (backward-compatible) ─────────────────
    # Accept both old single-value and new array formats
    if 'icd9_procedures' not in body and 'icd9_procedure' in body:
        single = body.get('icd9_procedure', '')
        body['icd9_procedures'] = [single] if single else []
    if 'secondary_icd10' not in body:
        body['secondary_icd10'] = []

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
        recommendation = _recommender.synthesize(
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
        from src.models.crud import get_stats_summary, get_prediction_history, get_impact_stats
        summary = get_stats_summary()
        summary["prediction_history"] = get_prediction_history(days=7)
        summary.update(get_impact_stats(
            total_preds=summary.get("total_predictions"),
            valid_cnt=summary.get("grouping_valid_count"),
        ))
        summary["status"] = "success"
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route('/feedback', methods=['POST'])
def feedback():
    try:
        body = request.get_json(force=True, silent=True)
        if not body:
            return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400
        if 'correct_cbg' not in body:
            return jsonify({'status': 'error', 'message': 'correct_cbg is required'}), 422
        from src.models.crud import save_feedback
        row = save_feedback(body)
        
        # UC014 Retraining Trigger on incorrect feedback count threshold
        is_correct = body.get('is_correct', False)
        if not is_correct:
            from src.models.db_models import PredictionFeedback
            incorrect_count = PredictionFeedback.query.filter_by(is_correct=False).count()
            threshold = current_app.config.get('RETRAIN_THRESHOLD', 50)
            if incorrect_count > 0 and incorrect_count % threshold == 0:
                n_trials = current_app.config.get('RETRAIN_TRIALS', 10)
                _trigger_retraining_async(n_trials=n_trials)
                
        return jsonify({'status': 'success', 'feedback_id': row.id}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@api_bp.route('/retrain', methods=['POST'])
def retrain():
    """
    POST /api/v1/retrain
    Trigger model retraining manually.
    Admin-only: Requires X-Admin header set to 'true' or admin=true query param.
    """
    if request.headers.get('X-Admin') != 'true' and request.args.get('admin') != 'true':
        return jsonify({'status': 'error', 'message': 'Admin access required'}), 403
        
    sync = request.args.get('sync') == 'true'
    n_trials_str = request.args.get('n_trials', '10')
    try:
        n_trials = int(n_trials_str)
    except ValueError:
        n_trials = 10
        
    if sync:
        try:
            from src.services.retrainer import execute_retraining
            result = execute_retraining(n_trials=n_trials)
            if result.get("status") == "success":
                return jsonify(result), 200
            else:
                return jsonify(result), 500
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    else:
        _trigger_retraining_async(n_trials=n_trials)
        return jsonify({
            'status': 'success',
            'message': 'Retraining initiated in the background'
        }), 202



@api_bp.route('/icd-search', methods=['GET'])
def icd_search():
    """
    Search ICD codes by Indonesian medical term or code prefix.

    Query params:
      q     (str, required): search term, min 2 chars
      type  (str, optional): 'diagnosis' (default) or 'procedure'
      limit (int, optional): max results, default 5, max 10

    Returns:
      {"results": [...], "query": str, "type": str, "count": int}
    """
    q           = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'diagnosis')
    try:
        limit = min(int(request.args.get('limit', 5)), 10)
    except (ValueError, TypeError):
        limit = 5

    if len(q) < 2:
        return jsonify({'results': [], 'query': q,
                        'type': search_type, 'count': 0})

    if search_type not in ('diagnosis', 'procedure'):
        return jsonify({'error': "type must be 'diagnosis' or 'procedure'"}), 400

    results = icd_search_service.search(q, search_type, limit)
    return jsonify({
        'results': results,
        'query':   q,
        'type':    search_type,
        'count':   len(results),
    })
