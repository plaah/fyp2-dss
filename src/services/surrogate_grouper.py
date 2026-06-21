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

    # Deterministic ICD-10 chapter → MDC letter (INACBG design rule).
    # None = no override: model prediction is kept as-is for ambiguous chapters.
    # Z, R, Q intentionally excluded: INACBG assigns them non-conventionally
    # (e.g. Z09 follow-up → MDC Q, not MDC Z).
    CHAPTER_TO_MDC_RULE = {
        'A': 'A',  # Infectious diseases
        'B': 'A',  # Viral infections → MDC A (same group in INA-CBGs)
        'C': 'B',  # Malignant neoplasms
        'D': 'D',  # Blood and immune disorders
        'E': 'E',  # Endocrine, nutritional, metabolic
        'F': 'F',  # Mental and behavioural
        'G': 'G',  # Nervous system
        'H': 'H',  # Eye and ENT
        'I': 'I',  # Circulatory system
        'J': 'J',  # Respiratory system
        'K': 'K',  # Digestive system
        'L': 'L',  # Skin and subcutaneous tissue
        'M': 'M',  # Musculoskeletal and connective tissue
        'N': 'N',  # Genitourinary system
        'O': 'O',  # Pregnancy, childbirth, puerperium
        'S': 'S',  # Injuries and trauma
        'T': 'S',  # Poisoning / injury continued → MDC S
        # Excluded (no deterministic rule):
        # 'P' — excluded from training (neonatal)
        # 'Q' — congenital malformations; INA-CBGs may route elsewhere
        # 'R' — symptoms/signs: ambiguous, model is better
        # 'U' — special-purpose codes
        # 'V','W','X','Y' — external causes; INA-CBGs may use MDC S or other
        # 'Z' — Z-codes → model assigns correctly (Z09 → Q, etc.)
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
        self._pair_counts    = {}     # (icd_block, icd9_proc) → count for B5 rarity
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
            # B5: pair-count index for combination rarity detection
            try:
                train_path = os.path.join(BASE_DIR, "data", "clinical_training_data.csv")
                train_df = pd.read_csv(train_path, usecols=['icd_block', 'idrg_icd9_procedure'])
                train_df['idrg_icd9_procedure'] = train_df['idrg_icd9_procedure'].fillna('__none__')
                self._pair_counts = (
                    train_df.groupby(['icd_block', 'idrg_icd9_procedure'])
                    .size()
                    .to_dict()
                )
            except Exception:
                self._pair_counts = {}

            self._loaded = True
            logger.info("SurrogateGrouper: models loaded successfully")
        except Exception as exc:
            logger.error(f"SurrogateGrouper: failed to load models — {exc}")
            raise

    def reload(self):
        """Force reload of all model artifacts from disk atomically without downtime."""
        try:
            mdc_clf  = pickle.load(open(os.path.join(MODELS_DIR, "mdc_predictor.pkl"),        "rb"))
            sev_clf  = pickle.load(open(os.path.join(MODELS_DIR, "severity_predictor.pkl"),   "rb"))
            mdc_le   = pickle.load(open(os.path.join(MODELS_DIR, "mdc_label_encoder.pkl"),    "rb"))
            sev_le   = pickle.load(open(os.path.join(MODELS_DIR, "severity_label_encoder.pkl"), "rb"))
            lookup   = pickle.load(open(os.path.join(MODELS_DIR, "cbg_lookup_table.pkl"),     "rb"))
            preproc  = pickle.load(open(os.path.join(MODELS_DIR, "surrogate_preprocessing.pkl"), "rb"))
            mdc_fi   = pd.Series(
                mdc_clf.feature_importances_,
                index=preproc['feature_cols']
            ).sort_values(ascending=False)
            
            try:
                train_path = os.path.join(BASE_DIR, "data", "clinical_training_data.csv")
                train_df = pd.read_csv(train_path, usecols=['icd_block', 'idrg_icd9_procedure'])
                train_df['idrg_icd9_procedure'] = train_df['idrg_icd9_procedure'].fillna('__none__')
                pair_counts = (
                    train_df.groupby(['icd_block', 'idrg_icd9_procedure'])
                    .size()
                    .to_dict()
                )
            except Exception:
                pair_counts = {}

            # Atomic swap
            self._mdc_clf  = mdc_clf
            self._sev_clf  = sev_clf
            self._mdc_le   = mdc_le
            self._sev_le   = sev_le
            self._lookup   = lookup
            self._preproc  = preproc
            self._mdc_fi   = mdc_fi
            self._pair_counts = pair_counts
            self._loaded   = True
            logger.info("SurrogateGrouper: models reloaded atomically successfully")
        except Exception as exc:
            logger.error(f"SurrogateGrouper: failed to reload models — {exc}")
            raise

    # ── Public API ────────────────────────────────────────────────────────────
    def predict(self, clinical_input: dict) -> dict:
        """
        Predict CBG code and base tariff from clinical inputs.

        Args:
            clinical_input: {
                "primary_icd10": str,          # e.g. "I10"
                "icd9_procedure": str,         # e.g. "89.09" (optional, legacy single)
                "icd9_procedures": list[str],   # e.g. ["89.09", "39.95"] (optional, multi)
                "secondary_icd10": list[str],   # e.g. ["E11.9", "I10"] (optional)
                "inacbg_icd10": str,           # e.g. "I10" (optional, defaults to primary_icd10)
                "care_type": str,              # "outp" | "inp" | "emd" | "gp"
                "entry_type": str,             # "gp" | "outp" | "emd" | "inp" | ...
                "kelas": str,                  # "kelas_1" | "kelas_2" | "kelas_3"
                "episodes": int,               # default 1
            }

        Returns:
            Prediction dict with CBG code, tariff, MDC/severity predictions,
            confidence scores, lookup method, SHAP explanation, and multi-code analysis.
        """
        self._load()
        try:
            # ── Extract multi-code inputs (backward-compatible) ───────────
            secondary_icd10 = [s.strip().upper() for s in clinical_input.get('secondary_icd10', []) if s and s.strip()]
            icd9_procedures = [s.strip().upper() for s in clinical_input.get('icd9_procedures', []) if s and s.strip()]
            # Legacy single icd9_procedure fallback
            if not icd9_procedures:
                single_proc = str(clinical_input.get('icd9_procedure', '') or '').strip().upper()
                if single_proc and single_proc != 'NAN':
                    icd9_procedures = [single_proc]

            # ── Core ML prediction: uses primary_icd10 + first procedure ──
            features_df = self._derive_features(clinical_input)
            mdc_letter, mdc_conf   = self._predict_mdc(features_df)
            severity,   sev_conf   = self._predict_severity(features_df)
            icd_block    = features_df['icd_block_raw'].iloc[0]
            care_type_s  = features_df['care_type_raw'].iloc[0]
            kelas        = features_df['kelas_raw'].iloc[0]

            # Apply deterministic chapter → MDC rule to correct model errors
            primary_icd = str(clinical_input.get('primary_icd10', '') or '').strip().upper()
            mdc_letter, mdc_source = self._apply_chapter_rule(
                mdc_letter, mdc_conf, primary_icd
            )

            cbg_info     = self._lookup_cbg(icd_block, care_type_s, kelas, severity, mdc_letter)
            base_tariff  = cbg_info.get('base_tariff', 0.0)
            shap_exp     = self._get_shap_explanation(features_df)

            # B5: combination rarity (min rarity across all primary × procedure pairs)
            if icd9_procedures:
                rarities = []
                for proc in icd9_procedures:
                    proc_key = proc if proc and proc not in ('', 'NAN') else '__none__'
                    rarities.append(int(self._pair_counts.get((icd_block, proc_key), 0)))
                combination_rarity = min(rarities) if rarities else 0
            else:
                combination_rarity = int(self._pair_counts.get((icd_block, '__none__'), 0))

            # ── Multi-code enrichment ─────────────────────────────────────
            secondary_analysis = self._analyze_secondary_diagnoses(
                primary_icd, secondary_icd10, mdc_letter, severity
            )
            procedure_analysis = self._analyze_procedures(
                primary_icd, icd9_procedures
            )

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
                "mdc_source":                 mdc_source,
                "shap_explanation":           shap_exp,
                "combination_rarity":         combination_rarity,
                "alternative_cbgs":           self._get_alternatives(mdc_letter, severity, kelas),
                "secondary_diagnoses":        secondary_icd10,
                "procedures":                 icd9_procedures,
                "secondary_analysis":         secondary_analysis,
                "procedure_analysis":         procedure_analysis,
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

    # ── Chapter rule override ─────────────────────────────────────────────────
    def _apply_chapter_rule(self, ml_mdc: str, ml_conf: float, primary_icd: str):
        """
        Apply deterministic ICD chapter → MDC rule.
        Returns (final_mdc, source) where source is 'ml_model' or 'chapter_rule'.
        Rule only fires when the chapter has a deterministic mapping AND the ML
        prediction disagrees (or confidence < 0.80 for unambiguous chapters).
        """
        if not primary_icd or len(primary_icd) < 1:
            return ml_mdc, 'ml_model'
        chapter = primary_icd[0].upper()
        rule_mdc = self.CHAPTER_TO_MDC_RULE.get(chapter)
        if rule_mdc is None:
            # No deterministic rule for this chapter (Z, R, Q, etc.) — trust model
            return ml_mdc, 'ml_model'
        if ml_mdc == rule_mdc:
            return ml_mdc, 'ml_model'
        # Disagreement: override if ml confidence < 0.80, otherwise prefer rule
        # (rule is deterministic by INACBG spec; ML can be wrong for rare codes)
        return rule_mdc, 'chapter_rule'

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

    # ── B4: Alternative CBG suggestions ──────────────────────────────────────
    def _get_alternatives(self, mdc_letter: str, severity: str, kelas: str) -> list:
        """Return up to 2 alternative CBGs by varying severity (adjacent first)."""
        all_severities = ['0', 'I', 'II', 'III']
        try:
            current_idx = all_severities.index(severity)
        except ValueError:
            return []

        # Adjacent severities first (up then down), then fill remaining
        candidates = []
        if current_idx + 1 < len(all_severities):
            candidates.append(all_severities[current_idx + 1])
        if current_idx - 1 >= 0:
            candidates.append(all_severities[current_idx - 1])
        for s in all_severities:
            if s != severity and s not in candidates:
                candidates.append(s)

        kelas_key = kelas if kelas.startswith('kelas_') else f'kelas_{kelas}'
        fb1 = self._lookup.get('fallback_mdc_sev_kelas', {})
        fb2 = self._lookup.get('fallback_mdc_sev', {})

        alternatives = []
        for alt_sev in candidates:
            if len(alternatives) >= 2:
                break
            entry, basis = None, ''
            key1 = (mdc_letter, alt_sev, kelas_key)
            if key1 in fb1:
                entry = fb1[key1]
                basis = f"MDC {mdc_letter}, Severity {alt_sev}"
            else:
                key2 = (mdc_letter, alt_sev)
                if key2 in fb2:
                    entry = fb2[key2]
                    basis = f"MDC {mdc_letter}, Severity {alt_sev} (estimasi)"
            if entry and entry.get('cbg_code') and float(entry.get('base_tariff', 0)) > 0:
                alternatives.append({
                    "cbg_code":      entry.get('cbg_code', ''),
                    "base_tariff":   float(entry.get('base_tariff', 0)),
                    "severity":      alt_sev,
                    "severity_label": self.SEVERITY_LABELS.get(alt_sev, alt_sev),
                    "basis":         basis,
                })
        return alternatives

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

    # ── Multi-code analysis: secondary diagnoses ───────────────────────────
    # Known severity escalator chapters (common comorbidities that may raise
    # INA-CBGs severity): E=Endocrine/DM, I=Cardiovascular, N=Renal
    ESCALATOR_CHAPTERS = {'E', 'I', 'N'}

    def _analyze_secondary_diagnoses(self, primary_icd: str,
                                      secondaries: list,
                                      mdc_letter: str,
                                      severity: str) -> dict:
        """Analyze secondary diagnoses for comorbidity and severity signals."""
        if not secondaries:
            return {"has_secondaries": False}

        primary_chapter = primary_icd[0].upper() if primary_icd else ''
        chapters = {primary_chapter} if primary_chapter else set()
        secondary_chapters = []
        for code in secondaries:
            ch = code[0].upper() if code else ''
            if ch:
                chapters.add(ch)
                secondary_chapters.append(ch)

        escalator_hits = set(secondary_chapters) & self.ESCALATOR_CHAPTERS
        # Remove primary chapter from escalator hits (only secondary comorbidities)
        escalator_hits -= {primary_chapter}
        has_escalator = bool(escalator_hits)

        return {
            "has_secondaries":     True,
            "count":               len(secondaries),
            "distinct_chapters":   len(chapters),
            "chapter_list":        sorted(chapters),
            "has_comorbidity":     len(chapters) >= 2,
            "has_escalator":       has_escalator,
            "escalator_chapters":  sorted(escalator_hits),
            "severity_warning":    has_escalator and severity in ('0', 'I'),
        }

    # ── Multi-code analysis: procedures ───────────────────────────────────
    def _analyze_procedures(self, primary_icd: str,
                            procedures: list) -> dict:
        """Analyze procedure list for consistency and coverage."""
        if not procedures:
            return {"has_procedures": False, "count": 0}

        return {
            "has_procedures": True,
            "count":          len(procedures),
            "codes":          procedures,
        }
