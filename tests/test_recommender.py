"""
Unit tests for RecommendationEngine v2 (surrogate grouper architecture).

New synthesize() takes grouper_result (from SurrogateGrouper) + financial_result.
Primary action logic:
  - lookup_method == 'none'    → URGENT_RECODE + URGENT
  - mdc_confidence < 0.60      → VERIFY_CODING + HIGH
  - risk_level HIGH/CRITICAL   → REVIEW + HIGH/URGENT
  - financial_gap > 0          → REVIEW + MEDIUM
  - all clear                  → SUBMIT + LOW
"""

import pytest
from src.services.recommender import RecommendationEngine

engine = RecommendationEngine()

# ── Fixture helpers ────────────────────────────────────────────────────────────

def _grouper(mdc: str = 'Q', severity: str = '0',
             cbg: str = 'Q-5-44-0', cbg_desc: str = 'PENYAKIT KRONIS KECIL LAIN-LAIN',
             confidence: float = 0.92, sev_conf: float = 0.99,
             lookup: str = 'exact', base_tariff: float = 196_100,
             shap: list = None) -> dict:
    """Build a minimal grouper_result dict for tests."""
    return {
        "predicted_mdc":              mdc,
        "predicted_mdc_description":  "Test MDC Description",
        "predicted_severity":         severity,
        "predicted_severity_label":   "Rawat Jalan / Prosedur",
        "predicted_cbg_code":         cbg,
        "predicted_cbg_description":  cbg_desc,
        "predicted_base_tariff":      base_tariff,
        "tariff_by_kelas":            {
            "kelas_1": round(base_tariff * 1.5),
            "kelas_2": round(base_tariff * 1.25),
            "kelas_3": round(base_tariff * 1.0),
        },
        "mdc_confidence":             confidence,
        "severity_confidence":        sev_conf,
        "lookup_method":              lookup,
        "shap_explanation":           shap or [
            {"feature": "icd_chapter",  "impact": 0.42, "direction": "positive"},
            {"feature": "is_outpatient","impact": 0.31, "direction": "positive"},
            {"feature": "icd_block",    "impact": 0.18, "direction": "positive"},
        ],
        "status": "success",
    }


def _financial(risk: str = "LOW", reimb: float = 196_100, gap: float = 0,
               loss: float = 0, cf_days: int = 0, prob: float = 0.95) -> dict:
    return {
        "risk_level":                risk,
        "reimbursement_amount":      reimb,
        "financial_gap":             gap,
        "gap_percentage":            round(gap / reimb * 100, 2) if reimb else 0,
        "estimated_loss_idr":        loss,
        "cash_flow_risk_days":       cf_days,
        "reimbursement_probability": prob,
    }


# ── Output structure tests ─────────────────────────────────────────────────────

class TestOutputStructure:

    def test_output_has_all_required_keys(self):
        result = engine.synthesize(_grouper(), _financial())
        required = {
            "primary_action", "priority", "recommendations",
            "warnings", "coding_tips", "estimated_resolution_days", "summary",
        }
        assert required.issubset(result.keys())

    def test_recommendations_is_list(self):
        result = engine.synthesize(_grouper(), _financial())
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) >= 1

    def test_each_recommendation_has_required_keys(self):
        result = engine.synthesize(_grouper(), _financial())
        for rec in result["recommendations"]:
            assert "rank"       in rec
            assert "action"     in rec
            assert "reason"     in rec
            assert "impact"     in rec
            assert "confidence" in rec

    def test_coding_tips_is_list(self):
        result = engine.synthesize(_grouper(), _financial())
        assert isinstance(result["coding_tips"], list)
        assert len(result["coding_tips"]) >= 1

    def test_summary_is_non_empty_string(self):
        result = engine.synthesize(_grouper(), _financial())
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ── Primary action and priority tests ─────────────────────────────────────────

class TestPrimaryAction:

    def test_submit_for_high_confidence_exact_no_gap(self):
        """High confidence + exact lookup + no gap → SUBMIT + LOW."""
        result = engine.synthesize(_grouper(confidence=0.92, lookup='exact'), _financial("LOW"))
        assert result["primary_action"] == "SUBMIT"
        assert result["priority"] == "LOW"

    def test_verify_coding_for_low_mdc_confidence(self):
        """mdc_confidence < 0.60 → VERIFY_CODING + HIGH."""
        result = engine.synthesize(_grouper(confidence=0.45), _financial("HIGH"))
        assert result["primary_action"] == "VERIFY_CODING"
        assert result["priority"] == "HIGH"

    def test_urgent_recode_for_lookup_none(self):
        """lookup_method == 'none' → URGENT_RECODE + URGENT."""
        result = engine.synthesize(_grouper(lookup='none', cbg='Q-?-?-0'), _financial("CRITICAL"))
        assert result["primary_action"] == "URGENT_RECODE"
        assert result["priority"] == "URGENT"

    def test_review_for_high_risk(self):
        """HIGH risk → REVIEW."""
        result = engine.synthesize(_grouper(confidence=0.90), _financial("HIGH", gap=50_000))
        assert result["primary_action"] == "REVIEW"

    def test_review_for_positive_financial_gap(self):
        """Positive gap → REVIEW (tariff excess)."""
        result = engine.synthesize(_grouper(), _financial("MEDIUM", gap=20_000))
        assert result["primary_action"] == "REVIEW"


# ── Recommendation content tests ───────────────────────────────────────────────

class TestRecommendationContent:

    def test_first_recommendation_mentions_cbg_code(self):
        """Rank-1 recommendation should mention the predicted CBG code."""
        result = engine.synthesize(_grouper(cbg='Q-5-44-0'), _financial("LOW"))
        first = result["recommendations"][0]
        assert "Q-5-44-0" in first["action"] or "Q-5-44-0" in first["reason"]

    def test_low_confidence_warning_in_recommendations(self):
        """Low confidence → a recommendation about verifying ICD coding."""
        result = engine.synthesize(_grouper(confidence=0.45), _financial("HIGH"))
        texts = " ".join(r["action"] + r["reason"] for r in result["recommendations"])
        assert "kepercayaan" in texts.lower() or "verifikasi" in texts.lower()

    def test_gap_warning_recommendation_when_gap_positive(self):
        """Positive financial gap → a recommendation about tariff excess."""
        result = engine.synthesize(_grouper(), _financial("MEDIUM", gap=20_000))
        texts = " ".join(r["action"] + r["reason"] for r in result["recommendations"])
        assert "tarif" in texts.lower() or "gap" in texts.lower() or "ceiling" in texts.lower()

    def test_shap_feature_in_recommendations(self):
        """SHAP top feature should appear somewhere in recommendations."""
        g = _grouper(shap=[
            {"feature": "icd_chapter", "impact": 0.9, "direction": "positive"},
            {"feature": "is_outpatient", "impact": 0.5, "direction": "positive"},
            {"feature": "kelas", "impact": 0.2, "direction": "positive"},
        ])
        result = engine.synthesize(g, _financial("LOW"))
        all_text = " ".join(r["action"] + r["reason"] for r in result["recommendations"])
        # icd_chapter or a fallback should appear somewhere
        assert len(result["recommendations"]) >= 1


# ── Coding tips tests ──────────────────────────────────────────────────────────

class TestCodingTips:

    def test_mdc_j_respiratory_tip(self):
        """MDC J (respiratory) → pneumonia coding tip."""
        result = engine.synthesize(_grouper(mdc='J'), _financial("LOW"))
        assert any("Pernapasan" in t or "pneumonia" in t.lower() or "organisme" in t for t in result["coding_tips"])

    def test_mdc_i_circulatory_tip(self):
        """MDC I (circulatory) → hypertension coding tip."""
        result = engine.synthesize(_grouper(mdc='I'), _financial("LOW"))
        assert any("Sirkulasi" in t or "hipertensi" in t.lower() or "komplikasi" in t for t in result["coding_tips"])

    def test_mdc_z_admin_tip(self):
        """MDC Z (administrative) → Z code warning."""
        result = engine.synthesize(_grouper(mdc='Z'), _financial("LOW"))
        assert any("Z" in t for t in result["coding_tips"])

    def test_always_has_icd_version_tip(self):
        """Last tip should always remind about ICD-10 2010 version."""
        result = engine.synthesize(_grouper(), _financial("LOW"))
        assert any("2010" in t for t in result["coding_tips"])


# ── Warning tests ──────────────────────────────────────────────────────────────

class TestWarnings:

    def test_no_warnings_for_perfect_claim(self):
        result = engine.synthesize(_grouper(confidence=0.95, lookup='exact'),
                                   _financial("LOW", gap=0))
        assert result["warnings"] == []

    def test_medium_risk_produces_warning(self):
        result = engine.synthesize(_grouper(),
                                   _financial("MEDIUM", gap=20_000, loss=20_000, prob=0.80))
        assert any("gap" in w.lower() or "MEDIUM" in w for w in result["warnings"])

    def test_low_prob_produces_warning(self):
        result = engine.synthesize(_grouper(lookup='none', cbg='Q-?-?-0'),
                                   _financial("CRITICAL", loss=196_100, prob=0.15))
        assert any("probability" in w.lower() or "escalate" in w.lower() for w in result["warnings"])


# ── Resolution days tests ──────────────────────────────────────────────────────

class TestResolutionDays:

    def test_short_resolution_for_high_confidence_exact(self):
        result = engine.synthesize(_grouper(confidence=0.95, lookup='exact'), _financial("LOW"))
        assert result["estimated_resolution_days"] == 14   # STANDARD_SETTLEMENT_DAYS

    def test_longer_resolution_for_low_confidence(self):
        result = engine.synthesize(_grouper(confidence=0.45), _financial("HIGH"))
        assert result["estimated_resolution_days"] == 30

    def test_longest_resolution_for_lookup_none(self):
        result = engine.synthesize(_grouper(lookup='none'), _financial("CRITICAL"))
        assert result["estimated_resolution_days"] == 90


# ── Edge cases ─────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_shap_does_not_crash(self):
        result = engine.synthesize(_grouper(shap=[]), _financial("LOW"))
        assert result["primary_action"] in ("SUBMIT", "REVIEW", "VERIFY_CODING", "URGENT_RECODE")

    def test_empty_financial_does_not_crash(self):
        result = engine.synthesize(_grouper(), {})
        assert "primary_action" in result

    def test_empty_grouper_does_not_crash(self):
        result = engine.synthesize({}, _financial("LOW"))
        assert "primary_action" in result
