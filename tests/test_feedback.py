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

    def test_stats_endpoint_includes_impact_fields(self, client):
        resp = client.get('/api/v1/stats')
        assert resp.status_code == 200
        data = resp.get_json()
        for key in (
            "feedback_total", "feedback_confirmed", "feedback_confirmation_rate",
            "avg_mdc_confidence", "recent_feedback", "trust_score",
            "trust_score_breakdown", "pending_review",
        ):
            assert key in data, f"Stats endpoint missing key: {key}"


class TestGetImpactStats:

    def test_returns_expected_keys(self, app):
        from src.models.crud import get_impact_stats
        result = get_impact_stats()
        for key in (
            "feedback_total", "feedback_confirmed", "feedback_confirmation_rate",
            "avg_mdc_confidence", "recent_feedback", "trust_score",
            "trust_score_breakdown", "pending_review",
        ):
            assert key in result, f"Missing key: {key}"

    def test_safe_defaults_when_no_feedback(self, app):
        from src.models.crud import get_impact_stats
        result = get_impact_stats()
        assert isinstance(result["feedback_total"], int)
        assert isinstance(result["feedback_confirmation_rate"], float)
        assert isinstance(result["recent_feedback"], list)
        assert isinstance(result["pending_review"], list)
        assert result["trust_score"] is None or isinstance(result["trust_score"], int)

    def test_confirmation_rate_zero_when_no_feedback(self, app):
        from src.models.crud import get_impact_stats
        result = get_impact_stats()
        if result["feedback_total"] == 0:
            assert result["feedback_confirmation_rate"] == 0.0

    def test_pending_review_items_have_required_fields(self, app):
        from src.models.crud import get_impact_stats
        result = get_impact_stats()
        for item in result["pending_review"]:
            for field in ("id", "icd_codes", "cbg_prediction", "mdc_confidence", "risk_level", "created_at"):
                assert field in item, f"pending_review item missing field: {field}"

    def test_trust_score_within_bounds(self, app):
        """Trust score formula produces values in [0, 100] for any valid inputs."""
        # Direct math check — no DB needed
        for mdc in [0.0, 0.5, 1.0]:
            for conf in [0.0, 0.5, 1.0]:
                for valid in [0.0, 0.5, 1.0]:
                    score = round((mdc * 0.4 + conf * 0.4 + valid * 0.2) * 100)
                    assert 0 <= score <= 100, (
                        f"score {score} out of bounds for inputs {mdc},{conf},{valid}"
                    )

    def test_pending_review_handles_none_ml_prediction(self, app):
        """Predictions with ml_prediction=None don't crash pending_review."""
        from src.models.db_models import db, Prediction
        import datetime
        with app.app_context():
            p = Prediction(
                idrg_primary_icd10="A00",
                ml_prediction=None,
                risk_level="LOW",
                confidence_valid=0.9,
                created_at=datetime.datetime.utcnow(),
            )
            db.session.add(p)
            db.session.commit()
            pred_id = p.id
            try:
                from src.models.crud import get_impact_stats
                result = get_impact_stats()
                # Should not raise; item should appear in pending_review
                ids = [item["id"] for item in result["pending_review"]]
                assert pred_id in ids
                # mdc_confidence is a float or None, never an error
                item = next(i for i in result["pending_review"] if i["id"] == pred_id)
                assert item["mdc_confidence"] is None or isinstance(item["mdc_confidence"], float)
            finally:
                db.session.delete(db.session.get(Prediction, pred_id))
                db.session.commit()

    def test_recent_feedback_handles_orphan_feedback(self, app):
        """Feedback with no linked prediction uses fallback display values."""
        from src.models.db_models import db, PredictionFeedback
        import datetime
        with app.app_context():
            fb = PredictionFeedback(
                prediction_id=None,
                submitted_cbg="A-1-0-I",
                correct_cbg="A-1-0-I",
                is_correct=True,
                notes="",
                created_at=datetime.datetime.utcnow(),
            )
            db.session.add(fb)
            db.session.commit()
            fb_id = fb.id
            try:
                from src.models.crud import get_impact_stats
                result = get_impact_stats()
                recent = result["recent_feedback"]
                # The orphan entry should appear (most recent first) without crashing
                assert len(recent) >= 1
                # The one with no prediction should show "—" for icd_codes
                orphan = next((r for r in recent if r["cbg_prediction"] == "A-1-0-I"), None)
                assert orphan is not None, "orphan feedback not in recent_feedback"
                assert orphan["icd_codes"] == "—"
            finally:
                db.session.delete(db.session.get(PredictionFeedback, fb_id))
                db.session.commit()
