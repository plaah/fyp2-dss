"""
Surrogate INACBG Grouper — Training Pipeline
=============================================
Steps 1–4 of the architecture rebuild:
  Step 1: Extract clinical training dataset from tamtech_raw_extract.csv
  Step 2: Build CBG deterministic lookup table (3-level fallback)
  Step 3: Train Stage 1 — MDC predictor (XGBoost, 20-class)
  Step 4: Train Stage 2 — Severity predictor (XGBoost, 4-class)

Data facts (confirmed by CSV inspection):
  - 3,076 valid records after P-exclusion and X-0-98-X filter
  - 20 MDC classes (A B D E F G H I J K L M N O Q S U V W Z)
  - 4 severity levels: 0 (2122), I (685), II (179), III (91)
  - Tariff is fully deterministic from CBG code + kelas (0 multi-tariff rows)
  - care_type in CSV is int (1=inp, 2=outp, 3=emd), not string
"""

import os, sys, warnings, pickle, json
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.utils import resample
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import (accuracy_score, f1_score,
                              classification_report, confusion_matrix)
import xgboost as xgb

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
DOCS_DIR   = os.path.join(BASE_DIR, "docs")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# care_type int → string mapping (matches API input convention)
CARE_TYPE_MAP = {1: 'inp', 2: 'outp', 3: 'emd'}

# Columns to frequency-encode (high cardinality)
FREQ_COLS = ['idrg_primary_icd10', 'idrg_icd9_procedure',
             'inacbg_primary_icd10', 'icd_block']

# Columns to label-encode (low cardinality)
LABEL_COLS = ['icd_chapter', 'care_type_str', 'entry_type', 'kelas']

FEATURE_COLS = (
    FREQ_COLS +
    LABEL_COLS +
    ['is_z_code', 'is_r_code', 'is_outpatient', 'has_procedure', 'icd_match', 'episodes']
)

print("=" * 65)
print("  SURROGATE INACBG GROUPER — TRAINING PIPELINE")
print("=" * 65)


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — EXTRACT CLINICAL TRAINING DATASET
# ══════════════════════════════════════════════════════════════════════════════
print("\n\n[STEP 1]  Extract clinical training dataset")
print("─" * 65)

raw = pd.read_csv(os.path.join(DATA_DIR, "tamtech_raw_extract.csv"))
print(f"  Raw records loaded: {len(raw)}")

# Filter to clean approved records
valid = raw[
    (raw['ml_label'] == 'grouping_valid') &
    raw['inacbg_cbg_code'].notna() &
    (raw['inacbg_cbg_code'] != '') &
    (raw['inacbg_cbg_code'] != 'X-0-98-X')
].copy()

# Parse CBG components — use split('-').str[-1] to handle II and III correctly
valid['mdc_letter'] = valid['inacbg_cbg_code'].str[0]
valid['severity']   = valid['inacbg_cbg_code'].str.split('-').str[-1]

# Exclude MDC P (only 1 record — insufficient for training)
valid = valid[valid['mdc_letter'] != 'P'].copy()
print(f"  After filter (excl P): {len(valid)} records")

print(f"\n  MDC distribution:")
for letter, cnt in valid['mdc_letter'].value_counts().sort_index().items():
    bar = '█' * min(cnt // 20, 40)
    print(f"    {letter:2s}  {cnt:5d}  {bar}")

print(f"\n  Severity distribution:")
for sev, cnt in valid['severity'].value_counts().sort_index().items():
    print(f"    {sev:3s}  {cnt:5d}")

# ── Map care_type int → string ────────────────────────────────────────────────
valid['care_type_str'] = valid['care_type'].map(CARE_TYPE_MAP).fillna('emd')

# ── Clean string columns ──────────────────────────────────────────────────────
for col in ['idrg_primary_icd10', 'inacbg_primary_icd10']:
    valid[col] = valid[col].astype(str).str.strip().str.upper()
    valid[col] = valid[col].replace({'NAN': np.nan})

for col in ['idrg_icd9_procedure']:
    valid[col] = valid[col].astype(str).str.strip().str.upper()
    valid[col] = valid[col].replace({'NAN': np.nan})

valid['entry_type'] = valid['entry_type'].astype(str).str.strip().str.lower()
valid['kelas']      = valid['kelas'].astype(str).str.strip().str.lower()

# ── Feature engineering ───────────────────────────────────────────────────────
icd = valid['idrg_primary_icd10'].fillna('UNK')

valid['icd_chapter']   = icd.str[0].where(icd.str[0].str.isalpha(), other='X')
valid['icd_block']     = icd.str[:3].where(icd.str[:3] != 'NAN', other='UNK')
valid['is_z_code']     = icd.str.startswith('Z').astype(int)
valid['is_r_code']     = icd.str.startswith('R').astype(int)
valid['is_outpatient'] = (valid['care_type'] == 2).astype(int)
valid['has_procedure'] = valid['idrg_icd9_procedure'].notna().astype(int)
valid['icd_match']     = (
    valid['idrg_primary_icd10'].fillna('') ==
    valid['inacbg_primary_icd10'].fillna('')
).astype(int)
valid['episodes'] = valid['episodes'].clip(upper=10).fillna(1).astype(float)

print(f"\n  Engineered features:")
print(f"    icd_chapter unique: {valid['icd_chapter'].nunique()}")
print(f"    icd_block unique:   {valid['icd_block'].nunique()}")
print(f"    is_outpatient=1:    {valid['is_outpatient'].sum()} ({valid['is_outpatient'].mean()*100:.1f}%)")
print(f"    has_procedure=1:    {valid['has_procedure'].sum()} ({valid['has_procedure'].mean()*100:.1f}%)")
print(f"    icd_match=1:        {valid['icd_match'].sum()} ({valid['icd_match'].mean()*100:.1f}%)")

# Save targets before encoding
valid['target_mdc']      = valid['mdc_letter']
valid['target_severity'] = valid['severity']
valid['target_cbg_code'] = valid['inacbg_cbg_code']
valid['target_tariff']   = valid['base_tariff']

# ── Frequency encoding ────────────────────────────────────────────────────────
freq_maps = {}
for col in FREQ_COLS:
    col_data = valid[col].fillna('__missing__')
    freq_map  = col_data.value_counts(normalize=True).to_dict()
    freq_maps[col] = freq_map
    valid[col] = col_data.map(freq_map).fillna(0.0)

# ── Label encoding ────────────────────────────────────────────────────────────
label_encoders = {}
for col in LABEL_COLS:
    col_data = valid[col].fillna('__missing__').astype(str)
    le = LabelEncoder()
    valid[col] = le.fit_transform(col_data)
    label_encoders[col] = le

# Build feature matrix
X = valid[FEATURE_COLS].copy()
# Final null fill with median
for col in X.columns:
    if X[col].isnull().any():
        X[col] = X[col].fillna(X[col].median())

# Attach targets back for CSV export
out_df = X.copy()
out_df['target_mdc']      = valid['target_mdc'].values
out_df['target_severity'] = valid['target_severity'].values
out_df['target_cbg_code'] = valid['target_cbg_code'].values
out_df['target_tariff']   = valid['target_tariff'].values

out_df.to_csv(os.path.join(DATA_DIR, "clinical_training_data.csv"), index=False)
print(f"\n  Saved: data/clinical_training_data.csv  shape={out_df.shape}")
print(f"  Feature columns ({len(FEATURE_COLS)}): {FEATURE_COLS}")


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — BUILD CBG LOOKUP TABLE
# ══════════════════════════════════════════════════════════════════════════════
print("\n\n[STEP 2]  Build CBG lookup table")
print("─" * 65)

# Work on raw-string version (before encoding) for lookup
raw_valid = raw[
    (raw['ml_label'] == 'grouping_valid') &
    raw['inacbg_cbg_code'].notna() &
    (raw['inacbg_cbg_code'] != '') &
    (raw['inacbg_cbg_code'] != 'X-0-98-X')
].copy()
raw_valid['mdc_letter']   = raw_valid['inacbg_cbg_code'].str[0]
raw_valid['severity']     = raw_valid['inacbg_cbg_code'].str.split('-').str[-1]
raw_valid = raw_valid[raw_valid['mdc_letter'] != 'P'].copy()

raw_valid['care_type_str'] = raw_valid['care_type'].map(CARE_TYPE_MAP).fillna('emd')
for col in ['idrg_primary_icd10']:
    raw_valid[col] = raw_valid[col].astype(str).str.strip().str.upper().replace({'NAN': np.nan})
raw_valid['icd_block'] = raw_valid['idrg_primary_icd10'].fillna('UNK').str[:3]
raw_valid['kelas']     = raw_valid['kelas'].astype(str).str.strip().str.lower()

def _mode_str(s):
    """Most common value in a string series."""
    vc = s.value_counts()
    return vc.index[0] if len(vc) else None

# ── Primary lookup: (icd_block, care_type_str, kelas, severity) ──────────────
primary_lookup = {}
grp_primary = raw_valid.groupby(['icd_block', 'care_type_str', 'kelas', 'severity'])
for (icd_block, ct, kelas, sev), grp in grp_primary:
    cbg_code = _mode_str(grp['inacbg_cbg_code'])
    tariff   = grp['base_tariff'].mode()[0] if len(grp['base_tariff'].mode()) else grp['base_tariff'].median()
    desc     = _mode_str(grp['inacbg_cbg_desc'].fillna(''))
    primary_lookup[(icd_block, ct, kelas, sev)] = {
        'cbg_code':    cbg_code,
        'base_tariff': float(tariff),
        'cbg_desc':    desc or '',
    }

# Coverage check
covered = sum(
    (row['icd_block'], row['care_type_str'], row['kelas'], row['severity']) in primary_lookup
    for _, row in raw_valid.iterrows()
)
coverage_pct = covered / len(raw_valid) * 100
print(f"  Primary lookup entries:  {len(primary_lookup)}")
print(f"  Primary coverage:        {covered}/{len(raw_valid)} = {coverage_pct:.1f}%")

# ── Fallback 1: (mdc_letter, severity, kelas) ─────────────────────────────────
fallback_mdc_sev_kelas = {}
grp_fb1 = raw_valid.groupby(['mdc_letter', 'severity', 'kelas'])
for (mdc, sev, kelas), grp in grp_fb1:
    cbg_code = _mode_str(grp['inacbg_cbg_code'])
    tariff   = grp['base_tariff'].mode()[0] if len(grp['base_tariff'].mode()) else grp['base_tariff'].median()
    desc     = _mode_str(grp['inacbg_cbg_desc'].fillna(''))
    fallback_mdc_sev_kelas[(mdc, sev, kelas)] = {
        'cbg_code': cbg_code, 'base_tariff': float(tariff), 'cbg_desc': desc or ''
    }
print(f"  Fallback-1 entries (mdc+sev+kelas):  {len(fallback_mdc_sev_kelas)}")

# ── Fallback 2: (mdc_letter, severity) ───────────────────────────────────────
fallback_mdc_sev = {}
grp_fb2 = raw_valid.groupby(['mdc_letter', 'severity'])
for (mdc, sev), grp in grp_fb2:
    cbg_code = _mode_str(grp['inacbg_cbg_code'])
    tariff   = grp['base_tariff'].mode()[0] if len(grp['base_tariff'].mode()) else grp['base_tariff'].median()
    desc     = _mode_str(grp['inacbg_cbg_desc'].fillna(''))
    fallback_mdc_sev[(mdc, sev)] = {
        'cbg_code': cbg_code, 'base_tariff': float(tariff), 'cbg_desc': desc or ''
    }
print(f"  Fallback-2 entries (mdc+sev):        {len(fallback_mdc_sev)}")

cbg_lookup_table = {
    'primary':              primary_lookup,
    'fallback_mdc_sev_kelas': fallback_mdc_sev_kelas,
    'fallback_mdc_sev':     fallback_mdc_sev,
}
pickle.dump(cbg_lookup_table,
            open(os.path.join(MODELS_DIR, "cbg_lookup_table.pkl"), "wb"))
print("  Saved: models/cbg_lookup_table.pkl")

# Export human-readable CSV
csv_rows = []
for (icd_block, ct, kelas, sev), v in primary_lookup.items():
    csv_rows.append({
        'icd_block': icd_block, 'care_type': ct, 'kelas': kelas, 'severity': sev,
        'cbg_code': v['cbg_code'], 'base_tariff': v['base_tariff'], 'cbg_desc': v['cbg_desc']
    })
pd.DataFrame(csv_rows).to_csv(
    os.path.join(DATA_DIR, "cbg_lookup_table.csv"), index=False)
print("  Saved: data/cbg_lookup_table.csv")

# Also save preprocessing artifacts used by SurrogateGrouper at inference time
preprocessing_artifacts = {
    'freq_maps':      freq_maps,
    'label_encoders': label_encoders,
    'feature_cols':   FEATURE_COLS,
    'care_type_map':  CARE_TYPE_MAP,
}
pickle.dump(preprocessing_artifacts,
            open(os.path.join(MODELS_DIR, "surrogate_preprocessing.pkl"), "wb"))
print("  Saved: models/surrogate_preprocessing.pkl")


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — EVALUATE AND PRINT METRICS
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_model(name, model, X_test, y_test, le, log_lines):
    y_pred = model.predict(X_test)
    acc  = accuracy_score(y_test, y_pred)
    f1   = f1_score(y_test, y_pred, average='weighted')
    print(f"\n  {name}")
    print(f"  Accuracy:  {acc*100:.2f}%")
    print(f"  F1 (wtd):  {f1:.4f}")
    print(f"\n  Classification report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_, digits=3))
    print(f"  Confusion matrix:\n  {confusion_matrix(y_test, y_pred)}")

    log_lines.append(f"### {name}")
    log_lines.append(f"- Accuracy: {acc*100:.2f}%")
    log_lines.append(f"- Weighted F1: {f1:.4f}")
    log_lines.append("```")
    log_lines.append(classification_report(y_test, y_pred,
                                           target_names=le.classes_, digits=3))
    log_lines.append("```\n")
    return acc, f1


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — TRAIN STAGE 1: MDC PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════
print("\n\n[STEP 3]  Train Stage 1 — MDC Predictor (20-class XGBoost)")
print("─" * 65)

log_lines = ["# Model Retraining Log — Surrogate INACBG Grouper", ""]

y_mdc_raw = valid['target_mdc'].values
mdc_le = LabelEncoder()
y_mdc  = mdc_le.fit_transform(y_mdc_raw)
NUM_MDC = len(mdc_le.classes_)
print(f"  MDC classes ({NUM_MDC}): {list(mdc_le.classes_)}")

# Oversample minority classes (< 15 samples) using sklearn.utils.resample
X_arr = X.values
counts = pd.Series(y_mdc).value_counts()
min_samples = 15
X_os, y_os = X_arr.copy(), y_mdc.copy()
for cls_idx, cnt in counts.items():
    if cnt < min_samples:
        mask = y_mdc == cls_idx
        X_cls = X_arr[mask]
        y_cls = y_mdc[mask]
        X_up  = resample(X_cls, replace=True,
                         n_samples=min_samples - cnt, random_state=42)
        y_up  = np.full(min_samples - cnt, cls_idx)
        X_os  = np.vstack([X_os, X_up])
        y_os  = np.concatenate([y_os, y_up])
        print(f"    Oversampled MDC '{mdc_le.classes_[cls_idx]}': {cnt} → {min_samples}")

X_train_m, X_test_m, y_train_m, y_test_m = train_test_split(
    X_os, y_os, test_size=0.20, random_state=42, stratify=y_os
)
sw_m = compute_sample_weight('balanced', y_train_m)
print(f"  Train: {X_train_m.shape}  |  Test: {X_test_m.shape}")

# Validation split for early stopping
X_tr_m, X_val_m, y_tr_m, y_val_m = train_test_split(
    X_train_m, y_train_m, test_size=0.15, random_state=42, stratify=y_train_m
)
sw_tr_m = compute_sample_weight('balanced', y_tr_m)

mdc_es = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    eval_metric='mlogloss', objective='multi:softprob',
    num_class=NUM_MDC, random_state=42, n_jobs=-1, verbosity=0,
)
mdc_es.fit(X_tr_m, y_tr_m, sample_weight=sw_tr_m,
           eval_set=[(X_val_m, y_val_m)],
           early_stopping_rounds=20, verbose=False)
best_iter = mdc_es.best_iteration + 1
print(f"  Early stopping fired at iteration {best_iter}")

mdc_clf = xgb.XGBClassifier(
    n_estimators=best_iter, max_depth=6, learning_rate=0.1,
    eval_metric='mlogloss', objective='multi:softprob',
    num_class=NUM_MDC, random_state=42, n_jobs=-1, verbosity=0,
)
sw_full_m = compute_sample_weight('balanced', y_train_m)
mdc_clf.fit(X_train_m, y_train_m, sample_weight=sw_full_m, verbose=False)

log_lines += ["## Stage 1 — MDC Predictor", ""]
acc_mdc, f1_mdc = evaluate_model(
    "MDC Predictor (XGBoost)", mdc_clf, X_test_m, y_test_m, mdc_le, log_lines)

# Check success criteria and optionally tune
if acc_mdc < 0.75:
    print(f"\n  Accuracy {acc_mdc*100:.2f}% < 75% — tuning (n_estimators=500, max_depth=8)…")
    log_lines.append("**Triggered tuning: n_estimators=500, max_depth=8**\n")
    mdc_es2 = xgb.XGBClassifier(
        n_estimators=500, max_depth=8, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric='mlogloss', objective='multi:softprob',
        num_class=NUM_MDC, random_state=42, n_jobs=-1, verbosity=0,
    )
    mdc_es2.fit(X_tr_m, y_tr_m, sample_weight=sw_tr_m,
                eval_set=[(X_val_m, y_val_m)],
                early_stopping_rounds=20, verbose=False)
    best_iter2 = mdc_es2.best_iteration + 1
    mdc_tuned = xgb.XGBClassifier(
        n_estimators=best_iter2, max_depth=8, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric='mlogloss', objective='multi:softprob',
        num_class=NUM_MDC, random_state=42, n_jobs=-1, verbosity=0,
    )
    mdc_tuned.fit(X_train_m, y_train_m, sample_weight=sw_full_m, verbose=False)
    log_lines += ["## Stage 1 Tuned", ""]
    acc_t, f1_t = evaluate_model(
        "MDC Predictor (XGBoost tuned)", mdc_tuned, X_test_m, y_test_m, mdc_le, log_lines)
    if f1_t > f1_mdc:
        mdc_clf = mdc_tuned
        acc_mdc, f1_mdc = acc_t, f1_t
        print(f"  Tuned model adopted (F1={f1_mdc:.4f})")

pickle.dump(mdc_clf, open(os.path.join(MODELS_DIR, "mdc_predictor.pkl"), "wb"))
pickle.dump(mdc_le,  open(os.path.join(MODELS_DIR, "mdc_label_encoder.pkl"), "wb"))
with open(os.path.join(MODELS_DIR, "mdc_feature_names.txt"), "w") as f:
    f.write("\n".join(FEATURE_COLS))
print("\n  Saved: models/mdc_predictor.pkl")
print("  Saved: models/mdc_label_encoder.pkl")
print("  Saved: models/mdc_feature_names.txt")


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — TRAIN STAGE 2: SEVERITY PREDICTOR (4-class)
# ══════════════════════════════════════════════════════════════════════════════
print("\n\n[STEP 4]  Train Stage 2 — Severity Predictor (4-class XGBoost)")
print("─" * 65)

y_sev_raw = valid['target_severity'].values
sev_le = LabelEncoder()
y_sev  = sev_le.fit_transform(y_sev_raw)
NUM_SEV = len(sev_le.classes_)
print(f"  Severity classes ({NUM_SEV}): {list(sev_le.classes_)}")
for cls, cnt in zip(sev_le.classes_, np.bincount(y_sev)):
    print(f"    {cls}: {cnt}")

X_train_s, X_test_s, y_train_s, y_test_s = train_test_split(
    X_arr, y_sev, test_size=0.20, random_state=42, stratify=y_sev
)
sw_s = compute_sample_weight('balanced', y_train_s)
print(f"  Train: {X_train_s.shape}  |  Test: {X_test_s.shape}")

X_tr_s, X_val_s, y_tr_s, y_val_s = train_test_split(
    X_train_s, y_train_s, test_size=0.15, random_state=42, stratify=y_train_s
)
sw_tr_s = compute_sample_weight('balanced', y_tr_s)

sev_es = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    eval_metric='mlogloss', objective='multi:softprob',
    num_class=NUM_SEV, random_state=42, n_jobs=-1, verbosity=0,
)
sev_es.fit(X_tr_s, y_tr_s, sample_weight=sw_tr_s,
           eval_set=[(X_val_s, y_val_s)],
           early_stopping_rounds=20, verbose=False)
best_iter_s = sev_es.best_iteration + 1
print(f"  Early stopping fired at iteration {best_iter_s}")

sev_clf = xgb.XGBClassifier(
    n_estimators=best_iter_s, max_depth=6, learning_rate=0.1,
    eval_metric='mlogloss', objective='multi:softprob',
    num_class=NUM_SEV, random_state=42, n_jobs=-1, verbosity=0,
)
sev_clf.fit(X_train_s, y_train_s, sample_weight=sw_s, verbose=False)

log_lines += ["## Stage 2 — Severity Predictor", ""]
acc_sev, f1_sev = evaluate_model(
    "Severity Predictor (XGBoost, 4-class)", sev_clf, X_test_s, y_test_s, sev_le, log_lines)

pickle.dump(sev_clf, open(os.path.join(MODELS_DIR, "severity_predictor.pkl"), "wb"))
pickle.dump(sev_le,  open(os.path.join(MODELS_DIR, "severity_label_encoder.pkl"), "wb"))
with open(os.path.join(MODELS_DIR, "severity_feature_names.txt"), "w") as f:
    f.write("\n".join(FEATURE_COLS))
print("\n  Saved: models/severity_predictor.pkl")
print("  Saved: models/severity_label_encoder.pkl")
print("  Saved: models/severity_feature_names.txt")


# ══════════════════════════════════════════════════════════════════════════════
#  SAVE RETRAINING LOG
# ══════════════════════════════════════════════════════════════════════════════
log_path = os.path.join(DOCS_DIR, "model_retraining_log.md")
with open(log_path, "w") as f:
    f.write("\n".join(log_lines))
print(f"\n  Saved: docs/model_retraining_log.md")


# ══════════════════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("  === SURROGATE GROUPER TRAINING COMPLETE ===")
print("=" * 65)
print(f"  Stage 1 MDC:      Accuracy={acc_mdc*100:.2f}%  |  F1={f1_mdc:.4f}")
print(f"  Stage 2 Severity: Accuracy={acc_sev*100:.2f}%  |  F1={f1_sev:.4f}")
print(f"  Stage 3 Lookup:   Exact coverage={coverage_pct:.1f}%")
print(f"  Training records: {len(valid)}")
print(f"  MDC classes:      {NUM_MDC}")
print(f"  Severity classes: {NUM_SEV}")
print(f"  Feature columns:  {len(FEATURE_COLS)}")

# MDC criteria check
y_pred_mdc = mdc_clf.predict(X_test_m)
report_dict = {}
for i, cls in enumerate(mdc_le.classes_):
    mask = y_test_m == i
    if mask.sum() >= 20:
        recall_cls = (y_pred_mdc[mask] == i).sum() / mask.sum()
        status = '✅' if recall_cls >= 0.70 else '⚠️ '
        report_dict[cls] = recall_cls
        print(f"  MDC {cls} recall: {recall_cls:.2f}  {status}")
print("=" * 65)
