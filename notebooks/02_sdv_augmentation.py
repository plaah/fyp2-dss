"""
Sprint 1 T1.2 — Synthetic Dataset Generation via SDV GaussianCopula
Generates augmented BPJS claim records to reach 10K balanced dataset.

Target distribution:
  grouping_valid:     3,081 real + 3,862 synthetic = 6,943  (~70%)
  coding_incomplete:    225 real + 1,719 synthetic = 1,944  (~20%)
  grouping_invalid:      10 real +   990 synthetic = 1,000  (~10%)
  TOTAL: ~9,887 records
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import os
import sys

from sdv.single_table import GaussianCopulaSynthesizer
from sdv.metadata import SingleTableMetadata

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(BASE_DIR, "data", "tamtech_raw_extract.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "synthetic_bpjs.csv")

# ── Load data ──────────────────────────────────────────────────────────────────
print("=" * 60)
print("Loading data...")
df = pd.read_csv(RAW_PATH)
print(f"  Raw shape: {df.shape}")
print(f"  ml_label distribution:")
print(df["ml_label"].value_counts().to_string(header=False))

# ── Column selection ───────────────────────────────────────────────────────────
# Drop: ID column, high-null columns (>30%), free-text description columns
DROP_COLS = [
    "claim_id",                   # ID — not a feature
    "inacbg_icd10_error",         # 98.8% null
    "final_error_no",             # 93.0% null
    "idrg_primary_icd10_desc",    # free-text description
    "inacbg_primary_icd10_desc",  # free-text description
    "drg_description",            # free-text description
    "inacbg_cbg_desc",            # free-text description
    "final_message",              # free-text description
]

# Also drop ml_label — we split by it and add it back after synthesis
FEATURE_COLS = [c for c in df.columns if c not in DROP_COLS + ["ml_label"]]

print(f"\nFeature columns selected for SDV ({len(FEATURE_COLS)}):")
print(FEATURE_COLS)

# ── Helper: fit GaussianCopula + sample ────────────────────────────────────────

def synthesize_subset(subset_df: pd.DataFrame, label: str, n_generate: int, seed: int = 42) -> pd.DataFrame:
    """Fit GaussianCopulaSynthesizer on subset and generate n_generate rows."""
    print(f"\n[{label}] Fitting on {len(subset_df)} real rows → generating {n_generate} synthetic...")

    data = subset_df[FEATURE_COLS].copy()

    # Build metadata
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(data)

    # Fit synthesizer
    synthesizer = GaussianCopulaSynthesizer(metadata)
    synthesizer.fit(data)

    # Sample
    synthetic = synthesizer.sample(num_rows=n_generate, batch_size=min(500, n_generate))
    synthetic["ml_label"] = label
    synthetic["source"] = "synthetic"

    print(f"  → Generated: {len(synthetic)} rows")
    return synthetic

# ── Split by label ─────────────────────────────────────────────────────────────
np.random.seed(42)

gv_real  = df[df["ml_label"] == "grouping_valid"].copy()
ci_real  = df[df["ml_label"] == "coding_incomplete"].copy()
gi_real  = df[df["ml_label"] == "grouping_invalid"].copy()

print(f"\nReal subset sizes — gv:{len(gv_real)} ci:{len(ci_real)} gi:{len(gi_real)}")

# Tag real records
for subset in [gv_real, ci_real, gi_real]:
    subset["source"] = "real"

# ── Synthesize each class ──────────────────────────────────────────────────────
gv_synth = synthesize_subset(gv_real,  "grouping_valid",    n_generate=3862, seed=42)
ci_synth = synthesize_subset(ci_real,  "coding_incomplete", n_generate=1719, seed=42)
gi_synth = synthesize_subset(gi_real,  "grouping_invalid",  n_generate=990,  seed=42)

# ── Combine real + synthetic ───────────────────────────────────────────────────
print("\nCombining real + synthetic...")

# Align columns across all frames (real frames only have FEATURE_COLS + ml_label + source now)
def align(df_in: pd.DataFrame) -> pd.DataFrame:
    cols = FEATURE_COLS + ["ml_label", "source"]
    return df_in[cols].copy()

combined = pd.concat([
    align(gv_real),
    align(gv_synth),
    align(ci_real),
    align(ci_synth),
    align(gi_real),
    align(gi_synth),
], ignore_index=True)

print(f"  Combined shape: {combined.shape}")

# ── Validate distribution ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("VALIDATION REPORT")
print("=" * 60)

print(f"\nTotal records: {len(combined):,}")

dist = combined.groupby(["ml_label", "source"]).size().unstack(fill_value=0)
print("\nBreakdown by label × source:")
print(dist)

label_counts = combined["ml_label"].value_counts()
label_pct    = (label_counts / len(combined) * 100).round(1)
print("\nLabel distribution:")
for lbl in label_counts.index:
    print(f"  {lbl:<22} {label_counts[lbl]:>5}  ({label_pct[lbl]:.1f}%)")

# Target check
print("\nTarget vs actual:")
targets = {"grouping_valid": 7000, "coding_incomplete": 2000, "grouping_invalid": 1000}
for lbl, tgt in targets.items():
    actual = label_counts.get(lbl, 0)
    delta  = actual - tgt
    status = "OK" if abs(delta) < tgt * 0.10 else "WARNING"
    print(f"  {lbl:<22} target~{tgt:,}  actual={actual:,}  delta={delta:+,}  [{status}]")

print("\nSample rows per label (3 each):")
for lbl in combined["ml_label"].unique():
    print(f"\n  -- {lbl} --")
    sample = combined[combined["ml_label"] == lbl].sample(3, random_state=42)
    print(sample[["gender", "care_type", "ml_label", "source"]].to_string(index=False))

# ── Export ─────────────────────────────────────────────────────────────────────
combined.to_csv(OUT_PATH, index=False)
size_mb = os.path.getsize(OUT_PATH) / (1024 * 1024)
print(f"\nExported: {OUT_PATH}")
print(f"File size: {size_mb:.2f} MB")
print("=" * 60)
print("T1.2 COMPLETE")
