# Model Retraining Log — Surrogate INACBG Grouper

## Stage 1 — MDC Predictor

### MDC Predictor (XGBoost)
- Accuracy: 77.22%
- Weighted F1: 0.7747
```
              precision    recall  f1-score   support

           A      0.647     0.846     0.733        13
           B      0.500     0.333     0.400         3
           D      0.667     0.857     0.750         7
           E      0.500     0.800     0.615         5
           F      0.375     1.000     0.545         3
           G      0.704     0.792     0.745        24
           H      0.500     0.714     0.588         7
           I      0.800     0.571     0.667        21
           J      0.773     0.756     0.764        45
           K      0.778     0.737     0.757        19
           L      0.846     0.917     0.880        12
           M      0.643     0.871     0.740        31
           N      0.864     0.792     0.826        48
           O      0.500     0.667     0.571         3
           Q      0.878     0.816     0.846       255
           S      1.000     0.667     0.800         3
           U      0.500     0.444     0.471         9
           V      1.000     1.000     1.000         9
           W      0.625     0.714     0.667         7
           Z      0.670     0.663     0.667        95

    accuracy                          0.772       619
   macro avg      0.688     0.748     0.702       619
weighted avg      0.786     0.772     0.775       619

```

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
