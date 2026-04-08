from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__)

@api_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})

@api_bp.route('/predict', methods=['POST'])
def predict():
    # Stub — will wire to ML model in Sprint 2
    data = request.get_json()
    return jsonify({
        'status': 'stub',
        'message': 'predictor not yet wired',
        'received': data
    }), 200

@api_bp.route('/financial-impact', methods=['POST'])
def financial_impact():
    # Stub — Sprint 3
    return jsonify({'status': 'stub'}), 200

@api_bp.route('/feedback', methods=['POST'])
def feedback():
    # Stub — Sprint 5
    return jsonify({'status': 'stub'}), 200