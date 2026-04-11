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