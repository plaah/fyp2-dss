# FYP2 — AI-Driven Decision Support System for Hospital Casemix Coding

An AI-powered **Decision Support System (DSS)** that predicts Indonesian **BPJS INA-CBGs** claim-grouping outcomes from clinical inputs *at the doctor's diagnosis stage* — before Casemix coding begins. It surrogates the proprietary INACBG grouper with a machine-learning pipeline so hospitals can catch coding and tariff problems early, instead of after a claim is rejected.

> **Student:** Aflakh Rasikh Ibadurrahman · **Course:** SECJ 4134, Universiti Teknologi Malaysia (2025/2026) · **Supervisor:** Dr. Ruhaidah Binti Samsudin

---

## The Problem

In Indonesian hospitals, doctors write ICD-10 diagnoses and ICD-9 procedures without knowing how those codes will be **grouped** by the INACBG engine or what **tariff** BPJS will reimburse. Incorrect coding is only caught *after* Casemix — causing:

- Rejected / disputed claims (industry estimates put rejection at ~22–38%)
- Delayed reimbursement (30–90 days)
- Direct revenue loss from undercoding or claims that exceed the reimbursement ceiling

This DSS inserts a prediction step **before** Casemix so coders get an early, explainable signal.

### What it outputs

Given ICD-10 diagnosis codes + ICD-9 procedure codes, the system returns:

1. **Predicted INA-CBGs CBG group** (via a surrogate grouper)
2. **BPJS reimbursement ceiling** (base tariff for the predicted group)
3. **Financial risk** if the planned charge exceeds the ceiling
4. **Actionable guidance** for the Casemix coder, with SHAP-based explanations

### Where it fits in the hospital workflow

```
Nurse assessment
  ↓
Doctor writes ICD-10 diagnosis + ICD-9 procedure
  ↓  ←── DSS ENTERS HERE (before Casemix)
System predicts: CBG group │ tariff ceiling │ financial risk │ guidance
  ↓
Casemix coder reviews → finalizes coding
  ↓
iDRG validation → INACBG grouper → BPJS claim
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask 3.0, Python 3.9, SQLAlchemy 2.0 |
| ML | XGBoost 2.0, SHAP 0.44, scikit-learn 1.3 |
| Database | PostgreSQL |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Recharts |

---

## Architecture — Surrogate INACBG Grouper (v2)

The proprietary INACBG grouper is replaced by a transparent 3-stage ML pipeline. **Design rule:** only clinical inputs are used as features — never post-grouper fields — to avoid circular reasoning / data leakage.

### Stage 1 — MDC Predictor
- XGBoost (`multi:softprob`), 20 Major Diagnostic Categories
- **Accuracy 83% · Weighted F1 0.84**
- Key features: ICD chapter, ICD block frequency, care type (inpatient/outpatient)
- Plus a deterministic chapter-rule override for surgical MDC priority

### Stage 2 — Severity Predictor
- XGBoost (`multi:softprob`), 4 severity classes (outpatient, mild, moderate, severe)
- **Accuracy 95% · Weighted F1 0.96**
- Known limitation: severity-III F1 = 0.62 (only 91 training records for that class)

### Stage 3 — CBG Lookup
- Deterministic lookup with a 3-level fallback; 100% coverage of training records
- Key: `(icd_block, care_type, kelas, severity)`

### Explainability
- SHAP `TreeExplainer` on the MDC predictor surfaces the top-3 feature contributions per prediction, returned to the UI as `{feature, impact, direction}`.

> Trained models (`*.pkl`) are not committed. Regenerate them from the training scripts (see `notebooks/` and `scripts/`).

---

## Project Structure

```
fyp2-dss/
├── app.py                       # Flask entry point
├── config.py                    # Config via env vars (SECRET_KEY, DATABASE_URL)
├── requirements.txt
├── src/
│   ├── api/routes.py            # REST API (Blueprint, /api/v1)
│   ├── models/                  # SQLAlchemy ORM + CRUD
│   └── services/
│       ├── surrogate_grouper.py     # 3-stage ML prediction core
│       ├── financial_estimator.py   # tariff gap + risk bands
│       └── recommendation_engine.py # coder guidance text
├── frontend/                    # React + Vite SPA (built dist served by Flask)
│   └── src/
│       ├── pages/Predict.tsx
│       ├── pages/Dashboard.tsx
│       └── lib/api.ts           # typed fetch wrappers
├── models/                      # feature-name manifests (.pkl regenerated, not committed)
├── scripts/                     # eval reports, ICD lookup builders, doctor sim agent
├── notebooks/                   # model training
└── tests/                       # pytest suite (137 tests)
```

---

## API

Base path: `/api/v1`

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/predict` | POST | MDC + severity prediction |
| `/financial-impact` | POST | Tariff gap + financial risk |
| `/recommend` | POST | Coder action recommendation |
| `/full-assessment` | POST | **Main endpoint** — all outputs combined |
| `/icd-search` | GET | Free-text ICD search (Indonesian + English) |
| `/stats` | GET | Dashboard KPI aggregates |
| `/feedback` | POST | Save prediction feedback for retraining |
| `/retrain` | POST | Trigger model retraining when feedback threshold is met |

The built React SPA is served from the same Flask app at `/`.

---

## Database Schema

| Table | Purpose |
|---|---|
| `predictions` | Audit trail — prediction, risk level, financial gap, top SHAP feature, source |
| `icd_reference` | ICD-10 + ICD-9-CM catalogue — code, description, category, MDC group |
| `system_stats` | Pre-aggregated daily KPIs for the dashboard |
| `prediction_feedback` | Coder feedback used to drive model retraining |

---

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL
- Node.js 18+ (for the frontend)
- On Apple Silicon: `brew install libomp` (required by some ML deps)

### Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure via environment (defaults shown)
export DATABASE_URL="postgresql://localhost:5432/fyp2_db"
export SECRET_KEY="change-me"

python app.py            # Flask on port 5001
```

### Frontend

```bash
cd frontend
npm install
npm run dev              # Vite dev server on port 5173
npm run build            # production build into frontend/dist (served by Flask)
```

> Models and training data are not committed. Provide your own training CSVs and run the training scripts in `notebooks/` to generate the `*.pkl` artifacts before `/predict` will work.

---

## Testing

```bash
source venv/bin/activate
python -m pytest tests/ -q                     # 137 tests
python scripts/run_doctor_agent.py --direct    # end-to-end clinical-case simulation
cd frontend && npm run build                   # frontend build must succeed
```

Expected simulation WARNs (model limitations, not bugs):
- `J18.0` inpatient severity-III → I-MDC (cross-MDC artifact)
- `I63.9` inpatient severity-III → E-MDC (cross-MDC artifact)

---

## Design Constraints & Honesty Notes

1. **No data leakage** — grouping-validity fields are never used as ML features.
2. **ICD versions** — ICD-10 (2010 WHO) for diagnoses, ICD-9-CM for procedures, following Indonesian standard.
3. **Real hospital data is private** — training data is not included in this repository.
4. **Surrogate, not the real grouper** — this approximates INACBG behaviour for decision support; it is not a certified claims engine.
5. **Severity-III is undertrained** — predictions for the most severe class are the least reliable (small sample).

---

## License

Academic project (Final Year Project, UTM). No license granted for production or commercial use.
