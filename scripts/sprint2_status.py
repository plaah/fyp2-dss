"""
Sprint 2 Context Recovery Script
Run this at the start of any session to check which T2.x tasks are done.
Usage: python scripts/sprint2_status.py
"""

import os
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(label, condition, detail=""):
    status = "DONE   ✓" if condition else "MISSING ✗"
    print(f"  [{status}]  {label}{('  — ' + detail) if detail else ''}")
    return condition


def main():
    print("=" * 60)
    print("SPRINT 2 STATUS CHECK")
    print("=" * 60)

    models_dir = os.path.join(BASE_DIR, "models")
    docs_dir   = os.path.join(BASE_DIR, "docs")

    print("\n── T2.1  Model Training ──────────────────────────────")
    t21 = all([
        check("best_model.pkl",      os.path.exists(os.path.join(models_dir, "best_model.pkl"))),
        check("xgboost_model.pkl",   os.path.exists(os.path.join(models_dir, "xgboost_model.pkl"))),
        check("lightgbm_model.pkl",  os.path.exists(os.path.join(models_dir, "lightgbm_model.pkl"))),
        check("rf_baseline.pkl",     os.path.exists(os.path.join(models_dir, "rf_baseline.pkl"))),
        check("label_encoder.pkl",   os.path.exists(os.path.join(models_dir, "label_encoder.pkl"))),
        check("preprocessing.pkl",   os.path.exists(os.path.join(models_dir, "preprocessing.pkl"))),
        check("feature_names.txt",   os.path.exists(os.path.join(models_dir, "feature_names.txt"))),
        check("model_training_results.md",
              os.path.exists(os.path.join(docs_dir, "model_training_results.md"))),
    ])

    print("\n── T2.2  Flask /predict endpoint ─────────────────────")
    predictor_ok = os.path.exists(
        os.path.join(BASE_DIR, "src", "services", "predictor.py")
    )
    check("predictor.py", predictor_ok)

    routes_path = os.path.join(BASE_DIR, "src", "api", "routes.py")
    with open(routes_path) as f:
        routes_content = f.read()
    routes_wired = "predictor.predict" in routes_content
    check("/predict wired to predictor", routes_wired)

    # Try hitting the API if it's running
    health_ok = False
    predict_ok = False
    try:
        import urllib.request, json
        with urllib.request.urlopen("http://127.0.0.1:5000/api/v1/health", timeout=2) as r:
            data = json.loads(r.read())
            health_ok = data.get("status") == "ok"
        check("/health endpoint responding", health_ok,
              detail=f"model_loaded={data.get('model_loaded')}")
    except Exception:
        check("/health endpoint responding", False, detail="Flask not running (start with python app.py)")

    t22 = predictor_ok and routes_wired

    print("\n── T2.3  SHAP Explainability ─────────────────────────")
    explainer_ok = os.path.exists(
        os.path.join(BASE_DIR, "src", "services", "explainer.py")
    )
    bar_ok  = os.path.exists(os.path.join(docs_dir, "shap_plots", "shap_bar_plot.png"))
    sum_ok  = os.path.exists(os.path.join(docs_dir, "shap_plots", "shap_summary_plot.png"))
    check("explainer.py",          explainer_ok)
    check("shap_bar_plot.png",     bar_ok)
    check("shap_summary_plot.png", sum_ok)
    t23 = explainer_ok and bar_ok and sum_ok

    print("\n── T2.4  Docs & Commit ───────────────────────────────")
    sprint_sum = os.path.join(docs_dir, "sprint2_summary.md")
    check("sprint2_summary.md", os.path.exists(sprint_sum))
    check("scripts/sprint2_status.py", True)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  T2.1 Model Training:     {'✅ DONE' if t21 else '❌ INCOMPLETE'}")
    print(f"  T2.2 Flask /predict:     {'✅ DONE' if t22 else '❌ INCOMPLETE'}")
    print(f"  T2.3 SHAP Explainability:{'✅ DONE' if t23 else '❌ INCOMPLETE'}")

    if t21 and t22 and t23:
        print("\n  Demo 1 ready: YES")
        print("  Resume: Nothing — Sprint 2 is complete.")
    else:
        pending = []
        if not t21: pending.append("T2.1")
        if not t22: pending.append("T2.2")
        if not t23: pending.append("T2.3")
        print(f"\n  Demo 1 ready: NO")
        print(f"  Resume from: {pending[0]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
