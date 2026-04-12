# FYP2 — AI-Driven Decision Support System for Hospital Management
## Claude Code Context File — Read this EVERY session before doing anything

**Student:** Aflakh Rasikh Ibadurrahman  
**Course:** SECJ 4134 | UTM | Semester 2, 2025/2026  
**Supervisor:** [Supervisor name]  
**Jira Project:** SCRUM (aflakhamjad.atlassian.net)  
**GitHub:** fyp2-dss (private repo)

---

## Project Overview

An AI-powered Decision Support System (DSS) that predicts BPJS INA-CBGs 
claim grouping outcomes from clinical inputs at the doctor's diagnosis 
stage — before Casemix coding begins. Built for Tamtech (health IT 
company serving Indonesian hospitals using Neurovi HIS).

**Core Problem:** Doctors write diagnoses and treatment plans without 
knowing how those decisions will be grouped by the INACBG engine or 
what tariff BPJS will reimburse. Incorrect ICD combinations only get 
caught after Casemix coding — causing rejected claims, delayed 
reimbursement (30–90 days), and revenue loss for the hospital.

**What this DSS does:** Given a doctor's primary diagnosis (ICD-10) and 
planned procedure (ICD-9), the system predicts:
1. Which INA-CBGs CBG group the claim will be classified into
2. The BPJS reimbursement ceiling (base tariff) for that group
3. Financial risk if the planned charge exceeds the tariff ceiling
4. Actionable guidance for the Casemix coder before coding starts

**System Architecture:**
- Backend: Flask REST API (Python)
- ML: 2-stage XGBoost surrogate grouper (MDC predictor + severity 
  predictor) + deterministic CBG lookup table
- Database: PostgreSQL + SQLAlchemy
- Frontend: HTML/CSS/JS + Chart.js clinical dashboard
- Data: 3,076 real Tamtech hospital claims (Oct–Nov 2025)
- Integration: Neurovi HIS hook prepared (pending API docs)

---

## Tech Stack & Environment

- **Python:** 3.9.6
- **Virtual env:** `venv/` (ALWAYS activate before running anything)
- **Key packages:** Flask 3.0.0, SQLAlchemy 2.0.23, XGBoost 2.0.3, LightGBM 4.6.0, SHAP 0.44.0, SDV 1.8.0, pandas 2.1.4, numpy 1.26.4, scikit-learn 1.3.2
- **Database:** PostgreSQL — fyp2_db (localhost:5432)
- **OS:** macOS Apple Silicon (M-series) — libomp installed via brew for LightGBM

**Activate venv:**
```bash
source venv/bin/activate
```

---

## Project Structure

```
fyp2-dss/
├── data/
│   ├── tamtech_raw_extract.csv     ← REAL hospital data (3,429 records)
│   ├── synthetic_bpjs.csv          ← TARGET: final 10K dataset (to be generated)
│   ├── icd10_2010_reference.csv    ← ICD-10 2010 reference codes
│   └── icd9_cm_procedures.csv      ← ICD-9-CM procedure codes
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               ← Flask endpoints (stubs defined)
│   ├── models/
│   │   ├── __init__.py
│   │   └── db_models.py            ← SQLAlchemy ORM models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pipeline.py             ← Data pipeline module
│   │   └── predictor.py            ← ML predictor service
│   └── utils/
├── tests/
├── notebooks/
│   └── 01_synthetic_data_generation.ipynb
├── docs/
├── venv/
├── app.py                          ← Flask entry point
├── config.py                       ← DB config
├── requirements.txt
├── .gitignore
└── CLAUDE.md                       ← This file
```

---

## Dataset — Real Tamtech Data

**Source:** Tamtech `dio_finance` PostgreSQL database (real hospital BPJS claims)  
**Date range:** Oct–Nov 2025 (33 days)  
**File:** `data/tamtech_raw_extract.csv`

## Business Logic — Surrogate INACBG Grouper (Option C)

### Correct Hospital Flow (Doctor-first entry point)
```
Nurse assessment
↓
Doctor writes diagnosis (ICD-10) + treatment plan (ICD-9 procedure)
↓ ← DSS PREDICTION ENTERS HERE (before Casemix coding)
↓
System predicts: Which CBG group? What tariff? Financial risk?
↓
Casemix coder reviews DSS prediction → finalizes ICD coding
↓
iDRG internal validation → INACBG official grouper
↓
Claim sent to BPJS → reimbursement
```

### Prediction Targets (what the system outputs)
| Output | Description | Source |
|---|---|---|
| `predicted_mdc` | Major Diagnostic Category (A-Z) | Stage 1 ML |
| `predicted_severity` | Severity level (0/I/II/III) | Stage 2 ML |
| `predicted_cbg_code` | INA-CBGs CBG code | Stage 3 lookup |
| `predicted_base_tariff` | BPJS reimbursement ceiling (IDR) | Stage 3 lookup |

### What the system does NOT predict
- grouping_valid / coding_incomplete / grouping_invalid
  (These are OUTPUTS of the INACBG grouper — not inputs)
- Whether BPJS will approve the claim
  (That depends on final coding, not prediction)

### Training Data
- Source: 3,076 approved claims from Tamtech dio_finance
- Only `ml_label == grouping_valid` used (known correct groupings)
- Features: clinical inputs only — ICD-10, ICD-9, care_type, kelas, episodes
- No grouping result fields used (no circular reasoning)

### Label Definition (ml_label column — raw data reference only)

The raw CSV has a DUAL grouping engine label (IDRG internal + INACBG official):

| Label | Meaning | Count | % |
|---|---|---|---|
| `grouping_valid` | INACBG grouping succeeded, claim ready for BPJS submission | 3,138 | 91.5% |
| `coding_incomplete` | iDRG coding not finalized (E2103) — coder needs to act | 281 | 8.2% |
| `grouping_invalid` | INACBG grouper failed — invalid ICD coding | 10 | 0.3% |

### Key Columns

```
claim_id, gender, claim_status, claim_stage, claim_month_year,
care_type, tariff_class, entry_type, discharge_status, icu_indikator, episodes,
idrg_primary_icd10, idrg_primary_icd10_desc, idrg_icd10_valid,
idrg_icd9_procedure, idrg_icd9_valid,
inacbg_primary_icd10, inacbg_primary_icd10_desc, inacbg_icd10_validity, inacbg_icd10_error,
inacbg_icd9_procedure, inacbg_icd9_validity,
mdc_number, drg_code, drg_description, idrg_grouping_success,
inacbg_cbg_code, inacbg_cbg_desc, base_tariff, actual_tariff,
kelas, inacbg_grouping_success, final_success, final_message, final_error_no,
ml_label
```

### Clinical Training Dataset (v2 — Surrogate Grouper)
- File: `data/clinical_training_data.csv`
- Records: 3,076 (approved claims only, MDC P excluded)
- Features: icd_chapter, icd_block_freq, is_outpatient, care_type_enc,
  entry_type_enc, kelas_enc, episodes, mdc_number, icd_match, has_procedure
- Targets: mdc_letter (Stage 1), severity (Stage 2), cbg_code (lookup)
- Note: synthetic_bpjs.csv is legacy — no longer used for training

---

**ICD versions used:** ICD-10 version 2010 (WHO) for diagnosis, ICD-9-CM for procedures — standard in BPJS/INA-CBGs Indonesia.

---

## Sprint Plan

### Sprint 1 (Apr 7–13)

| Task | Jira | Status |
|---|---|---|
| T1.1 Project Setup & Environment | SCRUM-18 | ✅ Done |
| T1.2 Synthetic Dataset Generation | SCRUM-19 | ✅ Done |
| T1.3 Data Pipeline & Derived Labels | SCRUM-20 | ✅ Done |
| T1.4 Update Thesis Ch.3 | SCRUM-21 | ⏳ Pending |

### Sprint 2 (Apr 14–20) — CRITICAL: Demo 1 Apr 20–23

| Task | Jira | Status |
|---|---|---|
| T2.1 Train XGBoost + LightGBM models | SCRUM-22 | ✅ Done |
| T2.2 Flask REST API /predict endpoint | SCRUM-23 | ✅ Done |
| T2.3 SHAP explainability module | SCRUM-24 | ✅ Done |
| T2.4 Git commit + Sprint 2 summary | SCRUM-25 | ✅ Done |

### Sprint 3 (Apr 21–27)

| Task | Jira | Status |
|---|---|---|
| T3.1 Financial Impact Estimator | SCRUM-26 | ✅ Done |
| T3.2 Recommendation Synthesis Module | SCRUM-27 | ✅ Done |
| T3.3 Thesis Ch.5 Draft | SCRUM-28 | ✅ Done |
| T3.4 Sprint 3 Housekeeping + Git | SCRUM-29 | ✅ Done |

### Sprint 4 (Apr 28–May 4)

| Task | Jira | Status |
|---|---|---|
| T4.1 Frontend Dashboard v1 (2 pages) | SCRUM-29 | ✅ Done |
| T4.2 PostgreSQL Integration + /stats | SCRUM-30 | ✅ Done |
| T4.3 Thesis Ch.4 Draft (DB + UI Design) | SCRUM-31 | ✅ Done |
| T4.4 Sprint 4 Housekeeping + Git | SCRUM-32 | ✅ Done |

### Sprint 5 (May 5–11) — Architecture Rebuild

| Task | Description | Status |
|---|---|---|
| T5.1 Extract clinical training data | `notebooks/04_surrogate_grouper_training.py` Step 1 | ✅ Done |
| T5.2 Build CBG lookup table | 3-level fallback, 100% coverage | ✅ Done |
| T5.3 Train MDC predictor | XGBoost 20-class, accuracy=77.22% | ✅ Done |
| T5.4 Train Severity predictor | XGBoost 4-class, accuracy=92.21% | ✅ Done |
| T5.5 SurrogateGrouper service | `src/services/surrogate_grouper.py` | ✅ Done |
| T5.6 Update API routes | Clinical-only inputs, new /predict + /full-assessment | ✅ Done |
| T5.7 Update Frontend | New form + CBG headline + badge row + dual confidence | ✅ Done |
| T5.8 Update test suite | 91/91 tests passing | ✅ Done |
| T5.9 Housekeeping | Status script + CLAUDE.md + git commit | ✅ Done |

---

## API Endpoints

| Endpoint | Method | Sprint | Status |
|---|---|---|---|
| `/api/v1/health` | GET | S1 | ✅ Live |
| `/api/v1/predict` | POST | S2 | ✅ Live |
| `/api/v1/financial-impact` | POST | S3 | ✅ Live |
| `/api/v1/recommend` | POST | S3 | ✅ Live |
| `/api/v1/full-assessment` | POST | S3 | ✅ Live |
| `/api/v1/stats` | GET | S4 | ✅ Live |
| `/api/v1/feedback` | POST | S5 | ⏳ Planned |

---

## Dashboard

| Page | Route | Description |
|---|---|---|
| Prediction Tool | `/` | ICD-10 input form → ML prediction + SHAP + financial risk + recommendations |
| Analytics Overview | `/dashboard` | KPI cards + donut/line/risk charts + paginated predictions table + CSV export |

Shared: sidebar navigation, status indicator, Neurovi hook (disabled, pending API docs).

---

## Database Schema

| Table | Purpose | Key Columns |
|---|---|---|
| `predictions` | Audit trail of every /full-assessment call | ml_prediction, risk_level, financial_gap, top_shap_feature, source |
| `icd_reference` | ICD-10 2010 + ICD-9-CM code catalogue | code, description, category, mdc_group |
| `system_stats` | Pre-aggregated daily metrics for dashboard | stat_date, total_predictions, avg_reimbursement_probability |

DB: PostgreSQL `fyp2_db` @ localhost:5432 (user: aflakhamjad)

---

## Neurovi Integration

Status: **Prepared, not yet active** — awaiting Neurovi API documentation from Tamtech.

Hooks in place:
- `fetchFromNeurovi(encounterId)` stub in `static/js/app.js`
- `source` field in `predictions` table accepts `'neurovi'` value
- "Connect Neurovi" button in sidebar (disabled, grayed out)

---

## ML Architecture — Surrogate INACBG Grouper (v2, Sprint 5)

> **Architecture rebuilt** from a flawed 3-class post-grouper predictor to a clinically
> correct 2-stage surrogate grouper. Inputs are now clinical-only (no circular feedback
> from grouper output). Training data: 3,076 records from tamtech_raw_extract.csv
> (ml_label == 'grouping_valid', excluding MDC P and X-0-98-X codes).

### Stage 1 — MDC Predictor

| Property | Value |
|---|---|
| Model | XGBoost (multi:softprob, 20 classes) |
| Accuracy | **77.22%** |
| Weighted F1 | **0.7747** |
| Training records | 3,076 |
| MDC classes | A B D E F G H I J K L M N O Q S U V W Z |
| Key features | icd_chapter, icd_block_freq, is_outpatient, care_type_enc |
| Artifact | `models/mdc_predictor.pkl` |

### Stage 2 — Severity Predictor

| Property | Value |
|---|---|
| Model | XGBoost (multi:softprob, 4 classes) |
| Accuracy | **92.21%** |
| Weighted F1 | **0.9251** |
| Severity classes | 0 (outpatient), I (mild), II (moderate), III (severe) |
| Key feature | is_outpatient (near-perfect predictor for severity 0) |
| Artifact | `models/severity_predictor.pkl` |

### Stage 3 — CBG Lookup

| Property | Value |
|---|---|
| Type | Deterministic lookup table (3-level fallback) |
| Primary key | (icd_block, care_type_str, kelas, severity) |
| Exact coverage | **100%** of training records |
| Fallback 1 | (mdc_letter, severity, kelas) |
| Fallback 2 | (mdc_letter, severity) |
| Artifact | `models/cbg_lookup_table.pkl` |

### SHAP Explainability

- TreeExplainer on MDC predictor → top 3 feature contributions per prediction
- Output: `[{"feature": str, "impact": float, "direction": "positive"|"negative"}]`
- Fallback to `feature_importances_` when TreeExplainer fails

### Legacy Model Performance (Sprint 2 — Retired)

> Retired 3-class predictor — accuracy was artificially high (99.85%) because it
> used post-grouper fields as features, creating circular reasoning.

| Model | Accuracy | Weighted F1 | Note |
|---|---|---|---|
| XGBoost (v1) | 99.85% | 0.9985 | Retired — circular features |
| LightGBM (v1) | 99.85% | 0.9985 | Retired |
| Random Forest | 99.85% | 0.9985 | Baseline only |

---

## Rubric Alignment (key weights)

| Component | Weight | Key Criteria |
|---|---|---|
| Output (Supervisor) | 40% | Fulfilled objectives, clean code, complete system, deployed, 3-min video |
| Presentation | 15% | Clear, confident, strong Q&A |
| Final Report (×2) | 20% | Complete chapters, methodology, testing |
| Progress 1 (Demo 1) | 5% | ≥40% completion by Apr 20 |
| Progress 2 (Demo 2) | 5% | ≥70% completion by May 25 |

---

## Important Constraints & Notes

1. **Apple Silicon (M-series Mac)** — LightGBM requires `brew install libomp`. numpy pinned to 1.26.4 for compatibility.
2. **Always activate venv** before running any Python: `source venv/bin/activate`
3. **Real data privacy** — tamtech_raw_extract.csv contains anonymized records. Never commit to public repo. Already in `.gitignore`.
4. **ICD codes** — Use ICD-10 2010 (WHO) for diagnosis, ICD-9-CM for procedures.
5. **No partial label** — The Tamtech system is binary (grouping_valid / invalid). Partial payment happens on BPJS side which this system doesn't capture.
6. **SDV augmentation** — Use GaussianCopula (not CTGAN) for small seed datasets like grouping_invalid (only 10 real records).
7. **Log all AI prompts used** — Required for thesis Appendix: List of Prompts Used.

---

## Current Session Priorities
1. `python scripts/surrogate_grouper_status.py` — check all artifacts
2. `python app.py` — verify Flask starts on port 5000/5001
3. `python -m pytest tests/ -q` — all 91 tests must pass
4. Check CLAUDE.md section "ML Architecture" for current model metrics

## Slim Context Rules (save tokens)
- Read ONLY the section you need, not the whole file
- Model metrics → read "ML Architecture" section only
- API inputs/outputs → read "API Endpoints" section only
- DB schema → read "Database Schema" section only
- Sprint status → read "Sprint Plan" section only

---

## How to Resume Work

Tell Claude Code:
> "Read CLAUDE.md, then continue from where we left off on [TASK]"

Claude Code will read this file and have full context without needing re-explanation.
