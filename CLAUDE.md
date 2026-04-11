# FYP2 — AI-Driven Decision Support System for Hospital Management
## Claude Code Context File — Read this EVERY session before doing anything

**Student:** Aflakh Rasikh Ibadurrahman  
**Course:** SECJ 4134 | UTM | Semester 2, 2025/2026  
**Supervisor:** [Supervisor name]  
**Jira Project:** SCRUM (aflakhamjad.atlassian.net)  
**GitHub:** fyp2-dss (private repo)

---

## Project Overview

An AI-powered Decision Support System (DSS) for hospital Casemix coders to predict BPJS claim grouping outcomes before submission. Built for Tamtech (a health IT company in Malaysia/Indonesia).

**Core Problem:** Casemix coders manually review ICD-10 diagnosis codes and ICD-9 procedures to determine BPJS grouping. Incorrect coding wastes time and causes rejected claims. This DSS predicts the grouping outcome automatically and explains why.

**System Architecture:**
- Backend: Flask REST API (Python)
- ML: XGBoost + LightGBM + SHAP explainability
- Database: PostgreSQL + SQLAlchemy
- Frontend: HTML/CSS/JS + Chart.js
- Data: Real Tamtech hospital data + SDV augmentation

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

### Label Definition (ml_label column)

The system uses a DUAL grouping engine (IDRG internal + INACBG official BPJS):

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

### Target Dataset: synthetic_bpjs.csv

- **Total:** 10,000 records
- **Distribution:** 70% grouping_valid / 20% coding_incomplete / 10% grouping_invalid
- **Method:** Real data + SDV GaussianCopula augmentation per class
- **Augmentation needed:**
  - grouping_valid: +3,862 synthetic (seed: 3,138 real)
  - coding_incomplete: +1,719 synthetic (seed: 281 real)
  - grouping_invalid: +990 synthetic (seed: 10 real)

---

## Business Logic — BPJS Claim Grouping Flow

```
Patient discharged
    ↓
Casemix coder assigns ICD-10 diagnosis + ICD-9 procedure
    ↓
iDRG grouping (internal validation) → DRG code + tariff estimate
    ↓
INACBG grouping (official BPJS engine) → CBG code + base_tariff + kelas
    ↓
Claim submitted to BPJS (kemkes_dc → bpjs_dc)
    ↓
Final result: grouping_valid / coding_incomplete / grouping_invalid
```

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

---

## API Endpoints

| Endpoint | Method | Sprint | Status |
|---|---|---|---|
| `/api/v1/health` | GET | S1 | ✅ Live |
| `/api/v1/predict` | POST | S2 | ✅ Live |
| `/api/v1/financial-impact` | POST | S3 | ✅ Live |
| `/api/v1/recommend` | POST | S3 | ✅ Live |
| `/api/v1/full-assessment` | POST | S3 | ✅ Live |
| `/api/v1/feedback` | POST | S5 | ⏳ Planned |

---

## Model Performance (Sprint 2 Results)

| Model | Accuracy | Weighted F1 | AUC-ROC |
|---|---|---|---|
| Random Forest (baseline) | 99.85% | 0.9985 | 1.0000 |
| **XGBoost (primary — DEPLOYED)** | **99.85%** | **0.9985** | **0.9996** |
| LightGBM | 99.85% | 0.9985 | 0.9997 |

- Best model saved: `models/best_model.pkl` (XGBoost, 150 iterations)
- Top SHAP features: `final_success`, `claim_stage`, `inacbg_primary_icd10`, `entry_type`, `claim_status`
- SHAP plots: `docs/shap_plots/`

---

## ML Model Plan (Sprint 2)

- **Primary model:** XGBoost
- **Secondary model:** LightGBM  
- **Baseline:** Random Forest
- **Target accuracy:** ≥85% on test set
- **Explainability:** SHAP TreeExplainer — top 3 features per prediction
- **Evaluation:** Accuracy, F1-score (weighted), AUC-ROC (one-vs-rest)
- **Train/test split:** 80/20 stratified by ml_label

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

When Claude Code starts a new session, check this list:

1. Is `data/tamtech_raw_extract.csv` present? → Validate with pandas
2. Is `data/synthetic_bpjs.csv` present? → If not, run augmentation
3. Is `app.py` runnable? → `python app.py` should start Flask on port 5000
4. What's the current sprint task? → Check Sprint Plan above

---

## How to Resume Work

Tell Claude Code:
> "Read CLAUDE.md, then continue from where we left off on [TASK]"

Claude Code will read this file and have full context without needing re-explanation.
