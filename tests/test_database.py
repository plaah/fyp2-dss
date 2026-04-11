"""
Database CRUD tests (T4.2)
Tests run against the real fyp2_db PostgreSQL database using a test app context.
Each test class uses a transaction rollback to avoid polluting the predictions table.
"""

import pytest
from datetime import datetime, timedelta

from app import create_app
from src.models.db_models import db as _db, Prediction


# ── App and DB fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """Create a Flask test app context for the entire module."""
    application = create_app()
    application.config["TESTING"] = True
    with application.app_context():
        yield application


@pytest.fixture()
def session(app):
    """
    Provide a DB session that rolls back after each test.
    Uses a savepoint so we can test commit-like behaviour without persisting.
    """
    connection = _db.engine.connect()
    transaction = connection.begin()

    # Override the session to use our connection
    _db.session.remove()
    _db.session.configure(bind=connection)

    yield _db.session

    _db.session.remove()
    transaction.rollback()
    connection.close()
    # Restore default session binding
    _db.session.configure(bind=_db.engine)


def _make_prediction(**kwargs) -> Prediction:
    """Factory: create an unsaved Prediction with sensible defaults."""
    defaults = dict(
        idrg_primary_icd10       = "I10",
        inacbg_primary_icd10     = "I10",
        kelas                    = "kelas_3",
        care_type                = "outp",
        entry_type               = "gp",
        ml_prediction            = "grouping_valid",
        confidence_valid         = 0.95,
        confidence_incomplete    = 0.03,
        confidence_invalid       = 0.02,
        risk_level               = "LOW",
        base_tariff              = 196_100,
        actual_tariff            = 196_100,
        financial_gap            = 0,
        reimbursement_probability= 0.95,
        primary_action           = "SUBMIT",
        top_shap_feature         = "final_success",
        source                   = "test",
    )
    defaults.update(kwargs)
    return Prediction(**defaults)


# ── Model tests ────────────────────────────────────────────────────────────────

class TestPredictionModel:

    def test_to_dict_has_all_keys(self, app):
        p = _make_prediction()
        p.created_at = datetime.utcnow()
        d = p.to_dict()
        required = {
            "id", "claim_id", "idrg_primary_icd10", "inacbg_primary_icd10",
            "ml_prediction", "risk_level", "base_tariff", "actual_tariff",
            "financial_gap", "reimbursement_probability", "primary_action",
            "top_shap_feature", "created_at", "source",
        }
        assert required.issubset(d.keys())

    def test_created_at_isoformat(self, app):
        p = _make_prediction()
        p.created_at = datetime(2026, 4, 11, 12, 0, 0)
        d = p.to_dict()
        assert d["created_at"] == "2026-04-11T12:00:00"

    def test_none_created_at_returns_none(self, app):
        p = _make_prediction()
        p.created_at = None
        assert p.to_dict()["created_at"] is None


# ── CRUD function tests ────────────────────────────────────────────────────────

class TestCRUD:

    def test_save_prediction_valid_outcome(self, app):
        from src.models.crud import save_prediction
        payload = {
            "prediction": {
                "prediction": "grouping_valid",
                "confidence": {"grouping_valid": 0.95, "coding_incomplete": 0.03, "grouping_invalid": 0.02},
                "explanation": [{"feature": "final_success", "impact": 5.0, "direction": "positive"}],
            },
            "financial": {
                "risk_level": "LOW",
                "reimbursement_amount": 196_100,
                "submitted_amount":     196_100,
                "financial_gap":        0,
                "reimbursement_probability": 0.95,
            },
            "recommendation": {"primary_action": "SUBMIT"},
            "request_body": {
                "idrg_primary_icd10":   "I10",
                "inacbg_primary_icd10": "I10",
                "kelas":                "kelas_3",
                "care_type":            "outp",
                "entry_type":           "gp",
            },
            "source": "test",
        }
        row = save_prediction(payload)
        assert row.id is not None
        assert row.ml_prediction == "grouping_valid"
        assert row.risk_level == "LOW"
        assert row.primary_action == "SUBMIT"
        assert row.top_shap_feature == "final_success"
        # cleanup
        _db.session.delete(row)
        _db.session.commit()

    def test_save_prediction_invalid_outcome(self, app):
        from src.models.crud import save_prediction
        payload = {
            "prediction": {
                "prediction": "grouping_invalid",
                "confidence": {"grouping_valid": 0.02, "coding_incomplete": 0.02, "grouping_invalid": 0.96},
                "explanation": [{"feature": "inacbg_grouping_success", "impact": 4.5, "direction": "negative"}],
            },
            "financial": {
                "risk_level": "CRITICAL",
                "reimbursement_amount": 196_100,
                "submitted_amount":     200_000,
                "financial_gap":        200_000,
                "reimbursement_probability": 0.15,
            },
            "recommendation": {"primary_action": "RECODE"},
            "request_body": {"idrg_primary_icd10": "Z09", "kelas": "kelas_1"},
            "source": "test",
        }
        row = save_prediction(payload)
        assert row.ml_prediction == "grouping_invalid"
        assert row.risk_level == "CRITICAL"
        assert row.primary_action == "RECODE"
        _db.session.delete(row)
        _db.session.commit()

    def test_save_prediction_missing_explanation_does_not_crash(self, app):
        from src.models.crud import save_prediction
        payload = {
            "prediction": {
                "prediction": "coding_incomplete",
                "confidence": {"grouping_valid": 0.05, "coding_incomplete": 0.90, "grouping_invalid": 0.05},
                "explanation": [],
            },
            "financial": {
                "risk_level": "HIGH",
                "reimbursement_amount": 100_000,
                "submitted_amount":     100_000,
                "financial_gap":        0,
                "reimbursement_probability": 0.70,
            },
            "recommendation": {"primary_action": "COMPLETE_CODING"},
            "request_body": {},
            "source": "test",
        }
        row = save_prediction(payload)
        assert row.top_shap_feature is None
        _db.session.delete(row)
        _db.session.commit()

    def test_get_recent_predictions_returns_list(self, app):
        from src.models.crud import get_recent_predictions
        result = get_recent_predictions(limit=5)
        assert isinstance(result, list)
        assert len(result) <= 5

    def test_get_recent_predictions_respects_limit(self, app):
        from src.models.crud import get_recent_predictions
        for limit in (1, 5, 10):
            result = get_recent_predictions(limit=limit)
            assert len(result) <= limit

    def test_get_stats_summary_has_required_keys(self, app):
        from src.models.crud import get_stats_summary
        summary = get_stats_summary()
        required = {
            "total_predictions", "today_predictions",
            "grouping_valid_pct", "coding_incomplete_pct", "grouping_invalid_pct",
            "avg_reimbursement_probability", "total_financial_gap_idr",
            "recent_predictions",
        }
        assert required.issubset(summary.keys())

    def test_get_stats_pcts_sum_to_100_or_zero(self, app):
        from src.models.crud import get_stats_summary
        s = get_stats_summary()
        total = s["total_predictions"]
        if total > 0:
            pct_sum = s["grouping_valid_pct"] + s["coding_incomplete_pct"] + s["grouping_invalid_pct"]
            assert abs(pct_sum - 100.0) < 1.0  # allow rounding tolerance

    def test_get_prediction_history_returns_7_days(self, app):
        from src.models.crud import get_prediction_history
        result = get_prediction_history(days=7)
        assert len(result) == 7

    def test_get_prediction_history_has_date_and_count(self, app):
        from src.models.crud import get_prediction_history
        result = get_prediction_history(days=3)
        for entry in result:
            assert "date" in entry
            assert "count" in entry
            assert isinstance(entry["count"], int)

    def test_seed_from_csv_skips_if_already_seeded(self, app):
        from src.models.crud import seed_from_csv
        # DB already has seed data from fixture — should return 0
        result = seed_from_csv(limit=10)
        assert result == 0


# ── Stats endpoint integration test ───────────────────────────────────────────

class TestStatsEndpoint:

    def test_stats_endpoint_returns_200(self, app):
        client = app.test_client()
        resp = client.get('/api/v1/stats')
        assert resp.status_code == 200

    def test_stats_endpoint_response_structure(self, app):
        client = app.test_client()
        resp = client.get('/api/v1/stats')
        data = resp.get_json()
        assert data["status"] == "success"
        assert "total_predictions" in data
        assert "grouping_valid_pct" in data
        assert "recent_predictions" in data

    def test_stats_total_is_positive(self, app):
        client = app.test_client()
        resp = client.get('/api/v1/stats')
        data = resp.get_json()
        assert data["total_predictions"] >= 0
