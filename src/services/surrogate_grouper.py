"""
Surrogate INACBG Grouper — Inference Service
============================================
Architecture:
    Stage 1: XGBoost MDC predictor (20 classes: A B D E F G H I J K L M N O Q S U V W Z)
    Stage 2: XGBoost severity predictor (4 classes: 0, I, II, III)
    Stage 3: Deterministic CBG lookup
                Primary key:  (icd_block, care_type, kelas, severity)
                Fallback-1:   (mdc_letter, severity, kelas)
                Fallback-2:   (mdc_letter, severity)

Business value:
    Enables doctors and Casemix coders to preview INACBG grouping outcome
    BEFORE the official grouper runs, allowing proactive coding correction
    and financial planning.

Training data: 3,076 real Tamtech claims (Oct–Nov 2025)
Models: models/mdc_predictor.pkl, models/severity_predictor.pkl,
        models/cbg_lookup_table.pkl, models/surrogate_preprocessing.pkl
"""

import os
import pickle
import logging
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "models")


class SurrogateGrouper:
    """
    Surrogate INACBG grouper predicting CBG code and base tariff from
    clinical inputs available at doctor diagnosis stage.
    """

    # INA-CBGs MDC descriptions (Bahasa Indonesia)
    MDC_DESCRIPTIONS = {
        'A': 'Penyakit Infeksi dan Parasit Tertentu',
        'B': 'Neoplasma',
        'D': 'Penyakit Darah, Organ Pembentuk Darah dan Gangguan Imunologi',
        'E': 'Penyakit Endokrin, Nutrisi dan Metabolik',
        'F': 'Gangguan Jiwa dan Perilaku',
        'G': 'Penyakit Susunan Saraf',
        'H': 'Penyakit Mata, Telinga, Hidung dan Tenggorokan',
        'I': 'Penyakit Sistem Sirkulasi',
        'J': 'Penyakit Sistem Pernapasan',
        'K': 'Penyakit Sistem Pencernaan',
        'L': 'Penyakit Kulit dan Jaringan Subkutan',
        'M': 'Penyakit Sistem Muskuloskeletal dan Jaringan Ikat',
        'N': 'Penyakit Sistem Genitourinari',
        'O': 'Kehamilan, Persalinan dan Masa Nifas',
        'Q': 'Penyakit Kronis dan Kondisi Lain-lain',
        'S': 'Cedera, Keracunan dan Akibat Luar Lainnya',
        'U': 'Prosedur dan Intervensi Khusus',
        'V': 'Faktor yang Mempengaruhi Status Kesehatan',
        'W': 'Pengobatan Belum Diklasifikasikan',
        'Z': 'Penyakit dan Kondisi Lain-lain / Kunjungan Rawat Jalan',
    }

    SEVERITY_LABELS = {
        '0':   'Rawat Jalan / Prosedur',
        'I':   'Rawat Inap Ringan',
        'II':  'Rawat Inap Sedang',
        'III': 'Rawat Inap Berat',
    }

    KELAS_MULTIPLIERS = {
        'kelas_1': 1.50,
        'kelas_2': 1.25,
        'kelas_3': 1.00,
    }

    # care_type string → int (matches training data encoding)
    CARE_TYPE_STR_MAP = {
        'outp': 2, 'gp': 2, 'ambulatory': 2,
        'inp': 1, 'inpatient': 1,
        'emd': 3, 'igd': 3, 'emergency': 3,
    }

    def __init__(self):
        self._mdc_clf        = None
        self._sev_clf        = None
        self._mdc_le         = None
        self._sev_le         = None
        self._lookup         = None
        self._preproc        = None
        self._mdc_fi         = None   # feature importances fallback for SHAP
        self._loaded         = False

    # ── Lazy load ─────────────────────────────────────────────────────────────
    def _load(self):
        if self._loaded:
            return
        try:
            self._mdc_clf  = pickle.load(open(os.path.join(MODELS_DIR, "mdc_predictor.pkl"),        "rb"))
            self._sev_clf  = pickle.load(open(os.path.join(MODELS_DIR, "severity_predictor.pkl"),   "rb"))
            self._mdc_le   = pickle.load(open(os.path.join(MODELS_DIR, "mdc_label_encoder.pkl"),    "rb"))
            self._sev_le   = pickle.load(open(os.path.join(MODELS_DIR, "severity_label_encoder.pkl"), "rb"))
            self._lookup   = pickle.load(open(os.path.join(MODELS_DIR, "cbg_lookup_table.pkl"),     "rb"))
            self._preproc  = pickle.load(open(os.path.join(MODELS_DIR, "surrogate_preprocessing.pkl"), "rb"))
            # Pre-compute feature importances for SHAP fallback
            self._mdc_fi   = pd.Series(
                self._mdc_clf.feature_importances_,
                index=self._preproc['feature_cols']
            ).sort_values(ascending=False)
            self._loaded = True
            logger.info("SurrogateGrouper: models loaded successfully")
        except Exception as exc:
            logger.error(f"SurrogateGrouper: failed to load models — {exc}")
            raise

    # ── Public API ────────────────────────────────────────────────────────────
    def predict(self, clinical_input: dict) -> dict:
        """
        Predict CBG code and base tariff from clinical inputs.

        Args:
            clinical_input: {
                "primary_icd10": str,      # e.g. "I10"
                "icd9_procedure": str,     # e.g. "89.09" (optional)
                "inacbg_icd10": str,       # e.g. "I10" (optional, defaults to primary_icd10)
                "care_type": str,          # "outp" | "inp" | "emd" | "gp"
                "entry_type": str,         # "gp" | "outp" | "emd" | "inp" | ...
                "kelas": str,              # "kelas_1" | "kelas_2" | "kelas_3"
                "episodes": int,           # default 1
            }

        Returns:
            Prediction dict with CBG code, tariff, MDC/severity predictions,
            confidence scores, lookup method, and SHAP explanation.
        """
        self._load()
        try:
            features_df = self._derive_features(clinical_input)
            mdc_letter, mdc_conf   = self._predict_mdc(features_df)
            severity,   sev_conf   = self._predict_severity(features_df)
            icd_block    = features_df['icd_block_raw'].iloc[0]
            care_type_s  = features_df['care_type_raw'].iloc[0]
            kelas        = features_df['kelas_raw'].iloc[0]
            cbg_info     = self._lookup_cbg(icd_block, care_type_s, kelas, severity, mdc_letter)
            base_tariff  = cbg_info.get('base_tariff', 0.0)
            shap_exp     = self._get_shap_explanation(features_df)

            return {
                "predicted_mdc":              mdc_letter,
                "predicted_mdc_description":  self.MDC_DESCRIPTIONS.get(mdc_letter, mdc_letter),
                "predicted_severity":         severity,
                "predicted_severity_label":   self.SEVERITY_LABELS.get(severity, severity),
                "predicted_cbg_code":         cbg_info.get('cbg_code', f"{mdc_letter}-?-?-{severity}"),
                "predicted_cbg_description":  cbg_info.get('cbg_desc', ''),
                "predicted_base_tariff":      base_tariff,
                "tariff_by_kelas":            self._calculate_tariff_by_kelas(base_tariff),
                "mdc_confidence":             round(mdc_conf, 4),
                "severity_confidence":        round(sev_conf, 4),
                "lookup_method":              cbg_info.get('lookup_method', 'none'),
                "shap_explanation":           shap_exp,
                "status":                     "success",
            }
        except Exception as exc:
            logger.exception("SurrogateGrouper.predict failed")
            return {"status": "error", "error": str(exc)}

    # ── Feature engineering ───────────────────────────────────────────────────
    def _derive_features(self, raw: dict) -> pd.DataFrame:
        """
        Derive all features from clinical input, matching training pipeline exactly.
        Returns DataFrame with encoded features PLUS raw helper columns (suffixed _raw).
        """
        preproc      = self._preproc
        freq_maps    = preproc['freq_maps']
        label_encs   = preproc['label_encoders']
        feature_cols = preproc['feature_cols']

        # ── Normalise raw inputs ──────────────────────────────────────────────
        primary_icd = str(raw.get('primary_icd10', '') or '').strip().upper() or 'UNK'
        inacbg_icd  = str(raw.get('inacbg_icd10',  '') or '').strip().upper() or primary_icd
        icd9_proc   = str(raw.get('icd9_procedure', '') or '').strip().upper()
        icd9_proc   = icd9_proc if icd9_proc and icd9_proc != 'NAN' else None

        care_type_s  = str(raw.get('care_type', 'outp')).strip().lower()
        entry_type_s = str(raw.get('entry_type', 'outp')).strip().lower()
        kelas_s      = str(raw.get('kelas', 'kelas_3')).strip().lower()
        episodes     = min(float(raw.get('episodes', 1) or 1), 10.0)

        care_type_int = self.CARE_TYPE_STR_MAP.get(care_type_s, 2)  # default outp

        # ── Derived boolean/text features ────────────────────────────────────
        icd_chapter   = primary_icd[0] if primary_icd and primary_icd[0].isalpha() else 'X'
        icd_block     = primary_icd[:3] if primary_icd != 'UNK' else 'UNK'
        is_z_code     = int(primary_icd.startswith('Z'))
        is_r_code     = int(primary_icd.startswith('R'))
        is_outpatient = int(care_type_int == 2)
        has_procedure = int(bool(icd9_proc))
        icd_match     = int(primary_icd == inacbg_icd)

        # ── Frequency encoding ────────────────────────────────────────────────
        def freq_encode(col, value):
            if value is None:
                value = '__missing__'
            return freq_maps.get(col, {}).get(value, 0.0)

        idrg_icd10_freq   = freq_encode('idrg_primary_icd10', primary_icd)
        icd9_freq         = freq_encode('idrg_icd9_procedure', icd9_proc or '__missing__')
        inacbg_icd10_freq = freq_encode('inacbg_primary_icd10', inacbg_icd)
        icd_block_freq    = freq_encode('icd_block', icd_block)

        # ── Label encoding ────────────────────────────────────────────────────
        def label_encode(col, value):
            le = label_encs.get(col)
            if le is None:
                return 0
            val_str = str(value).strip().lower() if col != 'icd_chapter' else str(value).strip().upper()
            if val_str not in le.classes_:
                return 0  # unseen → 0
            return int(le.transform([val_str])[0])

        icd_chapter_enc  = label_encode('icd_chapter', icd_chapter)
        care_type_enc    = label_encode('care_type_str', care_type_s)
        entry_type_enc   = label_encode('entry_type', entry_type_s)
        kelas_enc        = label_encode('kelas', kelas_s)

        # ── Assemble feature row in training column order ─────────────────────
        col_map = {
            'idrg_primary_icd10':  idrg_icd10_freq,
            'idrg_icd9_procedure': icd9_freq,
            'inacbg_primary_icd10': inacbg_icd10_freq,
            'icd_block':           icd_block_freq,
            'icd_chapter':         icd_chapter_enc,
            'care_type_str':       care_type_enc,
            'entry_type':          entry_type_enc,
            'kelas':               kelas_enc,
            'is_z_code':           is_z_code,
            'is_r_code':           is_r_code,
            'is_outpatient':       is_outpatient,
            'has_procedure':       has_procedure,
            'icd_match':           icd_match,
            'episodes':            episodes,
        }
        row = {col: col_map.get(col, 0.0) for col in feature_cols}

        # Attach raw helper columns (not used in model, used in lookup)
        row['icd_block_raw']   = icd_block
        row['care_type_raw']   = care_type_s
        row['kelas_raw']       = kelas_s

        return pd.DataFrame([row])

    # ── Stage 1: MDC predictor ────────────────────────────────────────────────
    def _predict_mdc(self, features_df: pd.DataFrame):
        feature_cols = self._preproc['feature_cols']
        X = features_df[feature_cols].values
        proba = self._mdc_clf.predict_proba(X)[0]
        idx   = int(np.argmax(proba))
        return self._mdc_le.classes_[idx], float(proba[idx])

    # ── Stage 2: Severity predictor ───────────────────────────────────────────
    def _predict_severity(self, features_df: pd.DataFrame):
        feature_cols = self._preproc['feature_cols']
        X = features_df[feature_cols].values
        proba = self._sev_clf.predict_proba(X)[0]
        idx   = int(np.argmax(proba))
        return self._sev_le.classes_[idx], float(proba[idx])

    # ── Stage 3: CBG lookup (3-level fallback) ────────────────────────────────
    def _lookup_cbg(self, icd_block: str, care_type: str, kelas: str,
                    severity: str, mdc_letter: str) -> dict:
        # Normalise kelas key to training format
        kelas_key = kelas if kelas.startswith('kelas_') else f'kelas_{kelas}'

        # Primary: exact (icd_block, care_type, kelas, severity)
        primary = self._lookup.get('primary', {})
        key1 = (icd_block, care_type, kelas_key, severity)
        if key1 in primary:
            return {**primary[key1], 'lookup_method': 'exact'}

        # Fallback 1: (mdc_letter, severity, kelas)
        fb1 = self._lookup.get('fallback_mdc_sev_kelas', {})
        key2 = (mdc_letter, severity, kelas_key)
        if key2 in fb1:
            return {**fb1[key2], 'lookup_method': 'fallback_mdc_sev_kelas'}

        # Fallback 2: (mdc_letter, severity) — ignore kelas
        fb2 = self._lookup.get('fallback_mdc_sev', {})
        key3 = (mdc_letter, severity)
        if key3 in fb2:
            return {**fb2[key3], 'lookup_method': 'fallback_mdc_sev'}

        return {
            'cbg_code': f'{mdc_letter}-?-?-{severity}',
            'base_tariff': 0.0,
            'cbg_desc': '',
            'lookup_method': 'none',
        }

    # ── Tariff by kelas ───────────────────────────────────────────────────────
    def _calculate_tariff_by_kelas(self, base_tariff_kelas3: float) -> dict:
        return {
            kelas: round(base_tariff_kelas3 * mult)
            for kelas, mult in self.KELAS_MULTIPLIERS.items()
        }

    # ── SHAP explanation (uses XGBoost feature_importances_ fallback) ─────────
    def _get_shap_explanation(self, features_df: pd.DataFrame) -> list:
        try:
            import shap
            feature_cols = self._preproc['feature_cols']
            X = features_df[feature_cols].values
            explainer  = shap.TreeExplainer(self._mdc_clf)
            shap_vals  = explainer.shap_values(X)      # list of arrays (one per class)
            # Use max absolute SHAP across all MDC classes for feature ranking
            shap_abs = np.abs(np.array(shap_vals)).max(axis=0)[0]   # shape (n_features,)
            indices  = np.argsort(shap_abs)[::-1][:3]
            result = []
            for idx in indices:
                val = float(shap_abs[idx])
                result.append({
                    "feature":   feature_cols[idx],
                    "impact":    round(val, 4),
                    "direction": "positive" if val >= 0 else "negative",
                })
            return result
        except Exception:
            # Fallback: use feature_importances_ from XGBoost
            top3 = self._mdc_fi.head(3)
            return [
                {"feature": feat, "impact": round(float(score), 4), "direction": "positive"}
                for feat, score in top3.items()
            ]
