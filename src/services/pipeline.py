"""
T1.3 — Data Pipeline & Derived Label Module
Loads synthetic_bpjs.csv, cleans, encodes, engineers features,
stratified 80/20 splits, saves train/test CSVs.
"""

import os
import warnings
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

SRC_PATH    = os.path.join(DATA_DIR, "synthetic_bpjs.csv")
X_TRAIN_OUT = os.path.join(DATA_DIR, "X_train.csv")
X_TEST_OUT  = os.path.join(DATA_DIR, "X_test.csv")
Y_TRAIN_OUT = os.path.join(DATA_DIR, "y_train.csv")
Y_TEST_OUT  = os.path.join(DATA_DIR, "y_test.csv")

# ── Column taxonomy ────────────────────────────────────────────────────────────
# Columns dropped before any processing
DROP_COLS = ["source"]                    # leakage — not a feature

# Columns that are genuinely low-cardinality categoricals → LabelEncoder
LOW_CARD_CATS = [
    "gender",
    "claim_status",
    "claim_month_year",
    "kelas",
    "idrg_icd9_valid",   # real values: '0'/'1'/NaN; synthetic may add slight noise
]

# High-cardinality string columns → frequency encoding
HIGH_CARD_CATS = [
    "idrg_primary_icd10",
    "inacbg_primary_icd10",
    "inacbg_cbg_code",
    "claim_stage",    # synthetic artifact inflated cardinality to ~999
    "entry_type",     # synthetic artifact inflated cardinality to ~998
]

# idrg_icd10_valid: nominally binary but GaussianCopula generated float strings
# → coerce to float directly (numeric treatment)
COERCE_NUMERIC = ["idrg_icd10_valid"]

# Boolean cols → int (0/1)
BOOL_COLS = ["idrg_grouping_success", "inacbg_grouping_success", "final_success"]

# Target
TARGET = "ml_label"


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(src_path: str = SRC_PATH, random_state: int = 42) -> dict:
    """
    Full pipeline: load → clean → engineer → encode → split → save.
    Returns a summary dict with shapes and label distributions.
    """
    print("=" * 60)
    print("T1.3  DATA PIPELINE")
    print("=" * 60)

    # Step 1 — Load
    df = _load(src_path)

    # Step 2 — Clean & validate
    df = _clean(df)

    # Step 3 — Feature engineering (before encoding so ICD strings are intact)
    df = _engineer_features(df)

    # Step 4 — Encode
    df = _encode(df)

    # Step 5 — Final type coercion + null fill
    df = _finalise(df)

    # Step 6 — Split
    X_train, X_test, y_train, y_test = _split(df, random_state=random_state)

    # Step 7 — Save
    _save(X_train, X_test, y_train, y_test)

    # Step 8 — Preview
    summary = _report(X_train, X_test, y_train, y_test)

    return summary


# ══════════════════════════════════════════════════════════════════════════════
#  PIPELINE STEPS
# ══════════════════════════════════════════════════════════════════════════════

def _load(src_path: str) -> pd.DataFrame:
    print(f"\n[1] Loading {src_path} …")
    df = pd.read_csv(src_path)
    print(f"    Shape: {df.shape}")
    df = df.drop(columns=DROP_COLS, errors="ignore")
    return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[2] Cleaning & validating …")

    # Booleans → int
    for col in BOOL_COLS:
        if col in df.columns:
            df[col] = df[col].astype(int)

    # Coerce nominally-numeric-but-stored-as-string columns
    for col in COERCE_NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalise low-card categoricals: strip, lowercase
    for col in LOW_CARD_CATS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()
            df[col] = df[col].replace({"nan": np.nan})

    # Normalise high-card string cols: strip, upper (ICD style)
    for col in HIGH_CARD_CATS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
            df[col] = df[col].replace({"NAN": np.nan})

    # Clip numeric columns that should be non-negative
    for col in ["base_tariff", "actual_tariff", "episodes", "mdc_number",
                "drg_code", "inacbg_icd10_validity", "idrg_icd9_procedure"]:
        if col in df.columns:
            df[col] = df[col].clip(lower=0)

    # Validate label integrity
    valid_labels = {"grouping_valid", "coding_incomplete", "grouping_invalid"}
    bad = ~df[TARGET].isin(valid_labels)
    if bad.any():
        print(f"    WARNING: {bad.sum()} rows with unexpected ml_label — dropping")
        df = df[~bad].copy()

    null_counts = df.isnull().sum()
    high_null = null_counts[null_counts / len(df) > 0.30]
    if not high_null.empty:
        print(f"    WARNING: columns still >30% null after clean: {high_null.index.tolist()}")

    print(f"    Shape after clean: {df.shape}")
    return df


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[3] Engineering features …")

    # icd_match: True if iDRG primary ICD-10 == INACBG primary ICD-10
    if "idrg_primary_icd10" in df.columns and "inacbg_primary_icd10" in df.columns:
        idrg  = df["idrg_primary_icd10"].astype(str).str.strip().str.upper()
        inacbg = df["inacbg_primary_icd10"].astype(str).str.strip().str.upper()
        df["icd_match"] = (idrg == inacbg).astype(int)
        print(f"    icd_match distribution: {df['icd_match'].value_counts().to_dict()}")

    # tariff_ratio: actual_tariff / base_tariff (claims overage / underpayment signal)
    if "actual_tariff" in df.columns and "base_tariff" in df.columns:
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = df["actual_tariff"] / df["base_tariff"]
        ratio = ratio.replace([np.inf, -np.inf], np.nan).fillna(1.0)
        df["tariff_ratio"] = ratio.round(4)
        print(f"    tariff_ratio — mean={df['tariff_ratio'].mean():.3f}  "
              f"min={df['tariff_ratio'].min():.3f}  max={df['tariff_ratio'].max():.3f}")

    # has_procedure: whether an ICD-9 procedure code was recorded
    if "idrg_icd9_procedure" in df.columns:
        df["has_procedure"] = df["idrg_icd9_procedure"].notna().astype(int)
        print(f"    has_procedure distribution: {df['has_procedure'].value_counts().to_dict()}")

    return df


def _encode(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[4] Encoding categoricals …")

    # — Low-cardinality → LabelEncoder (fit on full data; no leakage risk here
    #   since these are structural categoricals, not target-derived)
    le = LabelEncoder()
    for col in LOW_CARD_CATS:
        if col not in df.columns:
            continue
        # fill NaN with sentinel before encoding
        df[col] = df[col].fillna("__missing__")
        df[col] = le.fit_transform(df[col])
        print(f"    LabelEncoded: {col}")

    # — High-cardinality → frequency encoding
    #   (maps each category to its proportion in the full dataset)
    for col in HIGH_CARD_CATS:
        if col not in df.columns:
            continue
        freq_map = df[col].value_counts(normalize=True)
        df[col] = df[col].map(freq_map).fillna(0.0)
        print(f"    FreqEncoded:  {col}")

    return df


def _finalise(df: pd.DataFrame) -> pd.DataFrame:
    """Fill remaining nulls: median for numeric, 0 for boolean-like."""
    print("\n[5] Finalising — filling nulls …")

    label_col = df[TARGET].copy()
    X = df.drop(columns=[TARGET])

    numeric_cols = X.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        n_null = X[col].isnull().sum()
        if n_null > 0:
            median_val = X[col].median()
            X[col] = X[col].fillna(median_val)

    # Confirm no remaining nulls
    remaining = X.isnull().sum().sum()
    if remaining > 0:
        print(f"    WARNING: {remaining} nulls still present after fill")
    else:
        print(f"    All nulls resolved. Feature matrix shape: {X.shape}")

    df = pd.concat([X, label_col], axis=1)
    return df


def _split(df: pd.DataFrame, random_state: int = 42):
    print("\n[6] Stratified 80/20 train-test split …")

    X = df.drop(columns=[TARGET])
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,
        random_state=random_state,
        stratify=y,
    )

    print(f"    Train: {X_train.shape}  |  Test: {X_test.shape}")
    print(f"    Train label dist: {y_train.value_counts().to_dict()}")
    print(f"    Test  label dist: {y_test.value_counts().to_dict()}")

    return X_train, X_test, y_train, y_test


def _save(X_train, X_test, y_train, y_test):
    print("\n[7] Saving split files …")
    X_train.to_csv(X_TRAIN_OUT, index=False)
    X_test.to_csv(X_TEST_OUT,  index=False)
    y_train.to_csv(Y_TRAIN_OUT, index=False)
    y_test.to_csv(Y_TEST_OUT,  index=False)
    for path, obj in [(X_TRAIN_OUT, X_train), (X_TEST_OUT, X_test),
                      (Y_TRAIN_OUT, y_train), (Y_TEST_OUT, y_test)]:
        size_kb = os.path.getsize(path) / 1024
        print(f"    {os.path.basename(path):<20} {obj.shape}  {size_kb:.1f} KB")


def _report(X_train, X_test, y_train, y_test) -> dict:
    print("\n[8] Feature importance preview (Random Forest proxy) …")

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder as LE

    le = LE()
    y_enc = le.fit_transform(y_train)

    rf = RandomForestClassifier(n_estimators=50, max_depth=6,
                                random_state=42, n_jobs=-1)
    rf.fit(X_train, y_enc)

    importances = pd.Series(rf.feature_importances_, index=X_train.columns)
    top10 = importances.sort_values(ascending=False).head(10)

    print("\n    Top-10 features (RF importance):")
    for feat, score in top10.items():
        bar = "█" * int(score * 200)
        print(f"    {feat:<28} {score:.4f}  {bar}")

    print("\n" + "=" * 60)
    print("T1.3 COMPLETE")
    print("=" * 60)

    return {
        "total": len(X_train) + len(X_test),
        "n_features": X_train.shape[1],
        "train_shape": X_train.shape,
        "test_shape": X_test.shape,
        "top_features": top10.to_dict(),
    }


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_pipeline()
