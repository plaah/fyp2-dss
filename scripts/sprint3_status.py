"""
Sprint 3 Status Checker
========================
Verifies that all T3.1-T3.3 deliverables exist and that the new API
endpoints are reachable. Prints a status table: DONE / MISSING per component.

Usage:
    python scripts/sprint3_status.py
    python scripts/sprint3_status.py --port 5001   # custom port
"""

import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── File deliverables ──────────────────────────────────────────────────────────
FILE_CHECKS = [
    ("T3.1 FinancialEstimator module",  "src/services/financial_estimator.py"),
    ("T3.2 RecommendationEngine module", "src/services/recommender.py"),
    ("T3.1 FinancialEstimator tests",   "tests/test_financial_estimator.py"),
    ("T3.2 RecommendationEngine tests", "tests/test_recommender.py"),
    ("T3.3 Thesis Chapter 5 draft",     "docs/thesis_chapter5_draft.md"),
]

# ── Endpoint checks ────────────────────────────────────────────────────────────
ENDPOINT_CHECKS = [
    ("/api/v1/financial-impact", "POST"),
    ("/api/v1/recommend",        "POST"),
    ("/api/v1/full-assessment",  "POST"),
]

# Minimal valid payloads per endpoint
PAYLOADS = {
    "/api/v1/financial-impact": {
        "prediction_result": {"prediction": "grouping_valid", "confidence": {"grouping_valid": 0.9}},
        "base_tariff": 196100, "actual_tariff": 196100, "kelas": "kelas_3",
    },
    "/api/v1/recommend": {
        "prediction_result": {"prediction": "grouping_valid", "confidence": {"grouping_valid": 0.9}},
        "financial_result":  {"risk_level": "LOW", "reimbursement_amount": 196100,
                               "financial_gap": 0, "gap_percentage": 0,
                               "estimated_loss_idr": 0, "cash_flow_risk_days": 0,
                               "reimbursement_probability": 0.95},
        "explanation": [{"feature": "final_success", "impact": 5.0, "direction": "positive"}],
    },
    "/api/v1/full-assessment": {
        "gender": "male", "care_type": "outp", "idrg_primary_icd10": "I10",
        "inacbg_primary_icd10": "I10", "base_tariff": 196100, "actual_tariff": 196100,
        "idrg_grouping_success": True, "inacbg_grouping_success": True,
        "kelas": "kelas_3", "claim_stage": "final-claim", "episodes": 1,
    },
}


def check_files() -> list:
    results = []
    for label, rel_path in FILE_CHECKS:
        full_path = os.path.join(BASE_DIR, rel_path)
        exists    = os.path.isfile(full_path)
        size      = f"{os.path.getsize(full_path):,} bytes" if exists else "—"
        results.append((label, "✅ DONE" if exists else "❌ MISSING", size))
    return results


def check_endpoints(port: int) -> list:
    import urllib.request
    import urllib.error
    import json

    base_url = f"http://localhost:{port}"
    results  = []

    for path, method in ENDPOINT_CHECKS:
        url     = base_url + path
        payload = json.dumps(PAYLOADS.get(path, {})).encode("utf-8")
        req     = urllib.request.Request(
            url, data=payload, method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body   = json.loads(resp.read())
                status = body.get("status", "?")
                label  = f"✅ DONE ({status})"
        except urllib.error.HTTPError as e:
            label = f"⚠️  HTTP {e.code}"
        except Exception as e:
            label = f"❌ UNREACHABLE ({type(e).__name__})"
        results.append((f"{method} {path}", label))

    return results


def print_table(title: str, rows: list, cols: tuple):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")
    col_w = [max(len(str(r[i])) for r in rows + [cols]) + 2 for i in range(len(cols))]
    header = "  ".join(str(c).ljust(w) for c, w in zip(cols, col_w))
    print(f"  {header}")
    print(f"  {'—' * (sum(col_w) + 2 * len(col_w))}")
    for row in rows:
        line = "  ".join(str(c).ljust(w) for c, w in zip(row, col_w))
        print(f"  {line}")
    print(f"{'─'*60}")


def main():
    parser = argparse.ArgumentParser(description="Sprint 3 status checker")
    parser.add_argument("--port", type=int, default=5001,
                        help="Flask server port to check endpoints against (default: 5001)")
    args = parser.parse_args()

    print("\n========================================")
    print("  SPRINT 3 STATUS CHECK")
    print("========================================")

    # File checks
    file_results = check_files()
    print_table("FILE DELIVERABLES", file_results, ("Component", "Status", "Size"))

    done_count   = sum(1 for _, s, _ in file_results if "DONE" in s)
    total_count  = len(file_results)
    print(f"\n  Files: {done_count}/{total_count} DONE")

    # Endpoint checks
    print(f"\n  Checking endpoints on localhost:{args.port} …")
    ep_results = check_endpoints(args.port)
    print_table("API ENDPOINTS", ep_results, ("Endpoint", "Status"))

    ep_done = sum(1 for _, s in ep_results if "DONE" in s)
    print(f"\n  Endpoints: {ep_done}/{len(ep_results)} reachable")

    # Unit test count
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--tb=no", "-q"],
            capture_output=True, text=True, cwd=BASE_DIR
        )
        summary = [l for l in result.stdout.strip().splitlines() if "passed" in l or "failed" in l]
        test_summary = summary[-1] if summary else "could not determine"
    except Exception as e:
        test_summary = f"error: {e}"

    print(f"\n  Unit tests: {test_summary}")

    # Word count of thesis chapter
    thesis_path = os.path.join(BASE_DIR, "docs", "thesis_chapter5_draft.md")
    if os.path.isfile(thesis_path):
        with open(thesis_path) as f:
            words = len(f.read().split())
        print(f"  Thesis Ch.5 word count: {words:,} words")
    else:
        print("  Thesis Ch.5: ❌ NOT FOUND")

    print("\n========================================\n")


if __name__ == "__main__":
    main()
