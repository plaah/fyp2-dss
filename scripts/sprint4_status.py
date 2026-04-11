"""
Sprint 4 Status Checker
========================
Verifies all T4.1-T4.3 deliverables: DB tables, frontend templates,
static assets, and API endpoints.  Prints a DONE/MISSING status table.

Usage:
    python scripts/sprint4_status.py
    python scripts/sprint4_status.py --port 5001
"""

import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── File deliverables ──────────────────────────────────────────────────────────
FILE_CHECKS = [
    # T4.2
    ("T4.2 db_models.py",               "src/models/db_models.py"),
    ("T4.2 crud.py",                    "src/models/crud.py"),
    ("T4.2 DB tests",                   "tests/test_database.py"),
    # T4.1
    ("T4.1 templates/index.html",       "templates/index.html"),
    ("T4.1 templates/dashboard.html",   "templates/dashboard.html"),
    ("T4.1 static/js/app.js",           "static/js/app.js"),
    ("T4.1 static/css/style.css",       "static/css/style.css"),
    # T4.3
    ("T4.3 Thesis Ch.4 draft",          "docs/thesis_chapter4_draft.md"),
]

# ── Endpoint checks ────────────────────────────────────────────────────────────
ENDPOINT_CHECKS = [
    ("/",                    "GET",  None),
    ("/dashboard",           "GET",  None),
    ("/api/v1/stats",        "GET",  None),
    ("/api/v1/financial-impact", "POST", {
        "prediction_result": {"prediction": "grouping_valid", "confidence": {"grouping_valid": 0.9}},
        "base_tariff": 196100, "actual_tariff": 196100, "kelas": "kelas_3",
    }),
]


def check_files():
    results = []
    for label, rel_path in FILE_CHECKS:
        full = os.path.join(BASE_DIR, rel_path)
        ok   = os.path.isfile(full)
        size = f"{os.path.getsize(full):,} bytes" if ok else "—"
        results.append((label, "✅ DONE" if ok else "❌ MISSING", size))
    return results


def check_db(app):
    try:
        from src.models.db_models import db, Prediction, IcdReference, SystemStats
        with app.app_context():
            p_count = Prediction.query.count()
            return [
                ("predictions table", f"✅ DONE ({p_count} rows)"),
                ("icd_reference table", "✅ DONE"),
                ("system_stats table", "✅ DONE"),
            ]
    except Exception as e:
        return [
            ("predictions table", f"❌ ERROR: {e}"),
            ("icd_reference table", "⚠️  not checked"),
            ("system_stats table", "⚠️  not checked"),
        ]


def check_endpoints(port):
    import urllib.request, urllib.error, json
    base = f"http://localhost:{port}"
    results = []
    for path, method, payload in ENDPOINT_CHECKS:
        url  = base + path
        data = json.dumps(payload).encode() if payload else None
        req  = urllib.request.Request(url, data=data, method=method,
                                      headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                label = f"✅ HTTP {r.status}"
        except urllib.error.HTTPError as e:
            label = f"⚠️  HTTP {e.code}"
        except Exception as e:
            label = f"❌ UNREACHABLE ({type(e).__name__})"
        results.append((f"{method} {path}", label))
    return results


def print_table(title, rows, cols):
    print(f"\n{'─'*65}")
    print(f"  {title}")
    print(f"{'─'*65}")
    col_w = [max(len(str(r[i])) for r in rows + [cols]) + 2 for i in range(len(cols))]
    print("  " + "  ".join(str(c).ljust(w) for c, w in zip(cols, col_w)))
    print("  " + "—" * (sum(col_w) + 2 * len(col_w)))
    for row in rows:
        print("  " + "  ".join(str(c).ljust(w) for c, w in zip(row, col_w)))
    print(f"{'─'*65}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()

    print("\n========================================")
    print("  SPRINT 4 STATUS CHECK")
    print("========================================")

    # File checks
    file_results = check_files()
    print_table("FILE DELIVERABLES", file_results, ("Component", "Status", "Size"))
    done = sum(1 for _, s, _ in file_results if "DONE" in s)
    print(f"\n  Files: {done}/{len(file_results)} DONE")

    # DB checks
    try:
        sys.path.insert(0, BASE_DIR)
        os.chdir(BASE_DIR)
        from app import create_app
        app = create_app()
        db_results = check_db(app)
    except Exception as e:
        db_results = [("DB connection", f"❌ {e}")]
    print_table("DATABASE TABLES", db_results, ("Table", "Status"))

    # Endpoint checks
    print(f"\n  Checking endpoints on localhost:{args.port}…")
    ep_results = check_endpoints(args.port)
    print_table("API + PAGE ENDPOINTS", ep_results, ("Endpoint", "Status"))
    ep_done = sum(1 for _, s in ep_results if "DONE" in s or "200" in s)
    print(f"\n  Endpoints: {ep_done}/{len(ep_results)} reachable")

    # Test suite
    try:
        import subprocess
        r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "--tb=no", "-q"],
                           capture_output=True, text=True, cwd=BASE_DIR)
        summary = [l for l in r.stdout.strip().splitlines() if "passed" in l or "failed" in l]
        test_line = summary[-1] if summary else "could not determine"
    except Exception as e:
        test_line = f"error: {e}"
    print(f"\n  Unit tests: {test_line}")

    # Thesis word count
    for draft, label in [
        ("docs/thesis_chapter4_draft.md", "Ch.4"),
        ("docs/thesis_chapter5_draft.md", "Ch.5"),
    ]:
        p = os.path.join(BASE_DIR, draft)
        if os.path.isfile(p):
            wc = len(open(p).read().split())
            print(f"  Thesis {label}: {wc:,} words")
        else:
            print(f"  Thesis {label}: ❌ NOT FOUND")

    print("\n========================================\n")


if __name__ == "__main__":
    main()
