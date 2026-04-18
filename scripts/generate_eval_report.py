#!/usr/bin/env python3
"""Generate thesis evaluation artifacts: confusion matrices and classification reports."""
import pickle, sys, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).parent.parent))

EVAL_DIR = Path('docs/evaluation')
EVAL_DIR.mkdir(parents=True, exist_ok=True)

def load_artifacts():
    mdc_clf = pickle.load(open('models/mdc_predictor.pkl', 'rb'))
    sev_clf = pickle.load(open('models/severity_predictor.pkl', 'rb'))
    mdc_le  = pickle.load(open('models/mdc_label_encoder.pkl', 'rb'))
    sev_le  = pickle.load(open('models/severity_label_encoder.pkl', 'rb'))
    return mdc_clf, sev_clf, mdc_le, sev_le

def load_data():
    df = pd.read_csv('data/clinical_training_data.csv')
    feat = open('models/mdc_feature_names.txt').read().strip().split('\n')
    X    = df[feat]
    return X, df['target_mdc'], df['target_severity']

def save_cm(cm, labels, title, path):
    fig, ax = plt.subplots(figsize=(max(10, len(labels)), max(8, len(labels) - 2)))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
    disp.plot(ax=ax, colorbar=True, xticks_rotation=45)
    ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Saved: {path}')

def save_report(report, title, path):
    Path(path).write_text(f'# {title}\n\n```\n{report}\n```\n')
    print(f'  Saved: {path}')

def main():
    print('Loading...')
    mdc_clf, sev_clf, mdc_le, sev_le = load_artifacts()
    X, y_mdc, y_sev = load_data()

    X_tr, X_te, ym_tr, ym_te, ys_tr, ys_te = train_test_split(
        X, y_mdc, y_sev, test_size=0.2, random_state=42, stratify=y_mdc)

    # MDC — target_mdc is already string labels; model predicts encoded ints
    print('\n=== MDC Predictor ===')
    ym_pred   = mdc_clf.predict(X_te)
    ym_te_d   = ym_te.values if hasattr(ym_te, 'values') else ym_te
    ym_pred_d = mdc_le.inverse_transform(ym_pred)
    rpt = classification_report(ym_te_d, ym_pred_d, zero_division=0)
    print(rpt)
    save_report(rpt, 'MDC Predictor — Per-Class Classification Report',
                EVAL_DIR / 'mdc_classification_report.md')
    labels = sorted(set(ym_te_d))
    save_cm(confusion_matrix(ym_te_d, ym_pred_d, labels=labels),
            labels, 'MDC Confusion Matrix (Test Set)',
            EVAL_DIR / 'mdc_confusion_matrix.png')

    # Severity
    print('\n=== Severity Predictor ===')
    ys_pred   = sev_clf.predict(X_te)
    ys_te_d   = ys_te.values if hasattr(ys_te, 'values') else ys_te
    ys_pred_d = sev_le.inverse_transform(ys_pred)
    rpt2 = classification_report(ys_te_d, ys_pred_d, zero_division=0)
    print(rpt2)
    save_report(rpt2, 'Severity Predictor — Per-Class Classification Report',
                EVAL_DIR / 'severity_classification_report.md')
    labels2 = sorted(set(ys_te_d))
    save_cm(confusion_matrix(ys_te_d, ys_pred_d, labels=labels2),
            labels2, 'Severity Confusion Matrix (Test Set)',
            EVAL_DIR / 'severity_confusion_matrix.png')

    print('\nDone. Files in docs/evaluation/')

if __name__ == '__main__':
    main()
