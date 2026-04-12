"""
Unit tests for FinancialEstimator v2 (surrogate grouper architecture).

v2 risk logic:
  - lookup_method == 'none'         → CRITICAL
  - mdc_confidence < 0.60           → HIGH
  - tariff_ratio > 1.20             → HIGH
  - tariff_ratio > 1.05             → MEDIUM
  - lookup_method != 'exact'        → MEDIUM (approximate)
  - all clear                       → LOW
"""

import pytest
from src.services.financial_estimator import FinancialEstimator, KELAS_MULTIPLIERS

estimator = FinancialEstimator()

# ── helpers ────────────────────────────────────────────────────────────────────

_KELAS_MUL = {'kelas_1': 1.50, 'kelas_2': 1.25, 'kelas_3': 1.00}


def _grouper(base: float, confidence: float = 0.95,
             lookup: str = 'exact', kelas: str = 'kelas_3') -> dict:
    """Build a minimal grouper_result dict for tests."""
    return {
        'predicted_base_tariff': base,
        'tariff_by_kelas': {k: round(base * m) for k, m in _KELAS_MUL.items()},
        'mdc_confidence':   confidence,
        'lookup_method':    lookup,
        'predicted_cbg_code': 'Q-5-44-0',
    }


# ── Risk level tests ───────────────────────────────────────────────────────────

class TestRiskLevels:

    def test_risk_critical_when_lookup_none(self):
        g = _grouper(200_000, lookup='none')
        result = estimator.estimate(g, 200_000)
        assert result["risk_level"] == "CRITICAL"

    def test_risk_high_when_mdc_confidence_low(self):
        g = _grouper(200_000, confidence=0.50)
        result = estimator.estimate(g, 200_000)
        assert result["risk_level"] == "HIGH"

    def test_risk_low_when_submitted_within_5pct(self):
        # actual = base × 1.03 → ratio ≤ 1.05 → LOW
        g = _grouper(100_000)
        result = estimator.estimate(g, 103_000)
        assert result["risk_level"] == "LOW"

    def test_risk_medium_when_submitted_between_5_and_20pct(self):
        # actual = base × 1.10 → ratio 1.10 → MEDIUM
        g = _grouper(100_000)
        result = estimator.estimate(g, 110_000)
        assert result["risk_level"] == "MEDIUM"

    def test_risk_high_when_submitted_over_20pct(self):
        # actual = base × 1.25 → ratio 1.25 → HIGH
        g = _grouper(100_000)
        result = estimator.estimate(g, 125_000)
        assert result["risk_level"] == "HIGH"

    def test_risk_medium_when_lookup_approximate(self):
        # fallback lookup → MEDIUM even if tariff is fine
        g = _grouper(100_000, lookup='fallback_mdc_sev_kelas')
        result = estimator.estimate(g, 100_000)
        assert result["risk_level"] == "MEDIUM"


# ── Kelas multiplier tests ─────────────────────────────────────────────────────

class TestKelasMultipliers:

    def test_kelas_3_ceiling_equals_base(self):
        g = _grouper(200_000, kelas='kelas_3')
        result = estimator.estimate(g, 200_000, kelas='kelas_3')
        assert result["reimbursement_amount"] == pytest.approx(200_000.0)

    def test_kelas_2_ceiling_is_1_25x_base(self):
        g = _grouper(200_000, kelas='kelas_2')
        result = estimator.estimate(g, 250_000, kelas='kelas_2')
        assert result["reimbursement_amount"] == pytest.approx(250_000.0)

    def test_kelas_1_ceiling_is_1_50x_base(self):
        g = _grouper(200_000, kelas='kelas_1')
        result = estimator.estimate(g, 300_000, kelas='kelas_1')
        assert result["reimbursement_amount"] == pytest.approx(300_000.0)

    def test_unknown_kelas_defaults_to_kelas_3(self):
        g = _grouper(100_000)
        result = estimator.estimate(g, 100_000, kelas='kelas_X')
        assert result["reimbursement_amount"] == pytest.approx(100_000.0)

    def test_kelas_2_low_risk_when_submitted_at_ceiling(self):
        # kelas_2 ceiling = 200k × 1.25 = 250k; submit exactly 250k → ratio 1.0 → LOW
        g = _grouper(200_000, kelas='kelas_2')
        result = estimator.estimate(g, 250_000, kelas='kelas_2')
        assert result["risk_level"] == "LOW"


# ── Financial calculation tests ────────────────────────────────────────────────

class TestFinancialCalculations:

    def test_financial_gap_positive_when_over_ceiling(self):
        g = _grouper(196_100)
        result = estimator.estimate(g, 210_000)
        assert result["financial_gap"] > 0

    def test_financial_gap_negative_when_under_ceiling(self):
        g = _grouper(200_000)
        result = estimator.estimate(g, 180_000)
        assert result["financial_gap"] < 0

    def test_estimated_loss_is_zero_when_under_ceiling(self):
        g = _grouper(200_000)
        result = estimator.estimate(g, 180_000)
        assert result["estimated_loss_idr"] == 0.0

    def test_estimated_loss_equals_gap_when_over_ceiling(self):
        g = _grouper(200_000)
        result = estimator.estimate(g, 250_000)
        assert result["estimated_loss_idr"] == pytest.approx(50_000.0)

    def test_gap_percentage_calculation(self):
        g = _grouper(196_100)
        result = estimator.estimate(g, 210_000)
        expected_pct = round((210_000 - 196_100) / 196_100 * 100, 2)
        assert result["gap_percentage"] == pytest.approx(expected_pct, rel=1e-2)


# ── Cash flow delay tests ──────────────────────────────────────────────────────

class TestCashFlowDelay:

    def test_no_delay_for_high_confidence_exact_lookup(self):
        g = _grouper(100_000, confidence=0.95, lookup='exact')
        result = estimator.estimate(g, 100_000)
        assert result["cash_flow_risk_days"] == 0

    def test_delay_for_low_confidence(self):
        g = _grouper(100_000, confidence=0.50)
        result = estimator.estimate(g, 100_000)
        assert result["cash_flow_risk_days"] == 30

    def test_delay_for_lookup_none(self):
        g = _grouper(100_000, lookup='none')
        result = estimator.estimate(g, 100_000)
        assert result["cash_flow_risk_days"] == 90

    def test_minor_delay_for_fallback_lookup(self):
        g = _grouper(100_000, lookup='fallback_mdc_sev')
        result = estimator.estimate(g, 100_000)
        assert result["cash_flow_risk_days"] == 14


# ── Edge case tests ────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_base_tariff_zero_does_not_crash(self):
        g = _grouper(0)
        result = estimator.estimate(g, 100_000)
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert result["reimbursement_amount"] == 0.0

    def test_actual_tariff_zero(self):
        g = _grouper(100_000)
        result = estimator.estimate(g, 0)
        assert result["financial_gap"] < 0
        assert result["estimated_loss_idr"] == 0.0

    def test_missing_grouper_fields_default_gracefully(self):
        result = estimator.estimate({}, 0)
        assert "risk_level" in result
        assert "reimbursement_probability" in result

    def test_negative_base_tariff(self):
        g = _grouper(-100_000)
        result = estimator.estimate(g, 50_000)
        assert "risk_level" in result

    def test_exact_boundary_at_low_medium(self):
        # ratio = 1.05 exactly → LOW (boundary inclusive)
        g = _grouper(100_000)
        result = estimator.estimate(g, 105_000)
        assert result["risk_level"] == "LOW"

    def test_just_above_low_medium_boundary(self):
        # ratio ≈ 1.051 → MEDIUM
        g = _grouper(100_000)
        result = estimator.estimate(g, 105_100)
        assert result["risk_level"] == "MEDIUM"

    def test_output_has_all_required_keys(self):
        g = _grouper(100_000)
        result = estimator.estimate(g, 100_000)
        required_keys = {
            "reimbursement_amount", "submitted_amount", "financial_gap",
            "gap_percentage", "risk_level", "risk_explanation",
            "estimated_loss_idr", "cash_flow_risk_days", "reimbursement_probability",
        }
        assert required_keys.issubset(result.keys())
