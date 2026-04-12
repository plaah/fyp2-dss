"""
Surrogate Grouper Status Checker
=================================
Verifies that all required model artifacts exist and that the API
endpoints are responding correctly.

Usage:
    python scripts/surrogate_grouper_status.py [--port 5001]
"""

import argparse
import json
import os
import sys

import urllib.request
import urllib.error

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = {
    "MDC predictor model":        "models/mdc_predictor.pkl",
    "MDC label encoder":          "models/mdc_label_encoder.pkl",
    "MDC feature names":          "models/mdc_feature_names.txt",
    "Severity predictor model":   "models/severity_predictor.pkl",
    "Severity label encoder":     "models/severity_label_encoder.pkl",
    "Severity feature names":     "models/severity_feature_names.txt",
    "CBG lookup table":           "models/cbg_lookup_table.pkl",
    "Clinical training data":     "data/clinical_training_data.csv",
    "CBG lookup CSV":             "data/cbg_lookup_table.csv",
    "Model retraining log":       "docs/model_retraining_log.md",
}

ENDPOINTS = [
    ("GET",  "/api/v1/health",          None),
    ("POST", "/api/v1/predict",         {
        "primary_icd10": "I10",
        "care_type":     "outp",
        "entry_type":    "gp",
        "kelas":         "kelas_3",
        "episodes":      1,
    }),
    ("POST", "/api/v1/full-assessment", {
        "primary_icd10":  "I10",
        "care_type":      "outp",
        "entry_type":     "gp",
        "kelas":          "kelas_3",
        "episodes":       1,
        "actual_tariff":  196100,
    }),
    ("GET",  "/api/v1/stats",           None),
]


def check_files() -> int:
    """Check that all required model/data files exist."""
    print("\n── Model & Data Artifacts ─────────────────────────────────────────")
    failures = 0
    for label, rel_path in REQUIRED_FILES.items():
        full = os.path.join(BASE_DIR, rel_path)
        exists = os.path.isfile(full)
        size_kb = round(os.path.getsize(full) / 1024, 1) if exists else None
        status = f"✅  ({size_kb} KB)" if exists else "❌  MISSING"
        print(f"  {status:<20} {label:<30} {rel_path}")
        if not exists:
            failures += 1
    return failures


def check_endpoints(base_url: str) -> int:
    """Hit each API endpoint and report status."""
    print(f"\n── API Endpoints ({base_url}) ──────────────────────────────────────")
    failures = 0
    for method, path, body in ENDPOINTS:
        url = base_url + path
        try:
            if body:
                data = json.dumps(body).encode()
                req = urllib.request.Request(url, data=data,
                                             headers={"Content-Type": "application/json"},
                                             method=method)
            else:
                req = urllib.request.Request(url, method=method)

            with urllib.request.urlopen(req, timeout=5) as resp:
                code = resp.getcode()
                payload = json.loads(resp.read().decode())
                status_val = payload.get("status", "—")
                print(f"  ✅  {code}  {method:<5} {path:<35} status={status_val}")
        except urllib.error.HTTPError as e:
            print(f"  ❌  {e.code}  {method:<5} {path:<35} HTTPError")
            failures += 1
        except Exception as e:
            print(f"  ❌  ERR  {method:<5} {path:<35} {e}")
            failures += 1
    return failures


def check_model_metrics() -> None:
    """Print training metrics from the retraining log."""
    log_path = os.path.join(BASE_DIR, "docs/model_retraining_log.md")
    if not os.path.isfile(log_path):
        print("\n  ⚠️  model_retraining_log.md not found — run training script first.")
        return
    print("\n── Model Metrics (from retraining log) ─────────────────────────────")
    with open(log_path) as f:
        for line in f:
            if any(kw in line for kw in ("Accuracy", "F1", "Coverage", "Stage", "Records")):
                print(f"  {line.rstrip()}")


def main():
    parser = argparse.ArgumentParser(description="Surrogate Grouper status checker")
    parser.add_argument("--port", type=int, default=5001, help="Flask server port (default: 5001)")
    parser.add_argument("--no-api", action="store_true", help="Skip API endpoint checks")
    args = parser.parse_args()

    print("=" * 70)
    print("  SURROGATE INACBG GROUPER — STATUS CHECK")
    print("=" * 70)

    file_failures = check_files()
    check_model_metrics()

    api_failures = 0
    if not args.no_api:
        base_url = f"http://localhost:{args.port}"
        api_failures = check_endpoints(base_url)
    else:
        print("\n  (API check skipped — use without --no-api to check endpoints)")

    total_failures = file_failures + api_failures
    print("\n" + "=" * 70)
    if total_failures == 0:
        print("  ✅  ALL CHECKS PASSED — Surrogate Grouper is operational.")
    else:
        print(f"  ❌  {total_failures} check(s) FAILED — review output above.")
    print("=" * 70)
    sys.exit(0 if total_failures == 0 else 1)


if __name__ == "__main__":
    main()
