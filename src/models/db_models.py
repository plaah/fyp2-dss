"""
Database Models — SQLAlchemy ORM
==================================
Defines the three tables used by the DSS:

  predictions   — full audit trail of every /full-assessment API call
  icd_reference — ICD-10/ICD-9 code lookup for autocomplete and validation
  system_stats  — pre-aggregated daily metrics for dashboard chart performance

Design decisions:
  - predictions.source anticipates future Neurovi HIS integration
  - system_stats pre-computes aggregates so the dashboard does not run
    expensive GROUP BY queries on every page load
  - IcdReference uses a unique index on code to enable O(1) lookups

All models are registered on the shared `db` instance imported from here.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Prediction(db.Model):
    """
    Stores every /full-assessment API call result for audit trail and analytics.

    Each row captures the input claim parameters, ML prediction outcome,
    financial risk assessment, and the top SHAP feature — enough to reconstruct
    the full decision context without re-running the model.
    """
    __tablename__ = 'predictions'

    id                       = db.Column(db.Integer, primary_key=True)
    claim_id                 = db.Column(db.String(50))           # future Neurovi encounter ID
    idrg_primary_icd10       = db.Column(db.String(20))
    inacbg_primary_icd10     = db.Column(db.String(20))
    idrg_icd9_procedure      = db.Column(db.String(20))
    kelas                    = db.Column(db.String(10))
    care_type                = db.Column(db.String(20))
    entry_type               = db.Column(db.String(20))
    ml_prediction            = db.Column(db.String(30))           # grouping_valid / coding_incomplete / grouping_invalid
    confidence_valid         = db.Column(db.Float)
    confidence_incomplete    = db.Column(db.Float)
    confidence_invalid       = db.Column(db.Float)
    risk_level               = db.Column(db.String(10))           # LOW / MEDIUM / HIGH / CRITICAL
    base_tariff              = db.Column(db.BigInteger)
    actual_tariff            = db.Column(db.BigInteger)
    financial_gap            = db.Column(db.BigInteger)
    reimbursement_probability= db.Column(db.Float)
    primary_action           = db.Column(db.String(30))           # SUBMIT / RECODE / COMPLETE_CODING / REVIEW
    top_shap_feature         = db.Column(db.String(50))
    created_at               = db.Column(db.DateTime, default=datetime.utcnow)
    source                   = db.Column(db.String(20), default='manual')  # manual / neurovi

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of this prediction."""
        return {
            "id":                        self.id,
            "claim_id":                  self.claim_id,
            "idrg_primary_icd10":        self.idrg_primary_icd10,
            "inacbg_primary_icd10":      self.inacbg_primary_icd10,
            "idrg_icd9_procedure":       self.idrg_icd9_procedure,
            "kelas":                     self.kelas,
            "care_type":                 self.care_type,
            "entry_type":                self.entry_type,
            "ml_prediction":             self.ml_prediction,
            "confidence_valid":          self.confidence_valid,
            "confidence_incomplete":     self.confidence_incomplete,
            "confidence_invalid":        self.confidence_invalid,
            "risk_level":                self.risk_level,
            "base_tariff":               self.base_tariff,
            "actual_tariff":             self.actual_tariff,
            "financial_gap":             self.financial_gap,
            "reimbursement_probability": self.reimbursement_probability,
            "primary_action":            self.primary_action,
            "top_shap_feature":          self.top_shap_feature,
            "created_at":                self.created_at.isoformat() if self.created_at else None,
            "source":                    self.source,
        }


class IcdReference(db.Model):
    """
    ICD-10 and ICD-9-CM code reference table.

    Used for form autocomplete, code validation, and coding tips lookup.
    Seeded from data/icd10_2010_reference.csv and data/icd9_cm_procedures.csv.
    """
    __tablename__ = 'icd_reference'

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(300))
    category    = db.Column(db.String(10))    # 'icd10' or 'icd9'
    mdc_group   = db.Column(db.String(10))    # MDC number if known


class SystemStats(db.Model):
    """
    Daily pre-aggregated statistics for dashboard chart performance.

    Pre-computing daily aggregates avoids running expensive GROUP BY queries
    against the predictions table on every dashboard page load.
    Updated nightly by a background job (Sprint 5).
    """
    __tablename__ = 'system_stats'

    id                          = db.Column(db.Integer, primary_key=True)
    stat_date                   = db.Column(db.Date, nullable=False)
    total_predictions           = db.Column(db.Integer, default=0)
    grouping_valid_count        = db.Column(db.Integer, default=0)
    coding_incomplete_count     = db.Column(db.Integer, default=0)
    grouping_invalid_count      = db.Column(db.Integer, default=0)
    avg_reimbursement_probability = db.Column(db.Float)
    total_financial_gap_idr     = db.Column(db.BigInteger, default=0)
    top_icd10_code              = db.Column(db.String(20))
