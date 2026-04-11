# Model Training Results — T2.1

**Best model:** XGBoost  
**Accuracy:** 99.85%  
**Weighted F1:** 0.9985  
**AUC-ROC (macro OvR):** 0.9996  

## Metrics Comparison

| Model | Accuracy | Weighted F1 | AUC-ROC |
|---|---|---|---|
| Random Forest (baseline) | 99.85% | 0.9985 | 1.0000 |
| XGBoost | 99.85% | 0.9985 | 0.9996 |
| LightGBM | 99.85% | 0.9985 | 0.9997 |

## Classification Report (Best Model on Test Set)
```
                   precision    recall  f1-score   support

coding_incomplete      0.992     1.000     0.996       389
 grouping_invalid      1.000     0.985     0.992       200
   grouping_valid      1.000     1.000     1.000      1389

         accuracy                          0.998      1978
        macro avg      0.997     0.995     0.996      1978
     weighted avg      0.998     0.998     0.998      1978

```

## Feature List (28 features)
```
gender, claim_status, claim_stage, claim_month_year, care_type, tariff_class, entry_type, discharge_status, icu_indikator, episodes, idrg_primary_icd10, idrg_icd10_valid, idrg_icd9_procedure, idrg_icd9_valid, inacbg_primary_icd10, inacbg_icd10_validity, mdc_number, drg_code, idrg_grouping_success, inacbg_cbg_code, base_tariff, actual_tariff, kelas, inacbg_grouping_success, final_success, icd_match, tariff_ratio, has_procedure
```
---

## No-Leakage Experiment — XGBoost without `final_success`

**Motivation:** `final_success` (= `idrg_grouping_success AND inacbg_grouping_success`)
is a derived field that directly encodes the target label. Including it constitutes
data leakage — the model trivially reads the answer. This experiment measures how
much of the performance was real vs. leakage-driven.

**Feature dropped:** `final_success` (1 of 28 features removed → 27 features)  
**Saved as:** `models/xgboost_no_leakage.pkl`  
**Iterations used:** 80

### Results

| Metric | Original (with `final_success`) | No-Leakage (27 features) | Delta |
|---|---|---|---|
| Accuracy | 99.85% | 98.7867% | -1.0633pp |
| Weighted F1 | 0.9985 | 0.9879 | -0.0106 |
| AUC-ROC | 0.9996 | 0.9984 | -0.0012 |

### Classification Report (No-Leakage Model)
```
                   precision    recall  f1-score   support

coding_incomplete      0.964     0.977     0.971       389
 grouping_invalid      1.000     0.985     0.992       200
   grouping_valid      0.993     0.991     0.992      1389

         accuracy                          0.988      1978
        macro avg      0.986     0.984     0.985      1978
     weighted avg      0.988     0.988     0.988      1978
```

### Confusion Matrix
```
[[ 380    0    9]
 [   2  197    1]
 [  12    0 1377]]
```

### Interpretation

Accuracy dropped from 99.85% to 98.7867% (Δ -1.06pp). The model retains strong performance without `final_success`, confirming that the remaining 27 features carry genuine predictive signal. This no-leakage model is recommended for production if `final_success` cannot be guaranteed at prediction time (i.e., when predicting *before* both groupers have been run).

**Feature list (27, no `final_success`):**
```
gender, claim_status, claim_stage, claim_month_year, care_type, tariff_class, entry_type, discharge_status, icu_indikator, episodes, idrg_primary_icd10, idrg_icd10_valid, idrg_icd9_procedure, idrg_icd9_valid, inacbg_primary_icd10, inacbg_icd10_validity, mdc_number, drg_code, idrg_grouping_success, inacbg_cbg_code, base_tariff, actual_tariff, kelas, inacbg_grouping_success, icd_match, tariff_ratio, has_procedure
```
