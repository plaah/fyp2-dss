"""
Feedback CRUD and API endpoint tests (UC013/UC014).
Run: python -m pytest tests/test_feedback.py -v --tb=short
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def app():
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    with application.app_context():
        yield application


@pytest.fixture(scope="module")
def client(app):
    with app.test_client() as c:
        yield c


class TestPredictionFeedbackModel:

    def test_model_importable(self, app):
        from src.models.db_models import PredictionFeedback
        assert PredictionFeedback.__tablename__ == "prediction_feedback"

    def test_to_dict_has_required_keys(self, app):
        from src.models.db_models import PredictionFeedback
        from datetime import datetime
        fb = PredictionFeedback(
            prediction_id=None, submitted_cbg="I-1-1-II",
            correct_cbg="I-1-1-I", is_correct=False, notes="test"
        )
        fb.created_at = datetime.utcnow()
        d = fb.to_dict()
        for key in ("id", "prediction_id", "submitted_cbg", "correct_cbg", "is_correct", "notes", "created_at"):
            assert key in d

    def test_is_correct_defaults_falsy(self, app):
        from src.models.db_models import PredictionFeedback
        fb = PredictionFeedback(correct_cbg="I-1-1-I")
        # SQLAlchemy default applied on INSERT — value is None or False before save
        assert not fb.is_correct

    def test_prediction_id_nullable(self, app):
        from src.models.db_models import PredictionFeedback
        fb = PredictionFeedback(prediction_id=None, correct_cbg="I-1-1-I")
        assert fb.prediction_id is None


class TestFeedbackEndpoint:

    def test_post_feedback_success(self, client):
        resp = client.post('/api/v1/feedback',
                           json={"correct_cbg": "I-1-1-I", "is_correct": False,
                                 "submitted_cbg": "I-1-1-II", "notes": "severity salah"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "success"
        assert "feedback_id" in data

    def test_post_feedback_missing_correct_cbg(self, client):
        resp = client.post('/api/v1/feedback',
                           json={"submitted_cbg": "I-1-1-II", "is_correct": False})
        assert resp.status_code == 422
        data = resp.get_json()
        assert data["status"] == "error"

    def test_post_feedback_empty_body(self, client):
        resp = client.post('/api/v1/feedback',
                           data="not json", content_type='text/plain')
        assert resp.status_code == 400

    def test_post_feedback_no_prediction_id(self, client):
        resp = client.post('/api/v1/feedback',
                           json={"correct_cbg": "N-1-1-I", "is_correct": False})
        assert resp.status_code == 201
        assert resp.get_json()["status"] == "success"
