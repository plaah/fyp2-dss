"""
UC014 — Automated Model Retraining Pipeline
===========================================
Loads raw training data, queries the database for doctor feedback,
merges feedback into the training set, runs Optuna hyperparameter tuning,
evaluates the model, saves new artifacts, and triggers atomic swap.
"""

import os
import sys
import pickle
import json
import logging
import warnings
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.utils import resample
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import accuracy_score, f1_score, classification_report
import xgboost as xgb

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

CARE_TYPE_MAP = {1: 'inp', 2: 'outp', 3: 'emd'}
CARE_TYPE_STR_MAP = {'inp': 1, 'outp': 2, 'emd': 3, 'gp': 2}

FREQ_COLS = ['idrg_primary_icd10', 'idrg_icd9_procedure', 'inacbg_primary_icd10', 'icd_block']
LABEL_COLS = ['icd_chapter', 'care_type_str', 'entry_type', 'kelas']
FEATURE_COLS = FREQ_COLS + LABEL_COLS + [
    'is_z_code', 'is_r_code', 'is_outpatient', 'has_procedure', 'icd_match', 'episodes'
]

# Known invalid primary diagnoses (BPJS rules)
KNOWN_INVALID_PRIMARY = {
    "T78.4", "T78.40", "T78.9", "R69", "V99", "W19", "X59", "Y84", "Y99", "U07.1", "U07.2", "U09.9", "Z03.8", "Z04.9", "Z09", "Z54.9", "Z03.9"
}

def get_feedback_rows() -> list[dict]:
    """Query PredictionFeedback table and construct raw-format dictionary rows."""
    from src.models.db_models import db, PredictionFeedback, Prediction
    
    feedbacks = PredictionFeedback.query.filter_by(is_correct=False).all()
    rows = []
    
    for fb in feedbacks:
        if not fb.prediction_id:
            continue
        pred = db.session.get(Prediction, fb.prediction_id)
        if not pred:
            continue
            
        care_type_val = CARE_TYPE_STR_MAP.get(pred.care_type, 2)
        
        # Build raw row dict matching tamtech_raw_extract.csv structure
        row = {
            "claim_id": pred.claim_id or f"fb-{fb.id}",
            "gender": "L",
            "claim_status": "waiting",
            "claim_stage": "idrg",
            "claim_month_year": pred.created_at.strftime("%Y-%m") if pred.created_at else "2026-06",
            "care_type": care_type_val,
            "tariff_class": "3",
            "entry_type": pred.entry_type or "outp",
            "discharge_status": "1",
            "icu_indikator": "0",
            "episodes": 1.0,
            "idrg_primary_icd10": pred.idrg_primary_icd10,
            "idrg_primary_icd10_desc": "",
            "idrg_icd10_valid": "1",
            "idrg_icd9_procedure": pred.idrg_icd9_procedure or "",
            "idrg_icd9_valid": "1" if pred.idrg_icd9_procedure else "0",
            "inacbg_primary_icd10": pred.inacbg_primary_icd10 or pred.idrg_primary_icd10,
            "inacbg_primary_icd10_desc": "",
            "inacbg_icd10_validity": "1",
            "inacbg_icd10_error": "",
            "mdc_number": "",
            "drg_code": "",
            "drg_description": "",
            "idrg_grouping_success": True,
            "inacbg_cbg_code": fb.correct_cbg,
            "inacbg_cbg_desc": "",
            "base_tariff": float(pred.base_tariff) if pred.base_tariff else 0.0,
            "actual_tariff": float(pred.actual_tariff) if pred.actual_tariff else 0.0,
            "kelas": pred.kelas or "kelas_3",
            "inacbg_grouping_success": True,
            "final_success": True,
            "final_message": "",
            "final_error_no": "",
            "ml_label": "grouping_valid" # to pass filters
        }
        rows.append(row)
        
    return rows

def notify_admins(status: str, message: str, metrics: dict = None):
    """Log retrain status and send mock email notification to admins."""
    metrics_str = f" | Metrics: {json.dumps(metrics)}" if metrics else ""
    log_msg = f"[RETRAIN NOTIFICATION] Status: {status} | Message: {message}{metrics_str}"
    logger.info(log_msg)
    
    # Mock Email Send
    print("\n" + "="*80)
    print(f"📧 [EMAIL SENT] To: admin@hospital.go.id, casemix-lead@hospital.go.id")
    print(f"📧 Subject: [FYP2 DSS] Model Retraining Notification - {status}")
    print(f"📧 Body: {message}")
    if metrics:
        print(f"📧 Details:")
        print(f"   - MDC Accuracy: {metrics.get('mdc_accuracy', 0.0)*100:.2f}% (F1: {metrics.get('mdc_f1', 0.0):.4f})")
        print(f"   - Severity Accuracy: {metrics.get('severity_accuracy', 0.0)*100:.2f}% (F1: {metrics.get('severity_f1', 0.0):.4f})")
        print(f"   - CBG Lookup Coverage: {metrics.get('cbg_coverage', 0.0):.2f}%")
        print(f"   - Training Records: {metrics.get('training_records', 0)}")
    print("="*80 + "\n")

def execute_retraining(n_trials: int = 10) -> dict:
    """
    Run the full model retraining pipeline:
    1. Load raw data + database feedbacks.
    2. Build deterministic lookup table.
    3. Train XGBoost MDC + Severity models (with Optuna search).
    4. Save models, write retraining log.
    5. Trigger atomic swap in the running SurrogateGrouper.
    """
    logger.info("Retraining: starting pipeline execution...")
    t_start = datetime.now()
    
    # Load raw data
    raw_path = os.path.join(DATA_DIR, "tamtech_raw_extract.csv")
    if not os.path.exists(raw_path):
        err = f"Raw training file missing: {raw_path}"
        notify_admins("FAILED", err)
        return {"status": "error", "message": err}
        
    raw = pd.read_csv(raw_path)
    
    # Load database feedback rows
    fb_rows = get_feedback_rows()
    logger.info(f"Retraining: loaded {len(fb_rows)} feedback rows from database.")
    
    # Append feedbacks to raw
    if fb_rows:
        fb_df = pd.DataFrame(fb_rows)
        raw = pd.concat([raw, fb_df], ignore_index=True)
        
    # Clean approved records
    valid = raw[
        (raw['ml_label'] == 'grouping_valid') &
        raw['inacbg_cbg_code'].notna() &
        (raw['inacbg_cbg_code'] != '') &
        (raw['inacbg_cbg_code'] != 'X-0-98-X')
    ].copy()
    
    # Exclude neonatal / insufficient samples
    valid['mdc_letter'] = valid['inacbg_cbg_code'].str[0]
    valid['severity']   = valid['inacbg_cbg_code'].str.split('-').str[-1]
    valid = valid[valid['mdc_letter'] != 'P'].copy()
    
    if len(valid) < 100:
        err = f"Insufficient records for retraining: {len(valid)}"
        notify_admins("FAILED", err)
        return {"status": "error", "message": err}
        
    # Preprocess fields
    valid['care_type_str'] = valid['care_type'].map(CARE_TYPE_MAP).fillna('emd')
    for col in ['idrg_primary_icd10', 'inacbg_primary_icd10', 'idrg_icd9_procedure']:
        valid[col] = valid[col].astype(str).str.strip().str.upper().replace({'NAN': np.nan, 'NONE': np.nan})
        
    valid['entry_type'] = valid['entry_type'].astype(str).str.strip().str.lower()
    valid['kelas']      = valid['kelas'].astype(str).str.strip().str.lower()
    
    # Features
    icd = valid['idrg_primary_icd10'].fillna('UNK')
    valid['icd_chapter']   = icd.str[0].where(icd.str[0].str.isalpha(), other='X')
    valid['icd_block']     = icd.str[:3].where(icd.str[:3] != 'NAN', other='UNK')
    valid['is_z_code']     = icd.str.startswith('Z').astype(int)
    valid['is_r_code']     = icd.str.startswith('R').astype(int)
    valid['is_outpatient'] = (valid['care_type'] == 2).astype(int)
    valid['has_procedure'] = valid['idrg_icd9_procedure'].notna().astype(int)
    valid['icd_match']     = (
        valid['idrg_primary_icd10'].fillna('') == valid['inacbg_primary_icd10'].fillna('')
    ).astype(int)
    valid['episodes'] = valid['episodes'].clip(upper=10).fillna(1).astype(float)
    
    # Save targets
    valid['target_mdc']      = valid['mdc_letter']
    valid['target_severity'] = valid['severity']
    valid['target_cbg_code'] = valid['inacbg_cbg_code']
    valid['target_tariff']   = valid['base_tariff']
    
    # Freq encoding
    freq_maps = {}
    for col in FREQ_COLS:
        col_data = valid[col].fillna('__missing__')
        freq_map = col_data.value_counts(normalize=True).to_dict()
        freq_maps[col] = freq_map
        valid[col] = col_data.map(freq_map).fillna(0.0)
        
    # Label encoding
    label_encoders = {}
    for col in LABEL_COLS:
        col_data = valid[col].fillna('__missing__').astype(str)
        le = LabelEncoder()
        valid[col] = le.fit_transform(col_data)
        label_encoders[col] = le
        
    X = valid[FEATURE_COLS].copy()
    for col in X.columns:
        if X[col].isnull().any():
            X[col] = X[col].fillna(X[col].median())
            
    # Save clinical training data
    out_df = X.copy()
    out_df['target_mdc']      = valid['target_mdc'].values
    out_df['target_severity'] = valid['target_severity'].values
    out_df['target_cbg_code'] = valid['target_cbg_code'].values
    out_df['target_tariff']   = valid['target_tariff'].values
    out_df.to_csv(os.path.join(DATA_DIR, "clinical_training_data.csv"), index=False)
    
    # ── CBG Lookup Table ──
    primary_lookup = {}
    grp_primary = valid.groupby(['icd_block', 'care_type_str', 'kelas', 'severity'])
    
    def _mode_str(s):
        vc = s.value_counts()
        return vc.index[0] if len(vc) else None
        
    for (icd_b, ct, kl, sev), grp in grp_primary:
        cbg_code = _mode_str(grp['target_cbg_code'])
        # mode tariff or median
        mode_tariff_arr = grp['target_tariff'].mode()
        tariff = mode_tariff_arr[0] if len(mode_tariff_arr) else grp['target_tariff'].median()
        primary_lookup[(icd_b, ct, kl, sev)] = {
            'cbg_code': cbg_code,
            'base_tariff': float(tariff),
            'cbg_desc': ''
        }
        
    # Fallbacks
    fallback_mdc_sev_kelas = {}
    grp_fb1 = valid.groupby(['mdc_letter', 'severity', 'kelas'])
    for (mdc, sev, kl), grp in grp_fb1:
        cbg_code = _mode_str(grp['target_cbg_code'])
        mode_tariff_arr = grp['target_tariff'].mode()
        tariff = mode_tariff_arr[0] if len(mode_tariff_arr) else grp['target_tariff'].median()
        fallback_mdc_sev_kelas[(mdc, sev, kl)] = {
            'cbg_code': cbg_code, 'base_tariff': float(tariff), 'cbg_desc': ''
        }
        
    fallback_mdc_sev = {}
    grp_fb2 = valid.groupby(['mdc_letter', 'severity'])
    for (mdc, sev), grp in grp_fb2:
        cbg_code = _mode_str(grp['target_cbg_code'])
        mode_tariff_arr = grp['target_tariff'].mode()
        tariff = mode_tariff_arr[0] if len(mode_tariff_arr) else grp['target_tariff'].median()
        fallback_mdc_sev[(mdc, sev)] = {
            'cbg_code': cbg_code, 'base_tariff': float(tariff), 'cbg_desc': ''
        }
        
    cbg_lookup_table = {
        'primary': primary_lookup,
        'fallback_mdc_sev_kelas': fallback_mdc_sev_kelas,
        'fallback_mdc_sev': fallback_mdc_sev,
    }
    pickle.dump(cbg_lookup_table, open(os.path.join(MODELS_DIR, "cbg_lookup_table.pkl"), "wb"))
    
    # Save preprocessing
    preprocessing_artifacts = {
        'freq_maps': freq_maps,
        'label_encoders': label_encoders,
        'feature_cols': FEATURE_COLS,
        'care_type_map': CARE_TYPE_MAP,
    }
    pickle.dump(preprocessing_artifacts, open(os.path.join(MODELS_DIR, "surrogate_preprocessing.pkl"), "wb"))
    
    # ── MDC Model ──
    y_mdc_raw = valid['target_mdc'].values
    mdc_le = LabelEncoder()
    y_mdc = mdc_le.fit_transform(y_mdc_raw)
    NUM_MDC = len(mdc_le.classes_)
    
    # Oversample minority classes
    X_arr = X.values
    counts = pd.Series(y_mdc).value_counts()
    min_samples = 30
    X_os, y_os = X_arr.copy(), y_mdc.copy()
    for cls_idx, cnt in counts.items():
        if cnt < min_samples:
            mask = y_mdc == cls_idx
            X_cls = X_arr[mask]
            y_cls = y_mdc[mask]
            X_up = resample(X_cls, replace=True, n_samples=min_samples - cnt, random_state=42)
            y_up = np.full(min_samples - cnt, cls_idx)
            X_os = np.vstack([X_os, X_up])
            y_os = np.concatenate([y_os, y_up])
            
    X_train_m, X_test_m, y_train_m, y_test_m = train_test_split(
        X_os, y_os, test_size=0.20, random_state=42, stratify=y_os
    )
    sw_m = compute_sample_weight('balanced', y_train_m)
    
    X_tr_m, X_val_m, y_tr_m, y_val_m = train_test_split(
        X_train_m, y_train_m, test_size=0.15, random_state=42, stratify=y_train_m
    )
    sw_tr_m = compute_sample_weight('balanced', y_tr_m)
    
    # Optuna Search
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    def _mdc_objective(trial):
        params = dict(
            n_estimators=trial.suggest_int('n_estimators', 100, 300),
            max_depth=trial.suggest_int('max_depth', 4, 8),
            learning_rate=trial.suggest_float('learning_rate', 0.05, 0.25, log=True),
            subsample=trial.suggest_float('subsample', 0.7, 1.0),
            colsample_bytree=trial.suggest_float('colsample_bytree', 0.7, 1.0),
            objective='multi:softprob',
            eval_metric='mlogloss',
            num_class=NUM_MDC,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )
        clf = xgb.XGBClassifier(**params)
        clf.fit(X_tr_m, y_tr_m, sample_weight=sw_tr_m,
                eval_set=[(X_val_m, y_val_m)],
                early_stopping_rounds=15, verbose=False)
        preds = clf.predict(X_val_m)
        return accuracy_score(y_val_m, preds)
        
    study = optuna.create_study(direction='maximize')
    study.optimize(_mdc_objective, n_trials=n_trials)
    best_params = study.best_params
    best_params.update(dict(objective='multi:softprob', eval_metric='mlogloss',
                             num_class=NUM_MDC, random_state=42, n_jobs=-1, verbosity=0))
                             
    mdc_clf = xgb.XGBClassifier(**best_params)
    mdc_clf.fit(X_train_m, y_train_m, sample_weight=sw_m, verbose=False)
    
    y_pred_m = mdc_clf.predict(X_test_m)
    acc_mdc = accuracy_score(y_test_m, y_pred_m)
    f1_mdc = f1_score(y_test_m, y_pred_m, average='weighted')
    
    pickle.dump(mdc_clf, open(os.path.join(MODELS_DIR, "mdc_predictor.pkl"), "wb"))
    pickle.dump(mdc_le, open(os.path.join(MODELS_DIR, "mdc_label_encoder.pkl"), "wb"))
    
    # ── Severity Model ──
    y_sev_raw = valid['target_severity'].values
    sev_le = LabelEncoder()
    y_sev = sev_le.fit_transform(y_sev_raw)
    NUM_SEV = len(sev_le.classes_)
    
    X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(
        X_arr, y_sev, test_size=0.20, random_state=42, stratify=y_sev
    )
    sw_s = compute_sample_weight('balanced', y_train_s)
    
    X_tr_s, X_val_s, y_tr_s, y_val_s = train_test_split(
        X_train_s, y_train_s, test_size=0.15, random_state=42, stratify=y_train_s
    )
    sw_tr_s = compute_sample_weight('balanced', y_tr_s)
    
    sev_clf = xgb.XGBClassifier(
        n_estimators=150, max_depth=5, learning_rate=0.1,
        eval_metric='mlogloss', objective='multi:softprob',
        num_class=NUM_SEV, random_state=42, n_jobs=-1, verbosity=0
    )
    sev_clf.fit(X_train_s, y_train_s, sample_weight=sw_s, verbose=False)
    
    y_pred_s = sev_clf.predict(X_test_s)
    acc_sev = accuracy_score(y_test_s, y_pred_s)
    f1_sev = f1_score(y_test_s, y_pred_s, average='weighted')
    
    pickle.dump(sev_clf, open(os.path.join(MODELS_DIR, "severity_predictor.pkl"), "wb"))
    pickle.dump(sev_le, open(os.path.join(MODELS_DIR, "severity_label_encoder.pkl"), "wb"))
    
    # Write retraining log
    log_lines = [
        f"# Model Retraining Log — Surrogate INACBG Grouper",
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Training records count: {len(valid)}",
        "",
        "## Stage 1 — MDC Predictor",
        f"- Accuracy: {acc_mdc*100:.2f}%",
        f"- Weighted F1: {f1_mdc:.4f}",
        "```",
        classification_report(y_test_m, y_pred_m, target_names=mdc_le.classes_, digits=3),
        "```",
        "",
        "## Stage 2 — Severity Predictor",
        f"- Accuracy: {acc_sev*100:.2f}%",
        f"- Weighted F1: {f1_sev:.4f}",
        "```",
        classification_report(y_test_s, y_pred_s, target_names=sev_le.classes_, digits=3),
        "```"
    ]
    with open(os.path.join(DOCS_DIR, "model_retraining_log.md"), "w") as f:
        f.write("\n".join(log_lines))
        
    metrics = {
        "mdc_accuracy": float(acc_mdc),
        "mdc_f1": float(f1_mdc),
        "severity_accuracy": float(acc_sev),
        "severity_f1": float(f1_sev),
        "cbg_coverage": float(len(primary_lookup) / len(valid) * 100),
        "training_records": len(valid)
    }
    
    # ── Atomic Swap ──
    try:
        from src.api.routes import _grouper
        _grouper.reload()
        logger.info("Retraining: atomic reload succeeded in live server.")
    except Exception as exc:
        logger.warning(f"Retraining: live reload not completed (app context not active?): {exc}")
        
    elapsed = (datetime.now() - t_start).total_seconds()
    msg = f"Model retraining completed successfully in {elapsed:.1f} seconds."
    notify_admins("SUCCESS", msg, metrics)
    
    return {
        "status": "success",
        "message": msg,
        "metrics": metrics
    }
