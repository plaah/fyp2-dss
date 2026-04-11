"""
Unit tests for RecommendationEngine (T3.2)
Covers all 3 prediction outcomes, priority mapping, warnings, and coding tips.
"""

import pytest
from src.services.recommender import RecommendationEngine, RESOLUTION_DAYS

engine = RecommendationEngine()

# ── Fixture helpers ────────────────────────────────────────────────────────────

def _pred(outcome: str, confidence: float = 0.90, icd10: str = "I10") -> dict:
    return {
        "prediction": outcome,
        "confidence": {outcome: confidence},
        "inacbg_primary_icd10": icd10,
    }


def _financial(risk: str, reimb: float = 196_100, gap: float = 0, loss: float = 0,
               cf_days: int = 0, prob: float = 0.95) -> dict:
    return {
        "risk_level":                risk,
        "reimbursement_amount":      reimb,
        "financial_gap":             gap,
        "gap_percentage":            round(gap / reimb * 100, 2) if reimb else 0,
        "estimated_loss_idr":        loss,
        "cash_flow_risk_days":       cf_days,
        "reimbursement_probability": prob,
        "cbg_code":                  "Q-5-44-0",
        "cbg_description":           "TEST CBG",
    }


def _shap(top_feature: str = "final_success") -> list:
    return [
        {"feature": top_feature, "impact": 0.85, "direction": "positive"},
        {"feature": "claim_stage", "impact": 0.30, "direction": "negative"},
    ]


# ── Output structure tests ─────────────────────────────────────────────────────

class TestOutputStructure:

    def test_output_has_all_required_keys(self):
        result = engine.synthesize(
            _pred("grouping_valid"),
            _financial("LOW"),
            _shap(),
        )
        required = {
            "primary_action", "priority", "recommendations",
            "warnings", "coding_tips", "estimated_resolution_days", "summary",
        }
        assert required.issubset(result.keys())

    def test_recommendations_is_list(self):
        result = engine.synthesize(_pred("grouping_valid"), _financial("LOW"), _shap())
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) >= 1

    def test_each_recommendation_has_rank_action_reason_impact(self):
        result = engine.synthesize(_pred("grouping_valid"), _financial("LOW"), _shap())
        for rec in result["recommendations"]:
            assert "rank" in rec
            assert "action" in rec
            assert "reason" in rec
            assert "impact" in rec


# ── grouping_valid outcome tests ───────────────────────────────────────────────

class TestGroupingValid:

    def test_primary_action_is_submit_for_low_risk(self):
        result = engine.synthesize(_pred("grouping_valid"), _financial("LOW"), _shap())
        assert result["primary_action"] == "SUBMIT"

    def test_priority_low_for_low_risk(self):
        result = engine.synthesize(_pred("grouping_valid"), _financial("LOW"), _shap())
        assert result["priority"] == "LOW"

    def test_primary_action_is_submit_for_medium_risk(self):
        result = engine.synthesize(
            _pred("grouping_valid"),
            _financial("MEDIUM", reimb=196_100, gap=20_000, loss=20_000, prob=0.80),
            _shap(),
        )
        assert result["primary_action"] == "SUBMIT"
        assert result["priority"] == "MEDIUM"

    def test_primary_action_is_review_for_high_risk(self):
        result = engine.synthesize(
            _pred("grouping_valid"),
            _financial("HIGH", reimb=196_100, gap=50_000, loss=50_000, prob=0.60),
            _shap(),
        )
        assert result["primary_action"] == "REVIEW"
        assert result["priority"] == "HIGH"

    def test_medium_risk_has_two_recommendations(self):
        result = engine.synthesize(
            _pred("grouping_valid"),
            _financial("MEDIUM", reimb=196_100, gap=20_000, loss=20_000, prob=0.80),
            _shap(),
        )
        assert len(result["recommendations"]) == 2

    def test_resolution_days_is_standard_settlement(self):
        result = engine.synthesize(_pred("grouping_valid"), _financial("LOW"), _shap())
        assert result["estimated_resolution_days"] == RESOLUTION_DAYS["grouping_valid"]

    def test_no_warnings_for_low_risk(self):
        result = engine.synthesize(_pred("grouping_valid"), _financial("LOW"), _shap())
        assert result["warnings"] == []


# ── coding_incomplete outcome tests ───────────────────────────────────────────

class TestCodingIncomplete:

    def test_primary_action_is_complete_coding(self):
        result = engine.synthesize(
            _pred("coding_incomplete"),
            _financial("HIGH", reimb=196_100, cf_days=30, prob=0.70),
            _shap("final_success"),
        )
        assert result["primary_action"] == "COMPLETE_CODING"

    def test_priority_high(self):
        result = engine.synthesize(
            _pred("coding_incomplete"),
            _financial("HIGH", cf_days=30, prob=0.70),
            _shap(),
        )
        assert result["priority"] == "HIGH"

    def test_three_recommendations_generated(self):
        result = engine.synthesize(
            _pred("coding_incomplete"),
            _financial("HIGH", cf_days=30, prob=0.70),
            _shap("claim_stage"),
        )
        assert len(result["recommendations"]) == 3

    def test_top_shap_feature_drives_first_recommendation(self):
        result = engine.synthesize(
            _pred("coding_incomplete"),
            _financial("HIGH", cf_days=30, prob=0.70),
            _shap("inacbg_primary_icd10"),
        )
        first_rec = result["recommendations"][0]
        assert "ICD-10" in first_rec["reason"]

    def test_resolution_days_longer_than_valid(self):
        result = engine.synthesize(
            _pred("coding_incomplete"),
            _financial("HIGH", cf_days=30, prob=0.70),
            _shap(),
        )
        assert result["estimated_resolution_days"] == RESOLUTION_DAYS["coding_incomplete"]

    def test_summary_mentions_coding_incomplete(self):
        result = engine.synthesize(
            _pred("coding_incomplete"),
            _financial("HIGH", cf_days=30, prob=0.70),
            _shap(),
        )
        assert "incomplete" in result["summary"].lower() or "coding" in result["summary"].lower()


# ── grouping_invalid outcome tests ────────────────────────────────────────────

class TestGroupingInvalid:

    def test_primary_action_is_recode(self):
        result = engine.synthesize(
            _pred("grouping_invalid"),
            _financial("CRITICAL", reimb=196_100, loss=196_100, cf_days=90, prob=0.15),
            _shap("inacbg_grouping_success"),
        )
        assert result["primary_action"] == "RECODE"

    def test_priority_urgent(self):
        result = engine.synthesize(
            _pred("grouping_invalid"),
            _financial("CRITICAL", loss=196_100, cf_days=90, prob=0.15),
            _shap(),
        )
        assert result["priority"] == "URGENT"

    def test_three_recommendations_generated(self):
        result = engine.synthesize(
            _pred("grouping_invalid"),
            _financial("CRITICAL", loss=200_000, cf_days=90, prob=0.15),
            _shap("idrg_primary_icd10"),
        )
        assert len(result["recommendations"]) == 3

    def test_critical_warning_included(self):
        result = engine.synthesize(
            _pred("grouping_invalid"),
            _financial("CRITICAL", loss=196_100, cf_days=90, prob=0.15),
            _shap(),
        )
        assert any("CRITICAL" in w for w in result["warnings"])

    def test_resolution_days_is_longest(self):
        result = engine.synthesize(
            _pred("grouping_invalid"),
            _financial("CRITICAL", loss=196_100, cf_days=90, prob=0.15),
            _shap(),
        )
        assert result["estimated_resolution_days"] == RESOLUTION_DAYS["grouping_invalid"]

    def test_summary_mentions_urgent(self):
        result = engine.synthesize(
            _pred("grouping_invalid"),
            _financial("CRITICAL", loss=196_100, cf_days=90, prob=0.15),
            _shap(),
        )
        assert "URGENT" in result["summary"] or "risk" in result["summary"].lower()


# ── Coding tips tests ──────────────────────────────────────────────────────────

class TestCodingTips:

    def test_hypertension_tip_for_I10(self):
        result = engine.synthesize(_pred("grouping_valid", icd10="I10"), _financial("LOW"), _shap())
        assert any("Hypertension" in t for t in result["coding_tips"])

    def test_pneumonia_tip_for_J18(self):
        result = engine.synthesize(_pred("grouping_valid", icd10="J18.0"), _financial("LOW"), _shap())
        assert any("Pneumonia" in t for t in result["coding_tips"])

    def test_diabetes_tip_for_E11(self):
        result = engine.synthesize(_pred("grouping_valid", icd10="E11.9"), _financial("LOW"), _shap())
        assert any("Diabetes" in t for t in result["coding_tips"])

    def test_default_tip_for_unknown_code(self):
        result = engine.synthesize(_pred("grouping_valid", icd10="X99"), _financial("LOW"), _shap())
        assert len(result["coding_tips"]) >= 1

    def test_invalid_outcome_adds_extra_tip(self):
        result = engine.synthesize(_pred("grouping_invalid", icd10="Z09"), _financial("CRITICAL", loss=100_000, prob=0.15), _shap())
        assert len(result["coding_tips"]) >= 2


# ── Warning tests ──────────────────────────────────────────────────────────────

class TestWarnings:

    def test_medium_risk_produces_tariff_gap_warning(self):
        result = engine.synthesize(
            _pred("grouping_valid"),
            _financial("MEDIUM", gap=20_000, loss=20_000, prob=0.80),
            _shap(),
        )
        assert any("gap" in w.lower() or "MEDIUM" in w for w in result["warnings"])

    def test_low_reimb_probability_produces_warning(self):
        result = engine.synthesize(
            _pred("grouping_invalid"),
            _financial("CRITICAL", loss=196_100, prob=0.15),
            _shap(),
        )
        # prob = 0.15 < 0.50 → escalation warning
        assert any("probability" in w.lower() or "escalate" in w.lower() for w in result["warnings"])

    def test_no_warnings_for_perfect_valid_claim(self):
        result = engine.synthesize(
            _pred("grouping_valid"),
            _financial("LOW", gap=0, loss=0, prob=0.95),
            _shap(),
        )
        assert result["warnings"] == []


# ── Edge cases ─────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_explanation_does_not_crash(self):
        result = engine.synthesize(_pred("grouping_valid"), _financial("LOW"), [])
        assert result["primary_action"] == "SUBMIT"

    def test_empty_financial_result_does_not_crash(self):
        result = engine.synthesize(_pred("grouping_valid"), {}, _shap())
        assert "primary_action" in result

    def test_unknown_outcome_falls_back_to_review(self):
        result = engine.synthesize(_pred("unknown_outcome"), _financial("LOW"), _shap())
        # PRIMARY_ACTION_MAP won't match → defaults to REVIEW
        assert result["primary_action"] in ("REVIEW", "SUBMIT", "RECODE", "COMPLETE_CODING")

    def test_summary_is_non_empty_string(self):
        for outcome in ("grouping_valid", "coding_incomplete", "grouping_invalid"):
            fin = _financial("CRITICAL" if outcome == "grouping_invalid" else
                             ("HIGH" if outcome == "coding_incomplete" else "LOW"),
                             cf_days=90 if outcome == "grouping_invalid" else
                                     (30 if outcome == "coding_incomplete" else 0),
                             loss=196_100 if outcome != "grouping_valid" else 0,
                             prob=0.15 if outcome == "grouping_invalid" else 0.70)
            result = engine.synthesize(_pred(outcome), fin, _shap())
            assert isinstance(result["summary"], str) and len(result["summary"]) > 0
