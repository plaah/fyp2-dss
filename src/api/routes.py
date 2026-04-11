from flask import Blueprint, jsonify, request
from src.services import predictor, explainer

api_bp = Blueprint('api', __name__)


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
    return jsonify({'status': 'stub'}), 200


@api_bp.route('/feedback', methods=['POST'])
def feedback():
    return jsonify({'status': 'stub'}), 200
