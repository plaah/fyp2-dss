"""
T2.2 — Predictor Service
Loads best_model.pkl + preprocessing.pkl at startup.
Provides preprocess_input() and predict() for the Flask API.
"""

import os
import pickle
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ── Lazy-loaded singletons ─────────────────────────────────────────────────────
_model         = None
_preprocessing = None
_label_enc     = None


def _load_artifacts():
    global _model, _preprocessing, _label_enc
    if _model is not None:
        return
    _model         = pickle.load(open(os.path.join(MODELS_DIR, "best_model.pkl"), "rb"))
    _preprocessing = pickle.load(open(os.path.join(MODELS_DIR, "preprocessing.pkl"), "rb"))
    _label_enc     = pickle.load(open(os.path.join(MODELS_DIR, "label_encoder.pkl"), "rb"))


def get_model_name() -> str:
    _load_artifacts()
    return _preprocessing.get("best_model_name", "XGBoost")


def get_classes() -> list:
    _load_artifacts()
    return list(_preprocessing["classes"])


def is_loaded() -> bool:
    return _model is not None


def get_label_encoder():
    _load_artifacts()
    return _label_enc


# ── Feature ordering ───────────────────────────────────────────────────────────
_FEATURE_ORDER = None


def _to_bool_int(val) -> int:
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        return int(bool(val))
    if isinstance(val, str):
        return 1 if val.lower() in ("true", "1", "yes") else 0
    return 0


def preprocess_input(raw: dict) -> np.ndarray:
    """
    Transform a raw API JSON dict into a feature array ready for model.predict().
    Applies the same encoding logic used in pipeline.py.
    Returns np.ndarray shape (1, n_features).
    """
    _load_artifacts()
    global _FEATURE_ORDER
    if _FEATURE_ORDER is None:
        _FEATURE_ORDER = _preprocessing["feature_names"]

    le_map    = _preprocessing["label_encoders"]
    freq_maps = _preprocessing["freq_maps"]
    medians   = _preprocessing["numeric_medians"]
    care_map  = _preprocessing.get("care_type_map", {})

    row = {}

    # care_type: accept string ("outp") or int (2)
    ct_raw = raw.get("care_type", 2)
    if isinstance(ct_raw, str):
        row["care_type"] = care_map.get(ct_raw.lower(), 2)
    else:
        try:
            row["care_type"] = int(ct_raw)
        except (ValueError, TypeError):
            row["care_type"] = 2

    # Simple numeric fields
    simple_numeric = [
        "tariff_class", "discharge_status", "icu_indikator", "episodes",
        "idrg_icd9_procedure", "inacbg_icd10_validity",
        "mdc_number", "drg_code", "base_tariff", "actual_tariff",
    ]
    for col in simple_numeric:
        val = raw.get(col)
        if val is None:
            row[col] = medians.get(col, 0.0)
        else:
            try:
                row[col] = float(val)
            except (ValueError, TypeError):
                row[col] = medians.get(col, 0.0)

    # idrg_icd10_valid — nominally binary but stored as float
    val = raw.get("idrg_icd10_valid", 1)
    try:
        row["idrg_icd10_valid"] = float(val)
    except (ValueError, TypeError):
        row["idrg_icd10_valid"] = medians.get("idrg_icd10_valid", 1.0)

    # Boolean columns
    for col in ["idrg_grouping_success", "inacbg_grouping_success"]:
        row[col] = _to_bool_int(raw.get(col, True))

    # Derived: final_success = idrg AND inacbg both succeeded
    row["final_success"] = int(
        row["idrg_grouping_success"] == 1 and row["inacbg_grouping_success"] == 1
    )

    # Low-cardinality → LabelEncoder
    lc_defaults = {
        "gender":           "male",
        "claim_status":     "success",
        "claim_month_year": "2025-10",
        "kelas":            "kelas_3",
        "idrg_icd9_valid":  "1",
    }
    for col, default in lc_defaults.items():
        le = le_map.get(col)
        if le is None:
            row[col] = 0
            continue
        raw_val = str(raw.get(col, default)).strip().lower()
        if raw_val in le.classes_:
            row[col] = int(le.transform([raw_val])[0])
        elif "__missing__" in le.classes_:
            row[col] = int(le.transform(["__missing__"])[0])
        else:
            row[col] = 0

    # High-cardinality → frequency encoding
    hc_defaults = {
        "idrg_primary_icd10":  "",
        "inacbg_primary_icd10": "",
        "inacbg_cbg_code":     "",
        "claim_stage":         "final-claim",
        "entry_type":          "outp",
    }
    for col, default in hc_defaults.items():
        fmap    = freq_maps.get(col, {})
        raw_val = str(raw.get(col, default)).strip().upper()
        row[col] = fmap.get(raw_val, 0.0)

    # Engineered features
    idrg_icd   = str(raw.get("idrg_primary_icd10", "")).strip().upper()
    inacbg_icd = str(raw.get("inacbg_primary_icd10", "")).strip().upper()
    row["icd_match"] = int(idrg_icd == inacbg_icd and idrg_icd != "")

    base   = row.get("base_tariff", 0.0)
    actual = row.get("actual_tariff", 0.0)
    row["tariff_ratio"] = round(actual / base, 4) if base > 0 else 1.0

    icd9 = raw.get("idrg_icd9_procedure")
    row["has_procedure"] = 0 if (
        icd9 is None or str(icd9).strip() in ("", "nan", "None")
    ) else 1

    # Assemble in model's expected feature order
    feature_vec = np.array(
        [row.get(col, medians.get(col, 0.0)) for col in _FEATURE_ORDER],
        dtype=np.float64,
    ).reshape(1, -1)

    return feature_vec


def predict(raw: dict) -> dict:
    """
    Full prediction pipeline.
    Returns dict with prediction, confidence per class, model name, and raw feature array.
    """
    _load_artifacts()
    features    = preprocess_input(raw)
    classes     = _label_enc.classes_
    y_pred_enc  = _model.predict(features)[0]
    y_prob      = _model.predict_proba(features)[0]
    prediction  = _label_enc.inverse_transform([y_pred_enc])[0]
    confidence  = {cls: round(float(prob), 4) for cls, prob in zip(classes, y_prob)}

    return {
        "prediction": prediction,
        "confidence": confidence,
        "model_used": get_model_name(),
        "features":   features,      # passed to explainer
    }
