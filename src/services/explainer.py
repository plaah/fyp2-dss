"""
T2.3 — SHAP Explainability Module
Wraps shap.TreeExplainer around the best model.
explain() returns top 3 feature contributions for a single prediction.
Also generates summary/bar plots saved to docs/shap_plots/.
"""

import os
import pickle
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "models")
PLOTS_DIR  = os.path.join(BASE_DIR, "docs", "shap_plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

# ── Lazy-loaded singletons ─────────────────────────────────────────────────────
_explainer     = None
_feature_names = None
_label_enc     = None
_classes       = None


def _load():
    global _explainer, _feature_names, _label_enc, _classes
    if _explainer is not None:
        return

    import shap

    model      = pickle.load(open(os.path.join(MODELS_DIR, "best_model.pkl"), "rb"))
    preprocessing = pickle.load(open(os.path.join(MODELS_DIR, "preprocessing.pkl"), "rb"))
    _label_enc = pickle.load(open(os.path.join(MODELS_DIR, "label_encoder.pkl"), "rb"))
    _classes   = list(_label_enc.classes_)
    _feature_names = preprocessing["feature_names"]

    _explainer = shap.TreeExplainer(model)


def explain(features_array: np.ndarray, predicted_class_idx: int = None) -> list:
    """
    Compute SHAP values for a single sample and return top 3 contributions.

    Args:
        features_array: shape (1, n_features) — output of predictor.preprocess_input()
        predicted_class_idx: index of the predicted class (for multi-class SHAP slicing)

    Returns:
        List of dicts: [{"feature": str, "impact": float, "direction": str}, ...]
        direction = "positive" (pushes toward predicted class) or "negative"
    """
    _load()
    import shap

    shap_values = _explainer.shap_values(features_array)

    # shap_values is (n_classes, n_samples, n_features) for multi-class RF
    # or (n_samples, n_features, n_classes) for XGBoost
    if isinstance(shap_values, list):
        # sklearn-style: list of arrays, one per class
        if predicted_class_idx is None:
            predicted_class_idx = 0
        sv = shap_values[predicted_class_idx][0]  # shape (n_features,)
    elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        # XGBoost style: (n_samples, n_features, n_classes)
        if predicted_class_idx is None:
            predicted_class_idx = 0
        sv = shap_values[0, :, predicted_class_idx]  # shape (n_features,)
    else:
        sv = shap_values[0]  # binary or flat

    # Build ranked contributions
    contributions = []
    for i, (feat, val) in enumerate(zip(_feature_names, sv)):
        contributions.append({
            "feature":   feat,
            "impact":    abs(float(val)),
            "raw_shap":  float(val),
            "direction": "positive" if val >= 0 else "negative",
        })

    top3 = sorted(contributions, key=lambda x: x["impact"], reverse=True)[:3]

    # Return clean format for API
    return [
        {
            "feature":   c["feature"],
            "impact":    round(c["impact"], 4),
            "direction": c["direction"],
        }
        for c in top3
    ]


def generate_plots(n_samples: int = 500):
    """
    Generate and save SHAP summary and bar plots using a sample of X_train.
    Called once at startup or via CLI.
    """
    _load()
    import shap
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    DATA_DIR = os.path.join(BASE_DIR, "data")
    X_train  = pd.read_csv(os.path.join(DATA_DIR, "X_train.csv"))
    sample   = X_train.sample(min(n_samples, len(X_train)), random_state=42)

    print(f"  Computing SHAP values on {len(sample)} samples …")
    shap_values = _explainer.shap_values(sample)

    # Normalise to 2-D mean-abs for multi-class (average across classes)
    if isinstance(shap_values, list):
        sv_mean = np.mean(np.abs(np.array(shap_values)), axis=0)  # (n_samples, n_features)
    elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        sv_mean = np.mean(np.abs(shap_values), axis=2)            # (n_samples, n_features)
    else:
        sv_mean = np.abs(shap_values)

    feat_importance = pd.Series(
        sv_mean.mean(axis=0), index=_feature_names
    ).sort_values(ascending=False)

    # ── Bar plot ───────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 7))
    feat_importance.head(15).plot(kind="barh", ax=ax, color="steelblue")
    ax.invert_yaxis()
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title("SHAP Feature Importance (Mean |SHAP|) — Top 15")
    plt.tight_layout()
    bar_path = os.path.join(PLOTS_DIR, "shap_bar_plot.png")
    fig.savefig(bar_path, dpi=150)
    plt.close(fig)
    print(f"  Saved: {bar_path}")

    # ── Beeswarm summary plot ──────────────────────────────────────────────────
    try:
        sv_plot = shap_values[0] if isinstance(shap_values, list) else (
            shap_values[:, :, 0] if shap_values.ndim == 3 else shap_values
        )
        fig2, ax2 = plt.subplots(figsize=(10, 8))
        shap.summary_plot(sv_plot, sample, feature_names=_feature_names,
                          show=False, plot_type="dot", max_display=15)
        sum_path = os.path.join(PLOTS_DIR, "shap_summary_plot.png")
        plt.savefig(sum_path, dpi=150, bbox_inches="tight")
        plt.close("all")
        print(f"  Saved: {sum_path}")
    except Exception as e:
        print(f"  WARNING: beeswarm plot failed ({e}) — bar plot only.")

    return feat_importance.head(5).index.tolist()


if __name__ == "__main__":
    print("Generating SHAP plots …")
    top_feats = generate_plots()
    print(f"Top features: {top_feats}")
    print("=== T2.3 explainer plots DONE ===")
