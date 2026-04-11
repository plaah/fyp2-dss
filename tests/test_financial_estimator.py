"""
Unit tests for FinancialEstimator (T3.1)
Tests cover all 4 risk levels, all kelas multipliers, and edge cases.
"""

import pytest
from src.services.financial_estimator import (
    FinancialEstimator,
    KELAS_MULTIPLIERS,
    CASH_FLOW_DELAY_DAYS,
    REIMBURSEMENT_PROB_SPECIAL,
)

estimator = FinancialEstimator()

# ── helpers ────────────────────────────────────────────────────────────────────

def _pred(outcome: str, confidence: float = 0.90) -> dict:
    return {
        "prediction": outcome,
        "confidence": {outcome: confidence},
    }


def _claim(base: float, actual: float, kelas: str = "kelas_3") -> dict:
    return {"base_tariff": base, "actual_tariff": actual, "kelas": kelas}


# ── Risk level tests ───────────────────────────────────────────────────────────

class TestRiskLevels:

    def test_risk_critical_for_grouping_invalid(self):
        result = estimator.estimate(_pred("grouping_invalid"), _claim(200_000, 200_000))
        assert result["risk_level"] == "CRITICAL"

    def test_risk_high_for_coding_incomplete(self):
        result = estimator.estimate(_pred("coding_incomplete"), _claim(200_000, 200_000))
        assert result["risk_level"] == "HIGH"

    def test_risk_low_when_submitted_within_5pct(self):
        # actual = base * 1.03 → ratio ≤ 1.05 → LOW
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 103_000))
        assert result["risk_level"] == "LOW"

    def test_risk_medium_when_submitted_between_5_and_20pct(self):
        # actual = base * 1.10 → ratio 1.10 → MEDIUM
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 110_000))
        assert result["risk_level"] == "MEDIUM"

    def test_risk_high_when_submitted_over_20pct(self):
        # actual = base * 1.25 → ratio 1.25 → HIGH
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 125_000))
        assert result["risk_level"] == "HIGH"


# ── Kelas multiplier tests ─────────────────────────────────────────────────────

class TestKelasMultipliers:

    def test_kelas_3_ceiling_equals_base(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(200_000, 200_000, "kelas_3"))
        assert result["reimbursement_amount"] == pytest.approx(200_000.0)

    def test_kelas_2_ceiling_is_1_25x_base(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(200_000, 250_000, "kelas_2"))
        assert result["reimbursement_amount"] == pytest.approx(250_000.0)

    def test_kelas_1_ceiling_is_1_50x_base(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(200_000, 300_000, "kelas_1"))
        assert result["reimbursement_amount"] == pytest.approx(300_000.0)

    def test_unknown_kelas_defaults_to_kelas_3(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 100_000, "kelas_X"))
        assert result["reimbursement_amount"] == pytest.approx(100_000.0)

    def test_kelas_2_low_risk_when_submitted_at_ceiling(self):
        # kelas_2 ceiling = 200k × 1.25 = 250k; submitting exactly 250k → ratio 1.0 → LOW
        result = estimator.estimate(_pred("grouping_valid"), _claim(200_000, 250_000, "kelas_2"))
        assert result["risk_level"] == "LOW"


# ── Financial calculation tests ────────────────────────────────────────────────

class TestFinancialCalculations:

    def test_financial_gap_positive_when_over_ceiling(self):
        # submitted 210k > ceiling 196.1k → positive gap
        result = estimator.estimate(_pred("grouping_valid"), _claim(196_100, 210_000))
        assert result["financial_gap"] > 0

    def test_financial_gap_negative_when_under_ceiling(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(200_000, 180_000))
        assert result["financial_gap"] < 0

    def test_estimated_loss_is_zero_when_under_ceiling(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(200_000, 180_000))
        assert result["estimated_loss_idr"] == 0.0

    def test_estimated_loss_equals_full_tariff_when_invalid(self):
        # grouping_invalid → hospital loses the entire submitted amount
        result = estimator.estimate(_pred("grouping_invalid"), _claim(200_000, 200_000))
        assert result["estimated_loss_idr"] == pytest.approx(200_000.0)

    def test_gap_percentage_calculation(self):
        # 210k submitted, 196.1k ceiling → gap = 13.9k, pct = 13900/196100 * 100
        result = estimator.estimate(_pred("grouping_valid"), _claim(196_100, 210_000))
        expected_pct = round((210_000 - 196_100) / 196_100 * 100, 2)
        assert result["gap_percentage"] == pytest.approx(expected_pct, rel=1e-2)


# ── Cash flow delay tests ──────────────────────────────────────────────────────

class TestCashFlowDelay:

    def test_no_delay_for_valid(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 100_000))
        assert result["cash_flow_risk_days"] == 0

    def test_30_day_delay_for_incomplete(self):
        result = estimator.estimate(_pred("coding_incomplete"), _claim(100_000, 100_000))
        assert result["cash_flow_risk_days"] == CASH_FLOW_DELAY_DAYS["coding_incomplete"]

    def test_90_day_delay_for_invalid(self):
        result = estimator.estimate(_pred("grouping_invalid"), _claim(100_000, 100_000))
        assert result["cash_flow_risk_days"] == CASH_FLOW_DELAY_DAYS["grouping_invalid"]


# ── Reimbursement probability tests ───────────────────────────────────────────

class TestReimbursementProbability:

    def test_high_probability_for_low_risk_valid(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 100_000))
        assert result["reimbursement_probability"] == pytest.approx(0.95)

    def test_medium_probability_for_medium_risk(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 110_000))
        assert result["reimbursement_probability"] == pytest.approx(0.80)

    def test_probability_for_coding_incomplete(self):
        result = estimator.estimate(_pred("coding_incomplete"), _claim(100_000, 100_000))
        assert result["reimbursement_probability"] == REIMBURSEMENT_PROB_SPECIAL["coding_incomplete"]

    def test_low_probability_for_grouping_invalid(self):
        result = estimator.estimate(_pred("grouping_invalid"), _claim(100_000, 100_000))
        assert result["reimbursement_probability"] == REIMBURSEMENT_PROB_SPECIAL["grouping_invalid"]


# ── Edge case tests ────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_base_tariff_zero_does_not_crash(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(0, 100_000))
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert result["reimbursement_amount"] == 0.0

    def test_actual_tariff_zero(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 0))
        assert result["financial_gap"] < 0
        assert result["estimated_loss_idr"] == 0.0

    def test_missing_tariff_fields_default_to_zero(self):
        result = estimator.estimate(_pred("grouping_valid"), {})
        assert "risk_level" in result
        assert "reimbursement_probability" in result

    def test_negative_base_tariff(self):
        # Should not raise; risk level should still be computed
        result = estimator.estimate(_pred("grouping_valid"), _claim(-100_000, 50_000))
        assert "risk_level" in result

    def test_exact_boundary_at_low_medium(self):
        # ratio = 1.05 exactly → still LOW (boundary inclusive)
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 105_000))
        assert result["risk_level"] == "LOW"

    def test_just_above_low_medium_boundary(self):
        # ratio = 1.051 → MEDIUM
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 105_100))
        assert result["risk_level"] == "MEDIUM"

    def test_output_has_all_required_keys(self):
        result = estimator.estimate(_pred("grouping_valid"), _claim(100_000, 100_000))
        required_keys = {
            "reimbursement_amount", "submitted_amount", "financial_gap",
            "gap_percentage", "risk_level", "risk_explanation",
            "estimated_loss_idr", "cash_flow_risk_days", "reimbursement_probability",
        }
        assert required_keys.issubset(result.keys())
