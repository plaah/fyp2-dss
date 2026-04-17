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

FLASK_URL   = "http://localhost:5001"
AGENT_FILE  = Path("docs/agents/doctor_test_agent.md")
REPORT_DIR  = Path("docs/test_reports")

TEST_CASES = [
    {"name": "Hipertensi rawat jalan",  "expect_mdc": "Q",
     "payload": {"primary_icd10":"I10","inacbg_icd10":"I10","icd9_procedure":"89.09","care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":196100}},
    {"name": "Pneumonia rawat inap",    "expect_mdc": "J",
     "payload": {"primary_icd10":"J18.0","inacbg_icd10":"J18.0","icd9_procedure":"99.21","care_type":"inp","entry_type":"emd","kelas":"kelas_3","episodes":3,"actual_tariff":3613600}},
    {"name": "DM tipe 2 neuropati",     "expect_mdc": "E",
     "payload": {"primary_icd10":"E11.4","inacbg_icd10":"E11.4","icd9_procedure":"89.09","care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":2,"actual_tariff":3611500}},
    {"name": "BPH dengan TURP",         "expect_mdc": "V",
     "payload": {"primary_icd10":"N40.1","inacbg_icd10":"N40.1","icd9_procedure":"60.29","care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":7116300}},
    {"name": "Stroke iskemik",          "expect_mdc": "G",
     "payload": {"primary_icd10":"I63.9","inacbg_icd10":"I63.9","icd9_procedure":"93.39","care_type":"inp","entry_type":"emd","kelas":"kelas_3","episodes":5,"actual_tariff":5484100}},
    {"name": "ISPA rawat jalan",        "expect_mdc": "Q",
     "payload": {"primary_icd10":"J06.9","inacbg_icd10":"J06.9","icd9_procedure":"89.09","care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":150900}},
    {"name": "Tarif melebihi plafon",   "expect_risk": ["MEDIUM","HIGH"],
     "payload": {"primary_icd10":"I10","inacbg_icd10":"I10","icd9_procedure":"89.09","care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":500000}},
    {"name": "Katarak operasi",         "expect_mdc": "H",
     "payload": {"primary_icd10":"H25.9","inacbg_icd10":"H25.9","icd9_procedure":"13.19","care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":3638300}},
]

SEARCH_CASES = [
    ("hipertensi", "diagnosis", "I10"),
    ("pneumonia",  "diagnosis", "J18"),
    ("dm tipe 2",  "diagnosis", "E11"),
    ("nebulisasi", "procedure", None),
    ("stroke",     "diagnosis", "I6"),
]

def check_flask():
    try:
        r = requests.get(f"{FLASK_URL}/api/v1/health", timeout=3)
        return r.status_code == 200
    except:
        return False

def run_direct():
    p = w = f = 0
    lines = [
        "=== DOCTOR TEST AGENT REPORT ===",
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "Tester: Dr. Budi Santoso (simulated — direct mode)",
        f"System: {FLASK_URL}", "",
        "PREDICTION TESTS:"
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
                cbg  = pred.get("predicted_cbg_code", "")
                tariff  = pred.get("predicted_base_tariff", 0)
                risk    = fin.get("risk_level", "")
                gap     = fin.get("financial_gap", 0)
                mdc_c   = pred.get("mdc_confidence", 0)

                if "expect_mdc" in case:
                    if cbg and cbg[0] == case["expect_mdc"]:
                        status = "PASS"; p += 1
                    elif cbg:
                        status = "WARN"; w += 1
                    else:
                        status = "FAIL"; f += 1
                    detail = f"CBG={cbg or 'NULL'} Tariff=Rp{tariff:,.0f} MDC_conf={mdc_c*100:.0f}%"
                else:
                    if risk in case.get("expect_risk", []):
                        status = "PASS"; p += 1
                    elif risk:
                        status = "WARN"; w += 1
                    else:
                        status = "FAIL"; f += 1
                    detail = f"Risk={risk or 'NULL'} Gap=Rp{abs(gap):,.0f}"
        except Exception as e:
            status, detail = "FAIL", str(e)[:40]
            f += 1

        line = f"  {case['name']:<28} [{status}] {detail}"
        lines.append(line); print(line)

    lines += ["", "ICD SEARCH TESTS:"]
    for q, stype, exp in SEARCH_CASES:
        try:
            r = requests.get(f"{FLASK_URL}/api/v1/icd-search",
                             params={"q":q,"type":stype,"limit":5}, timeout=5)
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
            status, top = "FAIL", str(e)[:20]; f += 1

        line = f"  '{q:<16}' -> {stype:<12} [{status}] top={top}"
        lines.append(line); print(line)

    total = p + w + f
    verdict = ("READY FOR DEMO" if f == 0 and w <= 2
               else "MOSTLY WORKING" if f == 0
               else "NEEDS FIXES" if f <= 3
               else "CRITICAL ISSUES")

    lines += ["", f"SUMMARY: PASS={p} WARN={w} FAIL={f}/{total}",
              f"VERDICT: {verdict}", "==="]

    print("\n")
    for l in lines: print(l)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"doctor_agent_{ts}.md"
    out.write_text("\n".join(lines))
    print(f"\nReport saved: {out}")
    return f == 0

def run_via_claude():
    if not AGENT_FILE.exists():
        return None
    prompt = AGENT_FILE.read_text()
    prompt += f"\n\nIMPORTANT: Actually call the API at {FLASK_URL} using Python requests.\nRun ALL test cases and report ACTUAL response values.\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    try:
        result = subprocess.run(["claude", "-p", prompt],
                                capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print(result.stdout)
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        print(f"Flask not running at {FLASK_URL}")
        print("   Run: python app.py")
        sys.exit(1)
    print(f"Flask running at {FLASK_URL}\n")

    ok = None
    if "--direct" not in sys.argv:
        ok = run_via_claude()
    if ok is None:
        ok = run_direct()

    sys.exit(0 if ok else 1)
