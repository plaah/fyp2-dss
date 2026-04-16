---
name: bpjs-casemix-domain
description: >
  Deep domain knowledge base for BPJS Kesehatan, INA-CBGs tariff system,
  Casemix coding workflow, and Indonesian hospital billing. ALWAYS use this
  skill when the user asks about: BPJS rules, INA-CBGs, CBG codes, MDC groups,
  kelas tariffs, IDRG vs INACBG, grouping errors (E2103/E2063/E2006), ICD-10
  coding for Indonesian hospitals, claim rejection reasons, undercoding/overcoding,
  financial risk, reimbursement logic, or any question about "why does BPJS
  reject X" or "what does error Y mean". Essential context for all FYP2 DSS
  design decisions. Use before answering any BPJS/clinical domain question.
---

# BPJS Casemix Domain Knowledge

## Hospital Claim Flow (correct entry point)
```
Nurse assessment (triage + vitals)
    ↓
Doctor diagnosis + treatment plan  ← DSS ENTERS HERE
    ↓
Patient undergoes treatment
    ↓
Casemix coder: ICD-10 + ICD-9 coding
    ↓
iDRG (Tamtech internal grouper) → DRG code + tariff estimate
    ↓
INACBG (official BPJS grouper) → CBG code + base_tariff
    ↓
Claims batched monthly → BPJS DC
    ↓
BPJS pays after 30–90 days (or rejects)
```

## CBG Code Structure
```
Format:  [MDC]-[category]-[group]-[severity]
Example: J-4-16-I

MDC letter:  J = Respiratory
Category:    4 = Medical (1=surgical, 2-3=procedure, 4=medical, 5=misc)
Group:       16 = Pneumonia/whooping cough
Severity:    I = Ringan (mild inpatient)

Severity values:
  0   = Rawat jalan / outpatient / day procedure
  I   = Ringan (mild inpatient)
  II  = Sedang (moderate inpatient)
  III = Berat (severe inpatient)

NOTE: Tamtech hospital data only has severity 0 and I
(II and III not present in approved claims dataset)
```

## MDC Reference
| Letter | System | Key CBGs |
|---|---|---|
| A | Infectious (sepsis, TB, dengue) | A-4-13/14 |
| B | Hepatobiliary (liver, gallbladder) | B-1-12, B-4-13/14 |
| D | Blood (anemia) | D-1-20, D-4-13 |
| E | Endocrine (DM, thyroid) | E-1-20, E-4-10 |
| F | Mental health | F-5-14/16 |
| G | Nervous (stroke, epilepsy) | G-4-14, G-4-15, G-1-10 |
| H | Eye (cataract, glaucoma) | H-2-36, H-3-11/12 |
| I | Cardiovascular (AMI, angina) | I-4-10, I-4-17, I-4-20 |
| J | Respiratory (pneumonia, COPD) | J-4-16, J-4-17, J-4-18 |
| K | Digestive (appendix, hernia) | K-1-13/14, K-4-17/18 |
| L | Skin (cellulitis) | L-1-50, L-4-12 |
| M | Musculoskeletal (fracture) | M-1-80, M-3-16, M-4-12 |
| N | Urinary/kidney (UTI, stones) | N-1-40, N-3-14/15, N-4-12 |
| O | Obstetrics (C-section, delivery) | O-6-10, O-6-13 |
| Q | Chronic/misc outpatient | Q-5-44-0 (DOMINANT — 39%) |
| S | Injury/poisoning | S-4-12 |
| U | ENT (tonsil, ear) | U-1-15, U-4-13 |
| V | Male reproductive (prostate) | V-1-14 (TURP) |
| W | Female reproductive | W-1-20, W-4-14/16 |
| Z | Procedures/radiology/rehab | Z-3-12/18/23/27 |

## Tariff System
```
Kelas multipliers (approximate — use lookup table for exact):
  kelas_3: × 1.00  (reference — poorest, most common)
  kelas_2: × 1.25
  kelas_1: × 1.50

Tariff is FULLY DETERMINISTIC:
  CBG code + kelas → exactly one base_tariff value
  Confirmed: 0 rows with variance in Tamtech data
  Therefore: predict CBG code → look up tariff (no separate tariff model)

Example: J-4-16-I (Pneumonia ringan)
  kelas_3: Rp 3,613,600
  kelas_2: Rp 4,209,900
  kelas_1: Rp 4,806,100
```

## Grouping Errors (from Tamtech data)

### E2103 — iDRG coding belum final (~90% of failures)
- Workflow error: coder didn't finalize iDRG step
- NOT an ICD quality error
- Fix: complete iDRG before INACBG
- Common ICD patterns: Z09.8+Z09.8 (157), N40+Z09.8 (22), I10+I10 (23)

### E2063 — INA Grouper tidak valid (~5%)
- True coding error: INACBG rejected the ICD combination
- Fix: correct ICD codes
- Common causes: Z09.x as primary inpatient, R-codes as primary, N40 unspecified

### E2006 — NIK Coder tidak ditemukan (~3%)
- Admin error: coder's national ID not registered
- Fix: HR registers coder NIK in system
- Not a clinical issue

### CBG Code invalid (~2%)
- CBG generated is not in approved list
- Common with P-codes (neonatal) at non-NICU hospitals

## ICD-10 Rules for Indonesian BPJS
1. Z09.x (follow-up) cannot be ONLY diagnosis for inpatient claims
2. R-codes (symptoms R00-R99): only use when no specific diagnosis available
3. N40 (BPH): must use N40.0 or N40.1 — unspecified N40 rejected
4. Some codes are secondary-only — rejected as primary diagnosis
5. ICD-10 2010 WHO version (NOT ICD-10-CM used in US)
6. ICD-9-CM for procedures (NOT ICD-10-PCS)

## Common Indonesian Term → ICD Mappings
| Bahasa Indonesia | ICD-10 | Note |
|---|---|---|
| Hipertensi | I10 | Most common outpatient |
| Hipertensi gestasional | O13 | NOT I15 |
| DM tipe 2 / kencing manis | E11.9 | Subcode by complication |
| Neuropati DM | E11.4 | NOT G62.9 |
| Pneumonia / bronkopneumonia | J18.0 | Most common inpatient |
| PPOK | J44.1 | |
| Asma | J45.9 | |
| Stroke infark | I63.9 | |
| Gagal jantung | I50.9 | |
| Angina | I20.9 | |
| BPH / prostat | N40.1 | Must use .0 or .1 |
| ISK / infeksi saluran kemih | N39.0 | |
| Batu ginjal | N20.0 | |
| Katarak | H25.9 | |
| Fraktur femur | S72.9 | |
| Appendicitis | K35.8 | |
| KPD (ketuban pecah dini) | O42 | |
| Oligohidramnion | O41.0 | |
| ISPA | J06.9 | |
| Dengue / DF | A90 | |
| Diare akut | A09.0 | |
| Hipotensi | I95.9 | |

## Financial Logic (project implementation)
```python
financial_gap = actual_tariff - predicted_base_tariff
gap_ratio     = actual_tariff / predicted_base_tariff

Risk levels:
  LOW:      gap_ratio ≤ 1.05    → reimburse prob 0.95
  MEDIUM:   1.05 < ratio ≤ 1.20 → reimburse prob 0.80
  HIGH:     ratio > 1.20         → reimburse prob 0.60
  CRITICAL: grouping failed       → reimburse prob 0.15

Cash flow delay:
  SAFE claim:         0 extra days
  Coding incomplete: +30 days
  Grouping invalid:  +90 days
```

## Dual Grouper Architecture (Tamtech/Neurovi)
```
iDRG  = Tamtech's internal pre-validation grouper
        Must be "finalized" before INACBG runs
        E2103 = iDRG NOT finalized

INACBG = Official government BPJS grouper
         Final arbiter of CBG code + tariff
         E2063 = INACBG ran but returned invalid

Sequence: Code → iDRG finalize → INACBG → CBG + tariff → BPJS submit
```

## FYP2 Surrogate Grouper Design
```
Input:  primary_icd10, icd9_procedure, care_type, kelas, episodes
        (what doctor knows at diagnosis — no post-coding fields)

Stage 1: XGBoost MDC predictor
         20 classes (A-Z excl. P), accuracy 77.22%
         Key features: icd_chapter, icd_block_freq, is_outpatient

Stage 2: XGBoost severity predictor
         Binary: 0 (outpatient) vs I (inpatient), accuracy 92.21%
         Strongly correlated with care_type

Stage 3: Deterministic CBG lookup
         Key: (icd_block, care_type, kelas, severity)
         Fallback 1: (mdc_letter, severity, kelas)
         Fallback 2: (mdc_letter, severity)
         Coverage: 100% of training data

Output: predicted_cbg_code + predicted_base_tariff + tariff_by_kelas
```
