import requests
import json
import datetime

BASE_URL = "http://localhost:5001/api/v1"

cases = [
    {
        "id": "CASE 1 — Hipertensi",
        "payload": {"primary_icd10":"I10","inacbg_icd10":"I10","icd9_procedure":"89.09","care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":196100},
        "expected_cbg": "Q-5-44-0",
        "expected_tariff": 196100
    },
    {
        "id": "CASE 2 — Pneumonia",
        "payload": {"primary_icd10":"J18.0","inacbg_icd10":"J18.0","icd9_procedure":"99.21","care_type":"inp","entry_type":"emd","kelas":"kelas_3","episodes":3,"actual_tariff":3613600},
        "expected_cbg": "J-4-16-I",
        "expected_tariff": 3613600
    },
    {
        "id": "CASE 3 — DM neuropati",
        "payload": {"primary_icd10":"E11.4","inacbg_icd10":"E11.4","icd9_procedure":"89.09","care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":2,"actual_tariff":3611500},
        "expected_cbg": "E-4-10-I",
        "expected_tariff": 3611500
    },
    {
        "id": "CASE 4 — BPH TURP",
        "payload": {"primary_icd10":"N40.1","inacbg_icd10":"N40.1","icd9_procedure":"60.29","care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":7116300},
        "expected_cbg": "V-1-14-I",
        "expected_tariff": 7116300
    },
    {
        "id": "CASE 5 — Stroke iskemik",
        "payload": {"primary_icd10":"I63.9","inacbg_icd10":"I63.9","icd9_procedure":"93.39","care_type":"inp","entry_type":"emd","kelas":"kelas_3","episodes":5,"actual_tariff":5484100},
        "expected_cbg": "G-4-14", # checking prefix
        "expected_tariff": 5484100
    },
    {
        "id": "CASE 6 — ISPA",
        "payload": {"primary_icd10":"J06.9","inacbg_icd10":"J06.9","icd9_procedure":"89.09","care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":150900},
        "expected_mdc": "Q",
        "expected_tariff": 150900
    },
    {
        "id": "CASE 7 — Tarif melebihi",
        "payload": {"primary_icd10":"I10","inacbg_icd10":"I10","icd9_procedure":"89.09","care_type":"outp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":500000},
        "is_financial": True
    },
    {
        "id": "CASE 8 — Katarak",
        "payload": {"primary_icd10":"H25.9","inacbg_icd10":"H25.9","icd9_procedure":"13.19","care_type":"inp","entry_type":"gp","kelas":"kelas_3","episodes":1,"actual_tariff":3638300},
        "expected_cbg": "H-2-36-0",
        "expected_tariff": 3638300
    }
]

search_tests = [
    {"term": "hipertensi", "type": "diagnosis", "expect": "I10"},
    {"term": "pneumonia", "type": "diagnosis", "expect": "J18"},
    {"term": "dm tipe 2", "type": "diagnosis", "expect": "E11"},
    {"term": "nebulisasi", "type": "procedure"},
    {"term": "stroke", "type": "diagnosis", "expect": "I6"}
]

print(f"=== DOCTOR TEST AGENT REPORT ===")
print(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d')}")
print("Tester: Dr. Budi Santoso (simulated)")
print("System: FYP2 DSS http://localhost:5001\n")

print("TEST RESULTS:")
passes, warns, fails = 0, 0, 0

def evaluate_case(case, resp, is_financial=False):
    global passes, warns, fails
    
    if resp.status_code != 200:
        fails += 1
        return f"FAIL | API Error {resp.status_code}"
    
    data = resp.json()
    if data.get('status') != 'success':
        fails += 1
        return "FAIL | Result error"
    
    pred = data['prediction']
    fin = data['financial']
    
    cbg = pred.get('predicted_cbg_code')
    mdc = pred.get('predicted_mdc')
    tariff = pred.get('predicted_base_tariff', 0)
    conf = pred.get('mdc_confidence', 0)
    lookup = pred.get('lookup_method', '')
    
    if is_financial:
        gap = fin.get('financial_gap', 0)
        risk = fin.get('risk_level', '')
        if risk in ['MEDIUM', 'HIGH']:
            passes += 1
            return f"PASS | Risk={risk} | Gap=Rp{gap:,.0f}"
        else:
            fails += 1
            return f"FAIL | Risk={risk} (expected MEDIUM/HIGH) | Gap=Rp{gap:,.0f}"
    
    expected_cbg = case.get('expected_cbg', '')
    expected_mdc = case.get('expected_mdc', '')
    if expected_cbg:
        expected_mdc = expected_cbg[0]
        
    status = ""
    # Rule evaluation
    if not cbg or tariff == 0:
        status = "FAIL"
    elif expected_mdc and mdc != expected_mdc and mdc not in ['Q', 'Z']:
        status = "FAIL"
    elif expected_mdc and mdc != expected_mdc and mdc in ['Q', 'Z']:
        status = "WARN"
    elif conf < 0.6 or "fallback" in lookup:
        status = "WARN"
    else:
        status = "PASS"
        
    if status == "FAIL": fails += 1
    elif status == "WARN": warns += 1
    else: passes += 1
    
    return f"{status:4s} | CBG={cbg} | Tariff=Rp{tariff:,.0f} | conf={conf:.2f} lookup={lookup}"

for c in cases:
    try:
        r = requests.post(f"{BASE_URL}/full-assessment", json=c['payload'])
        res_str = evaluate_case(c, r, c.get('is_financial', False))
        print(f"{c['id']:25s}: {res_str}")
    except Exception as e:
        fails += 1
        print(f"{c['id']:25s}: FAIL | Exception: {e}")

print("\nICD SEARCH TESTS:")
for t in search_tests:
    try:
        r = requests.get(f"{BASE_URL}/icd-search?q={t['term']}&type={t['type']}")
        if r.status_code == 200:
            res = r.json()
            if len(res) > 0:
                top = res[0]['code']
                if t.get('expect'):
                    if top.startswith(t['expect']):
                        status = "PASS"
                        passes += 1
                    else:
                        status = "FAIL"
                        fails += 1
                else:
                    status = "PASS" # Procedure check
                    passes += 1
                print(f"Search \"{t['term']}\": {status:5s} | Top result: {top}")
            else:
                fails += 1
                print(f"Search \"{t['term']}\": FAIL  | No results")
        else:
            fails += 1
            print(f"Search \"{t['term']}\": FAIL  | HTTP {r.status_code}")
    except Exception as e:
        fails += 1
        print(f"Search \"{t['term']}\": FAIL  | Exception: {e}")


print("\nSUMMARY:")
print(f"  PASS:  {passes}/13")
print(f"  WARN:  {warns}/13")
print(f"  FAIL:  {fails}/13")

print("\nCLINICAL OBSERVATIONS (as Dr. Budi):")
print("- ")
print("\nVERDICT: ")

