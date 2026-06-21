"""
Retraining and Artifact Integrity tests (UC014).
Run: python -m pytest tests/test_retraining.py -v --tb=short
"""
import pytest
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(scope="module")
def app():
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["RETRAIN_THRESHOLD"] = 2 # Low threshold for test trigger
    application.config["RETRAIN_TRIALS"] = 1     # Fast trigger for test speed
    with application.app_context():
        yield application

@pytest.fixture(scope="module")
def client(app):
    with app.test_client() as c:
        yield c

class TestRetrainingPipeline:

    def test_retraining_execution(self, app):
        """Test the core execute_retraining function directly."""
        from src.services.retrainer import execute_retraining
        
        # Check files modified times before training
        from src.services.retrainer import MODELS_DIR
        mdc_path = os.path.join(MODELS_DIR, "mdc_predictor.pkl")
        sev_path = os.path.join(MODELS_DIR, "severity_predictor.pkl")
        cbg_path = os.path.join(MODELS_DIR, "cbg_lookup_table.pkl")
        
        mtime_before_mdc = os.path.getmtime(mdc_path)
        mtime_before_sev = os.path.getmtime(sev_path)
        mtime_before_cbg = os.path.getmtime(cbg_path)
        
        # Execute retraining with 1 trial (very fast)
        result = execute_retraining(n_trials=1)
        
        assert result["status"] == "success"
        assert "metrics" in result
        assert "mdc_accuracy" in result["metrics"]
        assert "severity_accuracy" in result["metrics"]
        
        # Verify file modifications (integrity check)
        assert os.path.getmtime(mdc_path) >= mtime_before_mdc
        assert os.path.getmtime(sev_path) >= mtime_before_sev
        assert os.path.getmtime(cbg_path) >= mtime_before_cbg

    def test_retrain_endpoint_forbidden_for_non_admin(self, client):
        """Test that POST /retrain returns 403 Forbidden without admin credentials."""
        resp = client.post('/api/v1/retrain')
        assert resp.status_code == 403
        assert resp.get_json()["status"] == "error"

    def test_retrain_endpoint_async(self, client):
        """Test POST /retrain manually triggers asynchronous retraining."""
        resp = client.post('/api/v1/retrain?admin=true&n_trials=1')
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["status"] == "success"
        assert "initiated in the background" in data["message"]

    def test_retrain_endpoint_sync(self, client):
        """Test POST /retrain manually triggers synchronous retraining."""
        # Add X-Admin: true header
        resp = client.post('/api/v1/retrain?sync=true&n_trials=1', headers={"X-Admin": "true"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "metrics" in data
        assert "mdc_accuracy" in data["metrics"]

    def test_automatic_trigger_on_feedback_threshold(self, app, client):
        """Test that submitting feedback past the threshold triggers background retraining."""
        from src.models.db_models import db, Prediction, PredictionFeedback
        
        # Setup: Create 2 predictions in DB to associate feedback with
        with app.app_context():
            # Clear existing incorrect feedbacks to ensure clean threshold check
            db.session.query(PredictionFeedback).filter_by(is_correct=False).delete()
            db.session.commit()
            
            p1 = Prediction(
                idrg_primary_icd10="I10",
                kelas="kelas_3",
                care_type="outp",
                ml_prediction="grouping_valid"
            )
            p2 = Prediction(
                idrg_primary_icd10="J18.9",
                kelas="kelas_3",
                care_type="outp",
                ml_prediction="grouping_valid"
            )
            db.session.add(p1)
            db.session.add(p2)
            db.session.commit()
            
            p1_id = p1.id
            p2_id = p2.id
            
        # Post first feedback (threshold = 2, so count = 1, should not trigger)
        resp1 = client.post('/api/v1/feedback', json={
            "prediction_id": p1_id,
            "submitted_cbg": "I-1-10-I",
            "correct_cbg": "I-1-10-II",
            "is_correct": False,
            "notes": "wrong severity"
        })
        assert resp1.status_code == 201
        
        # Post second feedback (count = 2, reaches threshold, triggers retrain)
        # We check that it completes successfully by running execute_retraining in the background thread.
        # To monitor, we check the modified time of severity_predictor.pkl.
        from src.services.retrainer import MODELS_DIR
        mdc_path = os.path.join(MODELS_DIR, "mdc_predictor.pkl")
        mtime_before = os.path.getmtime(mdc_path)
        
        resp2 = client.post('/api/v1/feedback', json={
            "prediction_id": p2_id,
            "submitted_cbg": "J-1-10-I",
            "correct_cbg": "J-1-10-II",
            "is_correct": False,
            "notes": "wrong severity again"
        })
        assert resp2.status_code == 201
        
        # Wait up to 10 seconds for background thread to run training and save models
        retrained = False
        for _ in range(20):
            time.sleep(0.5)
            if os.path.getmtime(mdc_path) > mtime_before:
                retrained = True
                break
                
        assert retrained, "Background retraining did not update model artifact after threshold."
        
        # Cleanup
        with app.app_context():
            db.session.query(PredictionFeedback).delete()
            db.session.query(Prediction).filter(Prediction.id.in_([p1_id, p2_id])).delete()
            db.session.commit()
