"""
ICD Search Service — 3-tier priority lookup for Indonesian medical terms.

Tier 1 (highest priority): Indonesian lookup tables from validated
  backtesting data and clinical procedure records. These are the exact
  terms doctors use in practice. Exact match first, then contains match.

Tier 2: WHO ICD-10 alphabetical index (English) and ICD-9-CM reference.
  Used as fallback when Indonesian lookup has no match.

Tier 3: Raw ICD code prefix match. Allows doctors who know the code to
  type it directly (e.g. "I10" or "89.0" still works).

No external API calls. All lookup is local — fast, free, offline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd


class IcdSearchService:
    """3-tier ICD code search for Indonesian medical terminology."""

    def __init__(self):
        self._icd10_indonesian: pd.DataFrame | None = None
        self._icd9_indonesian: pd.DataFrame | None = None
        self._icd10_reference: pd.DataFrame | None = None
        self._icd9_reference: pd.DataFrame | None = None
        self._loaded = False

    def _load(self) -> None:
        """Lazy-load all lookup tables once."""
        if self._loaded:
            return
        base = Path('data')

        def _safe_read(path: Path, default_cols: list) -> pd.DataFrame:
            try:
                return pd.read_csv(path).fillna('')
            except FileNotFoundError:
                return pd.DataFrame(columns=default_cols)

        self._icd10_indonesian = _safe_read(
            base / 'indonesian_icd10_lookup.csv',
            ['indonesian_term', 'icd10_code', 'confidence'],
        )
        self._icd9_indonesian = _safe_read(
            base / 'indonesian_icd9_lookup.csv',
            ['indonesian_procedure', 'icd9_code', 'confidence'],
        )
        self._icd10_reference = _safe_read(
            base / 'icd10_2010_reference.csv',
            ['term_en', 'icd10_code'],
        )
        self._icd9_reference = _safe_read(
            base / 'icd9_cm_procedures.csv',
            ['code', 'description_en'],
        )
        self._loaded = True

    def search(self, query: str, search_type: str = 'diagnosis',
               limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search ICD codes by Indonesian term or code prefix.

        Args:
            query:       Indonesian medical term or ICD code prefix (min 2 chars)
            search_type: 'diagnosis' (ICD-10) or 'procedure' (ICD-9)
            limit:       max results to return

        Returns:
            list of dicts with keys:
              code, description, indonesian_term, source, confidence
        """
        self._load()
        q = str(query).strip()
        if len(q) < 2:
            return []

        if search_type == 'diagnosis':
            return self._search_icd10(q.lower(), limit)
        return self._search_icd9(q.lower(), limit)

    # ── ICD-10 (diagnosis) ────────────────────────────────────────────────────

    def _search_icd10(self, q: str, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        df = self._icd10_indonesian
        if not df.empty:
            # Tier 1a — exact match
            exact = df[df['indonesian_term'] == q]
            for _, row in exact.iterrows():
                results.append(self._icd10_row(row, 'indonesian_lookup',
                                               str(row.get('confidence', 'high'))))

            # Tier 1b — contains match
            if len(results) < limit:
                partial = df[
                    df['indonesian_term'].str.contains(q, na=False, regex=False) &
                    (df['indonesian_term'] != q)
                ].head(limit - len(results))
                for _, row in partial.iterrows():
                    results.append(self._icd10_row(row, 'indonesian_lookup',
                                                   str(row.get('confidence', 'medium'))))

        # Tier 2 — English ICD-10 reference
        ref = self._icd10_reference
        if len(results) < limit and not ref.empty:
            term_col = 'term_en' if 'term_en' in ref.columns else ref.columns[0]
            code_col = 'icd10_code' if 'icd10_code' in ref.columns else ref.columns[1]
            en = ref[ref[term_col].str.lower().str.contains(q, na=False, regex=False)]
            for _, row in en.head(limit - len(results)).iterrows():
                results.append({
                    'code':            str(row[code_col]).strip(),
                    'description':     str(row[term_col]),
                    'indonesian_term': '',
                    'source':          'icd10_reference',
                    'confidence':      'low',
                })

        # Tier 3 — raw ICD-10 code prefix (e.g. doctor types "I10")
        if len(results) < limit and re.match(r'^[a-zA-Z]\d', q):
            q_up = q.upper()
            ref2 = self._icd10_reference
            if not ref2.empty:
                code_col = 'icd10_code' if 'icd10_code' in ref2.columns else ref2.columns[1]
                term_col = 'term_en' if 'term_en' in ref2.columns else ref2.columns[0]
                matches = ref2[
                    ref2[code_col].str.upper().str.startswith(q_up, na=False)
                ].head(limit - len(results))
                for _, row in matches.iterrows():
                    results.append({
                        'code':            str(row[code_col]).strip(),
                        'description':     str(row[term_col]),
                        'indonesian_term': '',
                        'source':          'code_prefix',
                        'confidence':      'low',
                    })

        return self._dedup(results)[:limit]

    def _icd10_row(self, row: pd.Series, source: str, confidence: str) -> Dict[str, Any]:
        return {
            'code':            str(row['icd10_code']).strip(),
            'description':     str(row.get('description_en', '')),
            'indonesian_term': str(row['indonesian_term']),
            'source':          source,
            'confidence':      confidence,
        }

    # ── ICD-9 (procedure) ─────────────────────────────────────────────────────

    def _search_icd9(self, q: str, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        df = self._icd9_indonesian
        if not df.empty:
            term_col = 'indonesian_procedure' if 'indonesian_procedure' in df.columns else df.columns[0]
            code_col = 'icd9_code' if 'icd9_code' in df.columns else df.columns[1]

            # Tier 1a — exact match
            exact = df[df[term_col] == q]
            for _, row in exact.iterrows():
                results.append(self._icd9_row(row, term_col, code_col,
                                              'indonesian_procedure_lookup', 'high'))

            # Tier 1b — contains match
            if len(results) < limit:
                partial = df[
                    df[term_col].str.contains(q, na=False, regex=False) &
                    (df[term_col] != q)
                ].head(limit - len(results))
                for _, row in partial.iterrows():
                    results.append(self._icd9_row(row, term_col, code_col,
                                                  'indonesian_procedure_lookup', 'medium'))

        # Tier 2 — ICD-9-CM English reference
        ref = self._icd9_reference
        if len(results) < limit and not ref.empty:
            desc_col = 'description_en' if 'description_en' in ref.columns else ref.columns[1]
            code_col_r = 'code' if 'code' in ref.columns else ref.columns[0]
            en = ref[ref[desc_col].str.lower().str.contains(q, na=False, regex=False)]
            for _, row in en.head(limit - len(results)).iterrows():
                results.append({
                    'code':            str(row[code_col_r]).strip(),
                    'description':     str(row[desc_col]),
                    'indonesian_term': '',
                    'source':          'icd9_reference',
                    'confidence':      'low',
                })

        # Tier 3 — raw ICD-9 code prefix (e.g. "89.0")
        if len(results) < limit and re.match(r'^\d', q):
            ref2 = self._icd9_reference
            if not ref2.empty:
                code_col_r = 'code' if 'code' in ref2.columns else ref2.columns[0]
                desc_col = 'description_en' if 'description_en' in ref2.columns else ref2.columns[1]
                matches = ref2[
                    ref2[code_col_r].astype(str).str.startswith(q, na=False)
                ].head(limit - len(results))
                for _, row in matches.iterrows():
                    results.append({
                        'code':            str(row[code_col_r]).strip(),
                        'description':     str(row[desc_col]),
                        'indonesian_term': '',
                        'source':          'code_prefix',
                        'confidence':      'low',
                    })

        return self._dedup(results)[:limit]

    def _icd9_row(self, row: pd.Series, term_col: str, code_col: str,
                  source: str, confidence: str) -> Dict[str, Any]:
        return {
            'code':            str(row[code_col]).strip(),
            'description':     str(row[term_col]),
            'indonesian_term': str(row[term_col]),
            'source':          source,
            'confidence':      confidence,
        }

    # ── Shared ────────────────────────────────────────────────────────────────

    @staticmethod
    def _dedup(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate codes, keeping first occurrence (highest priority)."""
        seen: set = set()
        out = []
        for r in results:
            if r['code'] not in seen:
                seen.add(r['code'])
                out.append(r)
        return out


# Singleton — loaded once per Flask process
icd_search_service = IcdSearchService()
