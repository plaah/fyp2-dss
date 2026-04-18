# Known Limitations — FYP2 DSS Surrogate INACBG Grouper

## 1. Severity III Training Data Artifact
Only 91 records with severity III in the 3,076-record training set. CBG lookup table
produces clinically incorrect mappings for severe inpatient cases at extreme severity.
Example: J18 severity III → I-4-20-III (Angina code). Chapter-rule corrects MDC letter
but the specific CBG code within MDC remains unreliable. Affects ~3% of inpatient cases.

## 2. MDC Class Imbalance
Q (misc outpatient) = 1,273 records (41%). Rare: S=7, F=9, B=10.
Chapter-rule deterministically handles the most imbalanced classes.
Mid-tier class confusion (G vs I vs J) remains a model limitation.

## 3. Feedback Loop Does Not Trigger Retraining
UC014 stores doctor corrections in prediction_feedback table but does not
trigger automated model retraining. Manual retraining via
notebooks/04_surrogate_grouper_training.py is required.

## 4. Neurovi Integration Stub (UC002)
Awaiting Neurovi HIS API documentation from Tamtech. All clinical inputs
are currently entered manually via the web form.

## 5. Single-Hospital Training Data
Training data from one Tamtech client hospital (Oct–Nov 2025, 33 days).
Generalizability to other hospitals with different case mix is unknown.

## 6. INA-CBGs Tariff Snapshot
CBG tariff data reflects Oct–Nov 2025 rates. BPJS updates tariffs annually.
Lookup table requires periodic refresh.

## 7. ICD-10 Version
Uses ICD-10 2010 (WHO) per BPJS standard. ICD-11 not yet supported.
