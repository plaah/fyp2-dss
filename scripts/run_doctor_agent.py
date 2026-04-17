#!/usr/bin/env python3
"""
Doctor Testing Agent runner for FYP2 DSS.

Two modes:
  --direct  : runs tests directly in Python (no claude CLI needed)
  (default) : tries claude CLI first, falls back to direct mode

Usage:
    source venv/bin/activate
    python scripts/run_doctor_agent.py           # auto mode
    python scripts/run_doctor_agent.py --direct  # direct mode
"""

import subprocess, sys, os, json, requests
from datetime import datetime
from pathlib import Path

FLASK_URL  = "http://localhost:5001"
AGENT_FILE = Path(__file__).parent.parent / "docs" / "agents" / "doctor_test_agent.md"
REPORT_DIR = Path(__file__).parent.parent / "docs" / "test_reports"

# Each test case pairs a prediction payload with an ICD search check.
# expected_cbg_prefix: first letter of the CBG code — checked against cbg[0]
# expected_risk: list of acceptable risk_level strings (for financial-only cases)
# search_q / search_type / search_expect: paired ICD search check (optional)
TEST_CASES = [
    {
        "name": "Hipertensi rawat jalan",
        "expected_cbg_prefix": "Q",
        "search_q": "hipertensi", "search_type": "diagnosis", "search_expect": "I10",
        "payload": {"primary_icd10":"I10","inacbg_icd10":"I10","icd9_procedure":"89.09",
                    "care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":196100},
    },
    {
        "name": "Pneumonia rawat inap",
        "expected_cbg_prefix": "J",
        "search_q": "pneumonia", "search_type": "diagnosis", "search_expect": "J18",
        "payload": {"primary_icd10":"J18.0","inacbg_icd10":"J18.0","icd9_procedure":"99.21",
                    "care_type":"inp","entry_type":"emd","kelas":"kelas_3","episodes":3,"actual_tariff":3613600},
    },
    {
        "name": "DM tipe 2 neuropati",
        "expected_cbg_prefix": "E",
        "search_q": "dm tipe 2", "search_type": "diagnosis", "search_expect": "E11",
        "payload": {"primary_icd10":"E11.4","inacbg_icd10":"E11.4","icd9_procedure":"89.09",
                    "care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":2,"actual_tariff":3611500},
    },
    {
        "name": "BPH dengan TURP",
        "expected_cbg_prefix": "V",
        "search_q": "prostat", "search_type": "diagnosis", "search_expect": "N40",
        "payload": {"primary_icd10":"N40.1","inacbg_icd10":"N40.1","icd9_procedure":"60.29",
                    "care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":7116300},
    },
    {
        "name": "Stroke iskemik",
        "expected_cbg_prefix": "G",
        "search_q": "stroke", "search_type": "diagnosis", "search_expect": "I6",
        "payload": {"primary_icd10":"I63.9","inacbg_icd10":"I63.9","icd9_procedure":"93.39",
                    "care_type":"inp","entry_type":"emd","kelas":"kelas_3","episodes":5,"actual_tariff":5484100},
    },
    {
        "name": "ISPA rawat jalan",
        "expected_cbg_prefix": "Q",
        "search_q": "ispa", "search_type": "diagnosis", "search_expect": None,
        "payload": {"primary_icd10":"J06.9","inacbg_icd10":"J06.9","icd9_procedure":"89.09",
                    "care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":150900},
    },
    {
        "name": "Tarif melebihi plafon",
        "expected_risk": ["MEDIUM", "HIGH"],
        "payload": {"primary_icd10":"I10","inacbg_icd10":"I10","icd9_procedure":"89.09",
                    "care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":500000},
    },
    {
        "name": "Katarak operasi",
        "expected_cbg_prefix": "H",
        "search_q": "katarak", "search_type": "diagnosis", "search_expect": "H25",
        "payload": {"primary_icd10":"H25.9","inacbg_icd10":"H25.9","icd9_procedure":"13.19",
                    "care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":3638300},
    },
]

# Standalone ICD search tests (not paired with a prediction case)
SEARCH_CASES = [
    ("nebulisasi", "procedure", None),
]


def check_flask():
    try:
        r = requests.get(f"{FLASK_URL}/api/v1/health", timeout=3)
        return r.status_code == 200
    except:
        return False


def eval_cbg(cbg, expected_prefix):
    """
    PASS  — CBG first letter matches expected MDC prefix.
    WARN  — CBG exists but wrong MDC, AND wrong letter is Q or Z
            (known INA-CBGs misc/fallback groups — not a hard failure).
    FAIL  — CBG null, empty, or wrong MDC with a non-Q/Z letter.
    """
    if not cbg:
        return "FAIL"
    if cbg[0] == expected_prefix:
        return "PASS"
    if cbg[0] in ("Q", "Z"):
        return "WARN"
    return "FAIL"


def run_direct():
    p = w = f = 0
    lines = [
        "=== DOCTOR TEST AGENT REPORT ===",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "Tester: Dr. Budi Santoso (simulated — direct mode)",
        f"System: FYP2 DSS {FLASK_URL}", "",
        "TEST RESULTS:",
    ]

    for case in TEST_CASES:
        try:
            r = requests.post(f"{FLASK_URL}/api/v1/full-assessment",
                              json=case["payload"], timeout=10)
            if r.status_code != 200:
                status, detail = "FAIL", f"HTTP {r.status_code}"
                f += 1
            else:
                d    = r.json()
                pred = d.get("prediction", {})
                fin  = d.get("financial", {})
                cbg    = pred.get("predicted_cbg_code", "")
                tariff = pred.get("predicted_base_tariff", 0)
                risk   = fin.get("risk_level", "")
                gap    = fin.get("financial_gap", 0)
                conf   = pred.get("mdc_confidence", 0)

                if "expected_cbg_prefix" in case:
                    status = eval_cbg(cbg, case["expected_cbg_prefix"])
                    detail = f"CBG={cbg or 'NULL'} | Tariff=Rp{tariff:,.0f} | conf={conf*100:.0f}%"
                else:
                    if risk in case.get("expected_risk", []):
                        status = "PASS"
                    elif risk:
                        status = "WARN"
                    else:
                        status = "FAIL"
                    detail = f"Risk={risk or 'NULL'} | Gap=Rp{abs(gap):,.0f}"

                if status == "PASS": p += 1
                elif status == "WARN": w += 1
                else: f += 1

        except Exception as e:
            status, detail = "FAIL", f"Error: {str(e)[:40]}"
            f += 1

        line = f"  {case['name']:<30} [{status}] | {detail}"
        lines.append(line)
        print(line)

    # ICD search tests — paired + standalone
    lines += ["", "ICD SEARCH TESTS:"]
    search_tests = []
    for case in TEST_CASES:
        if case.get("search_q"):
            search_tests.append((case["search_q"], case["search_type"], case.get("search_expect")))
    search_tests += SEARCH_CASES

    for q, stype, exp in search_tests:
        try:
            r = requests.get(f"{FLASK_URL}/api/v1/icd-search",
                             params={"q": q, "type": stype, "limit": 5}, timeout=5)
            results = r.json().get("results", [])
            if not results:
                status, top = "FAIL", "no results"; f += 1
            else:
                top = results[0]["code"]
                if exp and top.startswith(exp):
                    status = "PASS"; p += 1
                elif exp:
                    status = "WARN"; w += 1
                else:
                    status = "PASS"; p += 1
        except Exception as e:
            status, top = "FAIL", str(e)[:25]; f += 1

        line = f"  Search '{q:<16}' [{status}] | Top: {top}"
        lines.append(line)
        print(line)

    total = p + w + f
    if f == 0 and w <= 2:
        verdict = "✅ READY FOR DEMO"
    elif f == 0:
        verdict = "⚠️  MOSTLY WORKING — review warnings before demo"
    elif f <= 3:
        verdict = "🔧 NEEDS FIXES — see failed cases above"
    else:
        verdict = "🚨 CRITICAL ISSUES — multiple failures, do not demo yet"

    lines += [
        "",
        "SUMMARY:",
        f"  PASS:  {p}/{total}",
        f"  WARN:  {w}/{total}",
        f"  FAIL:  {f}/{total}",
        "",
        f"VERDICT: {verdict}",
        "===",
    ]

    print("\n")
    for l in lines:
        print(l)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"doctor_agent_{ts}.md"
    out.write_text("\n".join(lines))
    print(f"\nReport saved: {out}")
    return f == 0


def run_via_claude():
    if not AGENT_FILE.exists():
        return None
    prompt = AGENT_FILE.read_text()
    prompt += (
        f"\n\nIMPORTANT: Actually call the API at {FLASK_URL} using Python requests."
        f"\nRun ALL test cases and report ACTUAL response values."
        f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    )
    try:
        result = subprocess.run(["claude", "-p", prompt],
                                capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(result.stdout)
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            out = REPORT_DIR / f"doctor_agent_claude_{ts}.md"
            out.write_text(result.stdout)
            print(f"\nReport saved: {out}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


if __name__ == "__main__":
    print("=" * 55)
    print("  FYP2 DSS — Doctor Testing Agent")
    print("  Dr. Budi Santoso (GP, Indonesia)")
    print("=" * 55)

    if not check_flask():
        print(f"❌ Flask not running at {FLASK_URL}")
        print("   Run: python app.py")
        sys.exit(1)
    print(f"✅ Flask running at {FLASK_URL}\n")

    ok = None
    if "--direct" not in sys.argv:
        ok = run_via_claude()
    if ok is None:
        ok = run_direct()

    sys.exit(0 if ok else 1)
