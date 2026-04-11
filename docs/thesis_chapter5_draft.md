# Chapter 5: Implementation and Testing

## 5.1 Overview of System Implementation

The AI-driven Decision Support System (DSS) for BPJS Casemix claim grouping was developed using a layered architecture comprising four distinct tiers: the data layer, the machine learning service layer, the API layer, and the presentation layer. Each tier encapsulates a clearly defined responsibility, enabling the system to evolve incrementally without coupling concerns across boundaries.

The data layer is responsible for ingesting the hospital claims dataset sourced from Tamtech's production PostgreSQL database, applying feature engineering transformations, and producing cleaned, model-ready artefacts. The machine learning service layer houses the trained XGBoost classifier, the SHAP-based explainability engine, the financial impact estimator, and the recommendation synthesis engine. These services are stateless modules that expose Python function interfaces consumed by the layer above. The API layer is implemented as a Flask REST API using Blueprint-based modular routing, and it serves JSON responses to any HTTP client including the frontend dashboard. The presentation layer consists of a browser-based interface built with HTML, CSS, JavaScript, and Chart.js that allows Casemix coders to submit claim parameters and receive structured decision support in real time.

The project adopted a Scrum-based sprint development methodology across five two-week sprints. This approach was justified by the evolving nature of the requirements: the machine learning model selection, the tariff business rules, and the recommendation logic all required iterative refinement based on domain feedback and empirical experimentation. Sprint 1 established the project environment and data pipeline; Sprint 2 delivered the core ML prediction engine with SHAP explainability; Sprint 3 introduced the financial impact estimator and recommendation synthesis module, completing the backend intelligence layer. The sprint cadence ensured that each deliverable was independently testable and demoable, aligning with the project's Jira-tracked evaluation milestones.

The development environment consisted of Python 3.9.6 on macOS Apple Silicon (M-series), with library dependencies managed via a Python virtual environment. The key libraries utilised were Flask 3.0.0 for the REST API, XGBoost 2.0.3 and LightGBM 4.6.0 for machine learning, SHAP 0.44.0 for explainability, SQLAlchemy 2.0.23 for the database ORM, pandas 2.1.4 and NumPy 1.26.4 for data manipulation, and scikit-learn 1.3.2 for preprocessing utilities and evaluation metrics. PostgreSQL was used as the persistence store for claim records. LightGBM required the OpenMP runtime library (`libomp`) installed via Homebrew to function correctly on the Apple Silicon platform.

---

## 5.2 Coding of Main Functions

### 5.2.1 Data Pipeline Module (`src/services/pipeline.py`)

The data pipeline module is responsible for loading the synthetic augmented BPJS dataset, cleaning raw values, applying encoding transformations, engineering domain-relevant features, and producing stratified training and test splits that are written to disk for reproducible model training.

The dataset loading step reads `data/synthetic_bpjs.csv`, a 10,000-record file produced by augmenting 3,429 real Tamtech hospital claims using the SDV GaussianCopula generative model. An initial cleaning pass removes the `source` column, which encodes whether a record is real or synthetic and would constitute a data leakage feature. Missing values in boolean columns are filled with `False`, and string fields are normalised to lowercase.

Feature engineering introduces three derived columns that carry strong clinical and operational signal. The `icd_match` binary feature flags whether the primary ICD-10 code assigned by the iDRG grouper matches the code submitted to the INACBG grouper. A mismatch between these two systems is a known indicator of coding inconsistency that frequently causes grouping failures in the Indonesian BPJS context. The `tariff_ratio` numeric feature expresses the ratio of the hospital's actual submitted tariff to the INA-CBGs base tariff for the assigned CBG code. Values above 1.0 signal financial risk because BPJS will only reimburse up to the official ceiling. The `has_procedure` binary feature encodes whether any ICD-9-CM procedure code was submitted alongside the diagnosis, as the presence of a procedure code generally elevates the DRG complexity tier and influences the MDC assignment.

Encoding was applied in two strategies based on column cardinality. Low-cardinality categorical columns such as `gender`, `claim_status`, `kelas`, and `claim_month_year` were encoded using scikit-learn's `LabelEncoder` with a reserved `__missing__` class to gracefully handle unseen values at inference time. High-cardinality string columns — notably `idrg_primary_icd10`, `inacbg_primary_icd10`, `inacbg_cbg_code`, `claim_stage`, and `entry_type` — received frequency encoding, replacing each unique string with its observed proportion in the training set. This decision was motivated by the fact that ICD-10 codes number in the thousands and one-hot encoding would have produced a prohibitively wide feature matrix while introducing sparsity that degrades tree-based model performance.

The following excerpt illustrates the core feature engineering logic applied to each record:

```python
# idrg and inacbg ICD-10 must agree for a consistent grouping
df["icd_match"] = (
    df["idrg_primary_icd10"].str.strip().str.upper()
    == df["inacbg_primary_icd10"].str.strip().str.upper()
).astype(int)

# Tariff excess indicator: actual / base > 1 means hospital over-ceiling
df["tariff_ratio"] = df.apply(
    lambda r: round(r["actual_tariff"] / r["base_tariff"], 4)
    if r["base_tariff"] > 0 else 1.0, axis=1
)

# Whether any ICD-9-CM procedure was coded for this encounter
df["has_procedure"] = df["idrg_icd9_procedure"].apply(
    lambda v: 0 if pd.isna(v) or str(v).strip() in ("", "nan") else 1
)
```

The stratified 80/20 train-test split uses scikit-learn's `train_test_split` with `stratify=y` to ensure that the class distribution across `grouping_valid`, `coding_incomplete`, and `grouping_invalid` is preserved in both partitions. This is particularly important given the class imbalance: `grouping_valid` constitutes 70% of the dataset, while `grouping_invalid` accounts for only 10%.

---

### 5.2.2 Machine Learning Prediction Engine (`src/services/predictor.py`)

The prediction engine wraps a trained XGBoost classifier loaded from a serialised pickle artefact (`models/best_model.pkl`). XGBoost was selected as the primary model after comparing it against LightGBM and a Random Forest baseline across accuracy, weighted F1-score, and AUC-ROC (one-vs-rest). All three models achieved near-identical performance, converging at 99.85% accuracy and a weighted F1-score of 0.9985. XGBoost was preferred because it offered the best compatibility with SHAP's TreeExplainer, provided native support for multi-class probability calibration, and has well-documented production deployment characteristics in healthcare informatics literature.

The model was trained to perform three-class classification predicting the `ml_label` target: `grouping_valid` (claim approved for BPJS submission), `coding_incomplete` (iDRG finalization not done — coder must act), and `grouping_invalid` (INACBG grouper rejected the ICD codes — recoding required). The label distribution in the training data was 70% / 20% / 10% respectively, reflecting the target distribution specified by domain experts at Tamtech.

| Model | Accuracy | Weighted F1 | AUC-ROC (OvR) |
|---|---|---|---|
| Random Forest (baseline) | 99.85% | 0.9985 | 1.0000 |
| **XGBoost (deployed)** | **99.85%** | **0.9985** | **0.9996** |
| LightGBM | 99.85% | 0.9985 | 0.9997 |

A notable implementation challenge encountered during Sprint 2 concerned XGBoost's early stopping mechanism. The SHAP TreeExplainer requires that the model's internal `num_boost_round` matches the actual number of trees used during inference; when early stopping was enabled through the scikit-learn API, the internally stored `best_ntree_limit` diverged from the explainer's expectations, causing assertion errors at inference time. The resolution was to train the model for a fixed 150 iterations without early stopping, accepting the marginal risk of slight overfitting in exchange for full SHAP compatibility.

The predictor module loads all artefacts lazily at first call using module-level singleton variables. This ensures that the heavy model deserialisation occurs only once per server process lifetime. The `preprocess_input` function applies an identical transformation pipeline to each API request as was applied during training, accepting flexible input types (string `"true"` or boolean `True` for boolean fields; string `"outp"` or integer `2` for care type) to improve API ergonomics for frontend developers.

---

### 5.2.3 SHAP Explainability Module (`src/services/explainer.py`)

Explainability is a critical requirement for clinical decision support systems. Casemix coders are domain experts accountable for coding decisions; presenting a bare probability value without justification is insufficient and potentially harmful to clinical workflow trust. The SHAP (SHapley Additive exPlanations) framework addresses this by providing a theoretically grounded method for attributing the contribution of each input feature to a specific prediction.

The module wraps `shap.TreeExplainer`, which is optimised for tree ensemble models and computes exact Shapley values in polynomial time using the TreeSHAP algorithm. For each inference, the explainer returns an array of shape `(n_samples, n_features, n_classes)` for XGBoost multi-class models. The module slices this array along the predicted class dimension to extract the per-feature contributions specific to the predicted outcome, then returns the top three features sorted by absolute SHAP value magnitude.

An example SHAP output returned by the `/predict` endpoint for a valid claim is shown below:

```json
[
  { "feature": "final_success", "impact": 5.0993, "direction": "positive" },
  { "feature": "idrg_primary_icd10", "impact": 0.0320, "direction": "positive" },
  { "feature": "inacbg_primary_icd10", "impact": 0.0158, "direction": "positive" }
]
```

The dominance of `final_success` (SHAP impact 5.10, compared to 0.03 for the next feature) has a clear clinical interpretation: the model has correctly identified that the jointly successful completion of both the iDRG and INACBG grouping pipeline is the single strongest predictor of a valid BPJS claim outcome. This feature is a derived column (`final_success = idrg_grouping_success AND inacbg_grouping_success`) engineered during the data pipeline phase, and the model has learned its decisive role from the training data.

---

### 5.2.4 Financial Impact Estimator (`src/services/financial_estimator.py`)

The financial impact estimator implements the INA-CBGs tariff business rules that govern BPJS reimbursement in Indonesian hospitals. The core business logic is that BPJS reimburses at the official INA-CBGs base rate for the assigned CBG code, adjusted by a kelas (ward class) multiplier. The reimbursement ceiling is computed as:

```
reimbursement_ceiling = base_tariff × kelas_multiplier
```

where the kelas multipliers are defined by the official INA-CBGs tariff schedule:
- **Kelas 3** (standard BPJS ward): multiplier 1.00 — fully covered at base rate
- **Kelas 2**: multiplier 1.25 — hospital may charge up to 25% above base
- **Kelas 1**: multiplier 1.50 — hospital may charge up to 50% above base

Any amount submitted by the hospital above the ceiling is absorbed by the hospital and not reimbursed by BPJS. This creates a financial risk gap that Casemix coders and hospital finance teams must be made aware of before submission.

The estimator classifies financial risk into four levels derived from both the grouping outcome and the tariff ratio (actual / ceiling):

| Risk Level | Trigger Condition |
|---|---|
| LOW | `grouping_valid` AND tariff_ratio ≤ 1.05 |
| MEDIUM | `grouping_valid` AND 1.05 < tariff_ratio ≤ 1.20 |
| HIGH | `grouping_valid` AND tariff_ratio > 1.20, OR `coding_incomplete` |
| CRITICAL | `grouping_invalid` (zero reimbursement — full revenue forfeited) |

Reimbursement probability is estimated per risk band using domain calibration figures derived from practitioner knowledge of BPJS processing outcomes: 0.95 for LOW, 0.80 for MEDIUM, 0.60 for HIGH (valid grouping), 0.70 for `coding_incomplete` (will be paid after successful recoding), and 0.15 for `grouping_invalid` (requires full rework with high abandonment rate).

The cash flow risk — expressed as additional delay days before reimbursement — is 0 days for valid claims (settled in the next BPJS cycle), 30 days for incomplete coding (average recode-and-resubmit cycle), and 90 days for invalid grouping (full rework including ICD correction, INACBG re-grouping, and BPJS resubmission).

All constants are defined at the top of the module in named dictionaries (`KELAS_MULTIPLIERS`, `RISK_THRESHOLDS`, `CASH_FLOW_DELAY_DAYS`, `REIMBURSEMENT_PROB_BY_RISK`) rather than as magic numbers inline, to facilitate future tariff schedule updates without modifying business logic code.

---

### 5.2.5 Recommendation Synthesis Engine (`src/services/recommender.py`)

The recommendation synthesis engine aggregates the three upstream outputs — ML prediction, SHAP explanation, and financial assessment — into a unified, prioritised set of actionable instructions tailored to the Casemix coder's immediate workflow needs. This is the module that operationalises the DSS value proposition: translating probabilistic model outputs into concrete next steps that a non-technical clinical administrator can act on.

The engine defines a `PRIMARY_ACTION` for each prediction-risk combination, mapping to one of four values: `SUBMIT` (claim is valid and ready), `RECODE` (ICD-10 correction required), `COMPLETE_CODING` (iDRG finalisation missing), or `REVIEW` (valid but financial risk warrants human review). The recommendation priority (`LOW`, `MEDIUM`, `HIGH`, `URGENT`) mirrors the financial risk level and determines where the claim appears in the coder's task queue.

For `coding_incomplete` predictions, the engine inspects the top SHAP feature to identify the specific coding step that is blocking the claim. For example, if `final_success` is the dominant SHAP feature, the coder is directed to verify iDRG finalisation status. If `claim_stage` is dominant, the system instructs the coder to advance the claim to the `final-claim` stage in the Casemix management system. This feature-to-action mapping is implemented as a constant dictionary (`FEATURE_ACTION_MAP`) providing a transparent audit trail between model explanation and system recommendation.

The engine also generates ICD-10-specific coding tips from a curated lookup table (`ICD10_CODING_TIPS`) keyed by code prefix. For instance, a claim with primary code `I10` (essential hypertension) triggers the tip: *"Hypertension (I10): ensure complications are coded if present (I11–I13) for correct DRG grouping."* For `E11.x` (type 2 diabetes), the tip advises specifying the complication subcode to ensure correct MDC assignment.

An example recommendation output for a fully valid low-risk claim is shown below:

```json
{
  "primary_action": "SUBMIT",
  "priority": "LOW",
  "recommendations": [
    {
      "rank": 1,
      "action": "Submit claim to BPJS",
      "reason": "Grouping validated. INACBG CBG Q-5-44-0 accepted. No coding issues detected.",
      "impact": "IDR 196,100 reimbursement expected within 14 working days",
      "confidence": 0.9998
    }
  ],
  "warnings": [],
  "coding_tips": ["Verify ICD-10 code matches clinical documentation and is in ICD-10 2010 version"],
  "estimated_resolution_days": 14,
  "summary": "Claim is ready for BPJS submission with low financial risk (IDR 196,100 expected)."
}
```

---

## 5.3 Flask REST API

### 5.3.1 Architecture

The Flask REST API is implemented in `src/api/routes.py` using Flask's Blueprint mechanism, which registers all endpoints under a single `/api/v1` URL prefix. This design allows the API to be mounted at any path without modifying route definitions, and enables future versioned API families (`/api/v2`) to coexist without conflict. The `create_app()` factory in `app.py` instantiates the Flask application, applies the configuration object, and registers the Blueprint.

Service dependencies (predictor, explainer, financial estimator) are imported at module load time and, where computationally expensive (model loading), are lazily initialised on first invocation using module-level singleton variables. This ensures that the model artefacts are loaded only once per server process rather than on every request.

### 5.3.2 Endpoints

The API exposes five endpoints. Four are functional; one remains a stub for a future sprint.

**`GET /api/v1/health`**
A liveness probe that returns the server status, whether the XGBoost model is loaded, the model name, and the dataset record count. This endpoint is used by load balancers, monitoring agents, and the frontend dashboard's startup check.

**`POST /api/v1/predict`**
Accepts a JSON body containing claim fields (gender, care type, ICD-10 codes, tariff values, grouping flags, etc.) and returns the predicted `ml_label`, per-class confidence scores, the SHAP-derived top-3 feature explanations, and the model name. This is the core prediction endpoint.

Request example:
```json
{ "gender": "male", "care_type": "outp", "idrg_primary_icd10": "I10",
  "inacbg_primary_icd10": "I10", "base_tariff": 196100, "actual_tariff": 196100,
  "idrg_grouping_success": true, "inacbg_grouping_success": true, "kelas": "kelas_3" }
```

**`POST /api/v1/financial-impact`**
Accepts a prediction result object plus tariff data (base_tariff, actual_tariff, kelas, CBG code) and returns a complete financial risk assessment including the reimbursement ceiling, financial gap, risk level, estimated revenue loss, cash flow delay, and reimbursement probability.

**`POST /api/v1/recommend`**
Accepts the prediction result, financial result, and SHAP explanation as inputs, and returns ranked Casemix coding recommendations, financial warnings, ICD-10 coding tips, estimated resolution timeline, and an executive summary.

**`POST /api/v1/full-assessment`** *(Primary dashboard endpoint)*
The unified endpoint that executes the complete DSS pipeline in a single HTTP call: it runs prediction, computes financial impact, synthesises recommendations, and returns all three result objects combined with a processing time measurement. This is the endpoint consumed by the frontend dashboard.

Request example:
```json
{ "gender": "male", "care_type": "outp", "idrg_primary_icd10": "I10",
  "inacbg_primary_icd10": "I10", "base_tariff": 196100, "actual_tariff": 196100,
  "idrg_grouping_success": true, "inacbg_grouping_success": true,
  "kelas": "kelas_3", "claim_stage": "final-claim", "episodes": 1 }
```

Response structure:
```json
{
  "prediction": { "prediction": "grouping_valid", "confidence": {...}, "explanation": [...] },
  "financial":  { "risk_level": "LOW", "reimbursement_amount": 196100, ... },
  "recommendation": { "primary_action": "SUBMIT", "priority": "LOW", ... },
  "processing_time_ms": 145,
  "status": "success"
}
```

**`POST /api/v1/feedback`** *(Planned — Sprint 5)*
A stub endpoint reserved for the future human-in-the-loop feedback mechanism, which will allow Casemix coders to confirm or correct predictions, creating a labelled feedback loop for model retraining.

### 5.3.3 Error Handling

All endpoints wrap service calls in `try/except` blocks and return structured JSON error responses with appropriate HTTP status codes: `400 Bad Request` for malformed or missing input, and `500 Internal Server Error` for unexpected service failures. In the `/full-assessment` endpoint, the SHAP explanation step is wrapped independently so that a SHAP initialisation failure degrades gracefully to a placeholder explanation without aborting the prediction or financial assessment steps. This defensive design ensures that the DSS remains operational even if the explainability layer encounters an error, which is important for clinical workflow continuity.

Input validation is applied at API boundaries: JSON bodies are parsed with `silent=True` to prevent `400` errors from propagating upstream as unhandled exceptions, and required fields are checked explicitly before service methods are invoked. Service modules trust their callers and do not re-validate inputs internally, consistent with the principle of validating at system boundaries only.

---

*Word count by section:*
- 5.1 Overview: ~450 words
- 5.2.1 Data Pipeline: ~430 words
- 5.2.2 ML Prediction Engine: ~430 words
- 5.2.3 SHAP Explainability: ~310 words
- 5.2.4 Financial Estimator: ~430 words
- 5.2.5 Recommendation Engine: ~430 words
- 5.3 Flask REST API: ~520 words
- **Total: ~3,000 words**
