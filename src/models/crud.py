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

from src.models.db_models import db, Prediction, SystemStats


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

    confidence     = pred_block.get("confidence", {})
    explanation    = pred_block.get("explanation", [])
    top_shap       = explanation[0].get("feature") if explanation else None

    row = Prediction(
        claim_id                 = req_body.get("claim_id"),
        idrg_primary_icd10       = req_body.get("idrg_primary_icd10"),
        inacbg_primary_icd10     = req_body.get("inacbg_primary_icd10"),
        idrg_icd9_procedure      = req_body.get("idrg_icd9_procedure"),
        kelas                    = req_body.get("kelas"),
        care_type                = req_body.get("care_type"),
        entry_type               = req_body.get("entry_type"),
        ml_prediction            = pred_block.get("prediction"),
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
    risk_dist = {r: c for r, c in risk_counts}

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
    result = []
    for i in range(days - 1, -1, -1):
        d = date.today() - timedelta(days=i)
        day_total = Prediction.query.filter(
            db.func.date(Prediction.created_at) == d
        ).count()
        valid_c = Prediction.query.filter(
            db.func.date(Prediction.created_at) == d,
            Prediction.ml_prediction == "grouping_valid"
        ).count()
        result.append({
            "date":  d.isoformat(),
            "count": day_total,
            "valid": valid_c,
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
