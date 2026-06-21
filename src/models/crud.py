"""
CRUD Operations Module
========================
Provides clean database access functions for the DSS.
All functions expect to be called within a Flask application context.

Functions:
  save_prediction()        — persist a /full-assessment result
  get_recent_predictions() — last N predictions for the history table
  get_stats_summary()      — aggregate stats for /stats endpoint
  get_prediction_history() — daily counts for the line chart
  seed_from_csv()          — populate predictions from synthetic dataset
"""

from __future__ import annotations

import csv
import os
import random
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

from sqlalchemy import cast, Date as SADate

from src.models.db_models import db, Prediction, SystemStats, PredictionFeedback


def save_prediction(data: Dict[str, Any]) -> Prediction:
    """
    Persist a full-assessment result to the predictions table.

    Args:
        data: Merged dict containing keys from the /full-assessment response:
              prediction (dict), financial (dict), recommendation (dict),
              plus the original request body fields.

    Returns:
        Prediction: The newly created ORM instance (id populated after commit).
    """
    pred_block = data.get("prediction", {})
    fin_block  = data.get("financial",  {})
    rec_block  = data.get("recommendation", {})
    req_body   = data.get("request_body", {})

    # Surrogate grouper v2 — derive ml_prediction from primary_action
    # (legacy: pred_block had a "prediction" key with the 3-class label)
    _ACTION_TO_LABEL = {
        "SUBMIT":        "grouping_valid",
        "REVIEW":        "grouping_valid",
        "VERIFY_CODING": "coding_incomplete",
        "URGENT_RECODE": "grouping_invalid",
    }
    primary_action = rec_block.get("primary_action", "")
    ml_prediction = (
        _ACTION_TO_LABEL.get(primary_action)
        or pred_block.get("prediction")   # legacy fallback
    )

    # SHAP explanation lives in pred_block["shap_explanation"] (surrogate v2)
    # or pred_block["explanation"] (legacy)
    shap_exp   = pred_block.get("shap_explanation") or pred_block.get("explanation", [])
    top_shap   = shap_exp[0].get("feature") if shap_exp else None

    # Legacy confidence sub-dict (v1 only)
    confidence = pred_block.get("confidence", {})

    row = Prediction(
        claim_id                 = req_body.get("claim_id"),
        idrg_primary_icd10       = req_body.get("primary_icd10") or req_body.get("idrg_primary_icd10"),
        inacbg_primary_icd10     = req_body.get("inacbg_icd10") or req_body.get("inacbg_primary_icd10"),
        idrg_icd9_procedure      = req_body.get("icd9_procedure") or req_body.get("idrg_icd9_procedure"),
        kelas                    = req_body.get("kelas"),
        care_type                = req_body.get("care_type"),
        entry_type               = req_body.get("entry_type"),
        ml_prediction            = ml_prediction,
        confidence_valid         = confidence.get("grouping_valid"),
        confidence_incomplete    = confidence.get("coding_incomplete"),
        confidence_invalid       = confidence.get("grouping_invalid"),
        risk_level               = fin_block.get("risk_level"),
        base_tariff              = _to_int(fin_block.get("reimbursement_amount")),
        actual_tariff            = _to_int(fin_block.get("submitted_amount")),
        financial_gap            = _to_int(fin_block.get("financial_gap")),
        reimbursement_probability= fin_block.get("reimbursement_probability"),
        primary_action           = rec_block.get("primary_action"),
        top_shap_feature         = top_shap,
        source                   = data.get("source", "manual"),
    )
    db.session.add(row)
    db.session.commit()
    return row


def get_recent_predictions(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Return the most recent predictions ordered by created_at descending.

    Args:
        limit: Maximum number of rows to return (default 20).

    Returns:
        List of dicts, each representing one Prediction row.
    """
    rows = (
        Prediction.query
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]


def get_stats_summary() -> Dict[str, Any]:
    """
    Compute aggregate statistics across all stored predictions.

    Returns:
        dict with keys:
            total_predictions, today_predictions,
            grouping_valid_pct, coding_incomplete_pct, grouping_invalid_pct,
            avg_reimbursement_probability, total_financial_gap_idr,
            recent_predictions (last 5)
    """
    total = Prediction.query.count()
    today = date.today()
    today_count = Prediction.query.filter(
        db.func.date(Prediction.created_at) == today
    ).count()

    # Label distribution
    label_counts = (
        db.session.query(Prediction.ml_prediction, db.func.count())
        .group_by(Prediction.ml_prediction)
        .all()
    )
    counts = {label: cnt for label, cnt in label_counts}
    valid_cnt      = counts.get("grouping_valid",    0)
    incomplete_cnt = counts.get("coding_incomplete", 0)
    invalid_cnt    = counts.get("grouping_invalid",  0)
    # Fold null/unknown labels (from v2 architecture migration) into valid_cnt
    # so percentages always sum to 100%.
    other_cnt = total - valid_cnt - incomplete_cnt - invalid_cnt
    if other_cnt > 0:
        valid_cnt += other_cnt

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total > 0 else 0.0

    # Averages
    avg_prob_row = db.session.query(
        db.func.avg(Prediction.reimbursement_probability)
    ).scalar()
    avg_prob = round(float(avg_prob_row), 4) if avg_prob_row is not None else 0.0

    total_gap_row = db.session.query(
        db.func.sum(Prediction.financial_gap)
    ).scalar()
    total_gap = int(total_gap_row) if total_gap_row is not None else 0

    # Risk distribution
    risk_counts = (
        db.session.query(Prediction.risk_level, db.func.count())
        .group_by(Prediction.risk_level)
        .all()
    )
    risk_dist = {r or "UNKNOWN": c for r, c in risk_counts}

    return {
        "total_predictions":            total,
        "today_predictions":            today_count,
        "grouping_valid_pct":           pct(valid_cnt),
        "coding_incomplete_pct":        pct(incomplete_cnt),
        "grouping_invalid_pct":         pct(invalid_cnt),
        "grouping_valid_count":         valid_cnt,
        "coding_incomplete_count":      incomplete_cnt,
        "grouping_invalid_count":       invalid_cnt,
        "avg_reimbursement_probability": avg_prob,
        "total_financial_gap_idr":      total_gap,
        "risk_distribution":            risk_dist,
        "recent_predictions":           get_recent_predictions(limit=5),
    }


def get_prediction_history(days: int = 7) -> List[Dict[str, Any]]:
    """
    Return daily prediction counts for the last N days (for line chart).

    Args:
        days: Number of days to include (default 7).

    Returns:
        List of dicts [{"date": "2026-04-11", "count": 12, ...}, ...]
        One entry per day, ordered ascending.
    """
    cutoff = date.today() - timedelta(days=days - 1)
    rows = (
        db.session.query(
            cast(Prediction.created_at, SADate).label("day"),
            db.func.count().label("total"),
            db.func.sum(
                db.case((Prediction.ml_prediction == "grouping_valid", 1), else_=0)
            ).label("valid"),
        )
        .filter(Prediction.created_at >= cutoff)
        .group_by(cast(Prediction.created_at, SADate))
        .order_by(cast(Prediction.created_at, SADate))
        .all()
    )
    row_map = {r.day: r for r in rows}
    result = []
    for i in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        r = row_map.get(d)
        result.append({
            "date":  d.isoformat(),
            "count": r.total if r else 0,
            "valid": r.valid if r else 0,
        })
    return result


def seed_from_csv(filepath: str = "data/synthetic_bpjs.csv", limit: int = 100) -> int:
    """
    Populate the predictions table with a sample from the synthetic dataset.
    Skips seeding if predictions table already has rows.

    Args:
        filepath: Path to synthetic_bpjs.csv (relative to project root).
        limit:    Maximum number of rows to seed (default 100).

    Returns:
        int: Number of rows inserted (0 if already seeded).
    """
    if Prediction.query.count() > 0:
        return 0

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    csv_path = os.path.join(base_dir, filepath)

    if not os.path.isfile(csv_path):
        return 0

    label_to_action = {
        "grouping_valid":    "SUBMIT",
        "coding_incomplete": "COMPLETE_CODING",
        "grouping_invalid":  "RECODE",
    }
    label_to_risk = {
        "grouping_valid":    "LOW",
        "coding_incomplete": "HIGH",
        "grouping_invalid":  "CRITICAL",
    }

    inserted = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)

    random.shuffle(rows)
    rows = rows[:limit]

    base_dt = datetime.utcnow() - timedelta(days=6)
    for idx, row in enumerate(rows):
        label  = row.get("ml_label", "grouping_valid")
        action = label_to_action.get(label, "SUBMIT")
        risk   = label_to_risk.get(label, "LOW")

        # Spread records over the last 7 days for chart variety
        created = base_dt + timedelta(
            days=idx % 7,
            hours=random.randint(7, 17),
            minutes=random.randint(0, 59),
        )

        prob = {"LOW": 0.95, "HIGH": 0.70, "CRITICAL": 0.15}.get(risk, 0.80)

        base_t   = _safe_int(row.get("base_tariff", 0))
        actual_t = _safe_int(row.get("actual_tariff", 0))
        gap      = max(0, actual_t - base_t)

        p = Prediction(
            idrg_primary_icd10       = row.get("idrg_primary_icd10", ""),
            inacbg_primary_icd10     = row.get("inacbg_primary_icd10", ""),
            idrg_icd9_procedure      = row.get("idrg_icd9_procedure", ""),
            kelas                    = row.get("kelas", "kelas_3"),
            care_type                = str(row.get("care_type", "")),
            entry_type               = row.get("entry_type", ""),
            ml_prediction            = label,
            confidence_valid         = 0.95 if label == "grouping_valid"    else 0.02,
            confidence_incomplete    = 0.90 if label == "coding_incomplete" else 0.02,
            confidence_invalid       = 0.88 if label == "grouping_invalid"  else 0.02,
            risk_level               = risk,
            base_tariff              = base_t,
            actual_tariff            = actual_t,
            financial_gap            = gap,
            reimbursement_probability= prob,
            primary_action           = action,
            top_shap_feature         = "final_success",
            created_at               = created,
            source                   = "seed",
        )
        db.session.add(p)
        inserted += 1

    db.session.commit()
    return inserted


def get_impact_stats(total_preds: int | None = None, valid_cnt: int | None = None) -> Dict[str, Any]:
    """
    Compute impact metrics for the dashboard: feedback confirmation rate,
    trust score, recent feedback list, and pending review queue.

    Returns a dict that is merged into the /api/v1/stats response.
    All values have safe defaults — never raises on empty DB.
    """
    # ── Feedback aggregates ────────────────────────────────────────────────
    total_fb = PredictionFeedback.query.count()
    confirmed_fb = PredictionFeedback.query.filter(
        PredictionFeedback.is_correct.is_(True)
    ).count()
    confirmation_rate = round(confirmed_fb / total_fb, 4) if total_fb > 0 else 0.0

    # ── avg MDC confidence (confidence_valid = model confidence in grouping) ─
    avg_conf_row = db.session.query(
        db.func.avg(Prediction.confidence_valid)
    ).scalar()
    avg_mdc_confidence = round(float(avg_conf_row), 4) if avg_conf_row is not None else None

    # ── Recent feedback (last 5, most recent first) ────────────────────────
    recent_rows = (
        db.session.query(PredictionFeedback, Prediction)
        .outerjoin(Prediction, PredictionFeedback.prediction_id == Prediction.id)
        .order_by(PredictionFeedback.created_at.desc())
        .limit(5)
        .all()
    )
    recent_feedback = [
        {
            "icd_codes": pred.idrg_primary_icd10 if pred else "—",
            "cbg_prediction": fb.submitted_cbg or "—",
            "confirmed": fb.is_correct,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
        }
        for fb, pred in recent_rows
    ]

    # ── Trust score ────────────────────────────────────────────────────────
    trust_score = None
    trust_breakdown = None
    if total_fb > 0 and avg_mdc_confidence is not None:
        if total_preds is None:
            total_preds = Prediction.query.count()
        if valid_cnt is None:
            valid_cnt = Prediction.query.filter(
                Prediction.ml_prediction == "grouping_valid"
            ).count()
        grouping_valid_ratio = round(valid_cnt / total_preds, 4) if total_preds > 0 else 0.0

        trust_breakdown = {
            "mdc_confidence": avg_mdc_confidence,
            "confirmation_rate": confirmation_rate,
            "grouping_valid": grouping_valid_ratio,
        }
        trust_score = round(
            (avg_mdc_confidence * 0.4 + confirmation_rate * 0.4 + grouping_valid_ratio * 0.2) * 100
        )

    # ── Pending review: predictions with no feedback entry ─────────────────
    reviewed_pred_ids = (
        db.session.query(PredictionFeedback.prediction_id)
        .filter(PredictionFeedback.prediction_id.isnot(None))
    )
    pending_preds = (
        Prediction.query
        .filter(~Prediction.id.in_(reviewed_pred_ids))
        .order_by(Prediction.created_at.desc())
        .limit(10)
        .all()
    )
    conf_col = {
        "grouping_valid":    lambda p: p.confidence_valid,
        "coding_incomplete": lambda p: p.confidence_incomplete,
        "grouping_invalid":  lambda p: p.confidence_invalid,
    }
    pending_review = [
        {
            "id": p.id,
            "icd_codes": p.idrg_primary_icd10 or "—",
            "cbg_prediction": p.ml_prediction or "—",
            "mdc_confidence": conf_col.get(p.ml_prediction, lambda p: p.confidence_valid)(p),
            "risk_level": p.risk_level or "—",
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pending_preds
    ]

    return {
        "feedback_total":             total_fb,
        "feedback_confirmed":         confirmed_fb,
        "feedback_confirmation_rate": confirmation_rate,
        "avg_mdc_confidence":         avg_mdc_confidence,
        "recent_feedback":            recent_feedback,
        "trust_score":                trust_score,
        "trust_score_breakdown":      trust_breakdown,
        "pending_review":             pending_review,
    }


# ── Private helpers ────────────────────────────────────────────────────────────

def _to_int(val) -> int:
    """Safely convert a value to int, returning 0 on failure."""
    try:
        return int(float(val)) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _safe_int(val) -> int:
    """Convert a CSV string field to int, 0 on failure."""
    try:
        return int(float(str(val).replace(",", "").strip()))
    except (ValueError, TypeError):
        return 0


def save_feedback(data: dict):
    """Persist a doctor feedback report for an inaccurate prediction."""
    fb = PredictionFeedback(
        prediction_id = data.get('prediction_id'),
        submitted_cbg = data.get('submitted_cbg', ''),
        correct_cbg   = data.get('correct_cbg', ''),
        is_correct    = data.get('is_correct', False),
        notes         = data.get('notes', ''),
    )
    db.session.add(fb)
    db.session.commit()
    return fb
