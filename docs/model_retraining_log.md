# Model Retraining Log — Surrogate INACBG Grouper

## Stage 1 — MDC Predictor

### MDC Predictor (XGBoost)
- Accuracy: 75.00%
- Weighted F1: 0.7531
```
              precision    recall  f1-score   support

           A      0.818     0.692     0.750        13
           B      1.000     1.000     1.000         6
           D      0.667     0.286     0.400         7
           E      0.600     0.500     0.545         6
           F      0.545     1.000     0.706         6
           G      0.842     0.667     0.744        24
           H      0.250     0.571     0.348         7
           I      0.647     0.550     0.595        20
           J      0.723     0.739     0.731        46
           K      0.517     0.789     0.625        19
           L      0.688     0.917     0.786        12
           M      0.651     0.903     0.757        31
           N      0.841     0.771     0.804        48
           O      0.857     1.000     0.923         6
           Q      0.844     0.784     0.813       255
           S      1.000     1.000     1.000         6
           U      0.500     0.778     0.609         9
           V      1.000     0.889     0.941         9
           W      0.667     0.857     0.750         7
           Z      0.702     0.621     0.659        95

    accuracy                          0.750       632
   macro avg      0.718     0.766     0.724       632
weighted avg      0.769     0.750     0.753       632

```

- 5-Fold CV Accuracy: 0.7682 ± 0.0077

## Stage 2 — Severity Predictor

### Severity Predictor (XGBoost, 4-class)
- Accuracy: 92.21%
- Weighted F1: 0.9251
```
              precision    recall  f1-score   support

           0      1.000     0.995     0.998       425
           I      0.890     0.825     0.856       137
          II      0.511     0.667     0.578        36
         III      0.421     0.444     0.432        18

    accuracy                          0.922       616
   macro avg      0.705     0.733     0.716       616
weighted avg      0.930     0.922     0.925       616

```
