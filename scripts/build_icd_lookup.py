"""
Build Indonesian ICD Lookup Tables
====================================
Run once to generate validated lookup CSVs from backtesting and clinical data.
Outputs:
  data/indonesian_icd10_lookup.csv  — Indonesian diagnosis → ICD-10
  data/indonesian_icd9_lookup.csv   — Indonesian procedure → ICD-9

Run: python scripts/build_icd_lookup.py
"""

import pandas as pd
import re
import os


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_icd10_code(code_str):
    """Extract first valid ICD-10 code from cell (handles 'E11.9, I11.9' and 'I51./Q21.1')."""
    if pd.isna(code_str):
        return None
    # Split on comma or slash separators
    for c in re.split(r'[,/]', str(code_str)):
        c = c.strip().rstrip('.')
        if re.match(r'^[A-Z]\d{2}', c):
            return c
    return None


def clean_term(text):
    """Normalize Indonesian diagnosis/procedure text."""
    if pd.isna(text):
        return None
    text = str(text).lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.strip('"\'')
    return text if len(text) > 1 else None


def clean_icd9_code(code):
    """Validate ICD-9-CM procedure code format."""
    if pd.isna(code):
        return None
    code = str(code).strip()
    if re.match(r'^\d{2}\.?\d*$', code):
        return code
    return None


# ── Step 0 — Curated Alias Table (top 20 most-searched Indonesian terms) ──────

CURATED_ALIASES = [
    ('diabetes',        'E11.9', 'Type 2 diabetes mellitus, unspecified'),
    ('diabetes melitus', 'E11.9', 'Type 2 diabetes mellitus, unspecified'),
    ('dm tipe 2',       'E11.9', 'Type 2 diabetes mellitus, unspecified'),
    ('dm',              'E11.9', 'Diabetes mellitus'),
    ('demam',           'R50.9', 'Fever, unspecified'),
    ('tipes',           'A01.0', 'Typhoid fever'),
    ('tifoid',          'A01.0', 'Typhoid fever'),
    ('typhoid',         'A01.0', 'Typhoid fever'),
    ('diare',           'A09.9', 'Gastroenteritis and colitis of unspecified origin'),
    ('stroke',          'I64',   'Stroke, not specified as haemorrhage or infarction'),
    ('gerd',            'K21.9', 'Gastro-oesophageal reflux disease without oesophagitis'),
    ('asam urat',       'M10.9', 'Gout, unspecified'),
    ('maag',            'K29.7', 'Gastritis, unspecified'),
    ('batu ginjal',     'N20.0', 'Calculus of kidney'),
    ('sesak napas',     'R06.0', 'Dyspnoea'),
    ('kejang',          'R56.8', 'Other and unspecified convulsions'),
    ('anemia',          'D64.9', 'Anaemia, unspecified'),
    ('usus buntu',      'K37',   'Unspecified diseases of appendix'),
    ('katarak',         'H26.9', 'Cataract, unspecified'),
    ('tumor',           'D48.9', 'Neoplasm of uncertain behaviour, unspecified'),
    ('kista',           'N83.2', 'Other and unspecified ovarian cysts'),
    ('hernia',          'K46.9', 'Unspecified abdominal hernia without obstruction'),
    ('wasir',           'K64.9', 'Unspecified haemorrhoids'),
    ('sakit kepala',    'R51',   'Headache'),
    ('hipertensi',      'I10',   'Essential (primary) hypertension'),
    ('pneumonia',       'J18.9', 'Pneumonia, unspecified'),
    ('bronkitis',       'J40',   'Bronchitis, not specified as acute or chronic'),
    ('asma',            'J45.9', 'Asthma, unspecified'),
    ('infeksi saluran kemih', 'N39.0', 'Urinary tract infection, site not specified'),
    ('isk',             'N39.0', 'Urinary tract infection, site not specified'),
]


def build_icd10_from_tamtech():
    """Mine idrg_primary_icd10_desc from tamtech_raw for additional Indonesian terms."""
    raw_path = 'data/tamtech_raw_extract.csv'
    if not os.path.exists(raw_path):
        print("  [Step 0] tamtech_raw_extract.csv not found, skipping.")
        return []

    raw = pd.read_csv(raw_path, usecols=['idrg_primary_icd10', 'idrg_primary_icd10_desc'], low_memory=False)
    raw = raw.dropna(subset=['idrg_primary_icd10', 'idrg_primary_icd10_desc'])
    raw['code_clean'] = raw['idrg_primary_icd10'].apply(clean_icd10_code)
    raw['term_clean'] = raw['idrg_primary_icd10_desc'].apply(clean_term)
    raw = raw.dropna(subset=['code_clean', 'term_clean'])
    raw = raw[raw['term_clean'].str.len() > 2]

    # Keep most common ICD-10 code per description
    pairs = (raw.groupby('term_clean')['code_clean']
               .agg(lambda x: x.value_counts().index[0])
               .reset_index()
               .rename(columns={'term_clean': 'indonesian_term', 'code_clean': 'icd10_code'}))

    records = []
    for _, row in pairs.iterrows():
        records.append({
            'indonesian_term': row['indonesian_term'],
            'icd10_code':      row['icd10_code'],
            'description_en':  '',
            'confidence':      'medium',
            'source':          'tamtech_raw',
        })
    print(f"  [Step 0] Tamtech raw descriptions mined: {len(records)} terms")
    return records


# ── T6.1 Step 1 — ICD-10 Indonesian Lookup from Backtesting Data ─────────────

def build_icd10_lookup():
    dec_path = 'data/Backtesting Results - Stage 1 - 12_12_2025.csv'
    apr_path = 'data/Backtesting Results - Testing 01_04_2026.csv'

    dec_records = []
    apr_records = []

    # Process December backtesting
    dec = pd.read_csv(dec_path)
    print(f"Dec backtesting: {len(dec)} rows, cols={dec.columns.tolist()}")
    for _, row in dec.iterrows():
        term = clean_term(row['Diagnosa'])
        code = clean_icd10_code(row['Kode ICD-10 (benar)'])
        result = str(row.get('Result type', '')).strip()
        if term and code:
            confidence = 'high' if result == 'Exact Match' else 'medium'
            dec_records.append({
                'indonesian_term': term,
                'icd10_code': code,
                'description_en': '',
                'confidence': confidence,
                'source': 'backtesting_dec_2025',
            })

    # Process April backtesting
    apr = pd.read_csv(apr_path)
    print(f"Apr backtesting: {len(apr)} rows, cols={apr.columns.tolist()}")
    for _, row in apr.iterrows():
        term = clean_term(row['Diagnosa'])
        code = clean_icd10_code(row['Kode ICD-10 (benar)'])
        result = str(row.get('Result type', '')).strip()
        desc = str(row.get('Deskripsi', '')).strip() if pd.notna(row.get('Deskripsi')) else ''
        if term and code:
            confidence = 'high' if result == 'Exact Match' else 'medium'
            apr_records.append({
                'indonesian_term': term,
                'icd10_code': code,
                'description_en': desc,
                'confidence': confidence,
                'source': 'backtesting_apr_2026',
            })

    # Step 0a: tamtech raw descriptions
    tamtech_records = build_icd10_from_tamtech()

    # Step 0b: curated alias table (highest priority)
    alias_records = [
        {
            'indonesian_term': term,
            'icd10_code':      code,
            'description_en':  desc,
            'confidence':      'high',
            'source':          'curated_alias',
        }
        for term, code, desc in CURATED_ALIASES
    ]

    # Merge all sources: alias > backtesting > tamtech (priority order)
    all_records = alias_records + dec_records + apr_records + tamtech_records
    df = pd.DataFrame(all_records)

    # Deduplicate: for same term, keep highest confidence entry (alias wins)
    source_priority = {'curated_alias': 0, 'backtesting_dec_2025': 1, 'backtesting_apr_2026': 1, 'tamtech_raw': 2}
    df['src_rank']  = df['source'].map(source_priority).fillna(3)
    df['conf_rank'] = df['confidence'].map({'high': 0, 'medium': 1}).fillna(2)
    df = (df.sort_values(['conf_rank', 'src_rank'])
            .drop_duplicates(subset='indonesian_term', keep='first')
            .drop(['conf_rank', 'src_rank'], axis=1)
            .reset_index(drop=True))

    # Sort: high confidence first
    df = df.sort_values('confidence', ascending=True).reset_index(drop=True)

    df.to_csv('data/indonesian_icd10_lookup.csv', index=False)
    print(f"\nICD-10 lookup saved: {len(df)} unique terms")
    print(f"  High confidence: {(df['confidence'] == 'high').sum()}")
    print(f"  Medium confidence: {(df['confidence'] == 'medium').sum()}")
    print(df.head(10).to_string())
    return df


# ── T6.1 Step 2 — ICD-9 Indonesian Lookup from Tindakan Data ─────────────────

def build_icd9_lookup():
    tindakan_path = 'data/Data Tindakan ICD-9 - Data Tindakan ICD-9.csv'

    tindakan = pd.read_csv(tindakan_path, low_memory=False)
    print(f"\nTindakan data: {len(tindakan)} rows, cols={tindakan.columns.tolist()}")

    # Keep rows with both free text AND ICD-9 code
    noise_values = {
        '-', '0', 'nan', 'terlampir', 'medikamentosa', 'obat',
        'observasi', 'pemantauan', '', 'tidak ada', 'none',
    }

    proc = tindakan[
        tindakan['therapeutic_free_text'].notna() &
        tindakan['therapeutic_icd9'].notna()
    ][['therapeutic_free_text', 'therapeutic_icd9']].copy()

    proc['term_clean'] = proc['therapeutic_free_text'].apply(clean_term)
    proc['code_clean'] = proc['therapeutic_icd9'].apply(clean_icd9_code)
    proc = proc.dropna(subset=['term_clean', 'code_clean'])

    # Remove noise
    proc = proc[~proc['term_clean'].isin(noise_values)]
    proc = proc[proc['term_clean'].str.len() > 3]
    # Remove terms that start with non-letter characters (Excel errors, numbers, punctuation)
    proc = proc[proc['term_clean'].str.match(r'^[a-z]')]

    print(f"  Valid procedure records: {len(proc)}")
    print(f"  Unique terms: {proc['term_clean'].nunique()}")
    print(f"  Unique ICD-9 codes: {proc['code_clean'].nunique()}")

    # For duplicate terms: keep the most frequent ICD-9 code mapping
    icd9_lookup = (proc
        .groupby('term_clean')['code_clean']
        .agg(lambda x: x.value_counts().index[0])
        .reset_index()
        .rename(columns={'term_clean': 'indonesian_procedure',
                         'code_clean': 'icd9_code'})
    )
    icd9_lookup['source'] = 'tindakan_data'
    icd9_lookup['confidence'] = 'high'

    icd9_lookup.to_csv('data/indonesian_icd9_lookup.csv', index=False)
    print(f"\nICD-9 lookup saved: {len(icd9_lookup)} procedure terms")
    print(icd9_lookup.head(10).to_string())
    return icd9_lookup


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)

    print("=" * 60)
    print("  Building Indonesian ICD Lookup Tables")
    print("=" * 60)

    print("\n[Step 1] ICD-10 Diagnosis Lookup (backtesting data)...")
    icd10_df = build_icd10_lookup()

    print("\n[Step 2] ICD-9 Procedure Lookup (tindakan data)...")
    icd9_df = build_icd9_lookup()

    print("\n" + "=" * 60)
    print(f"=== T6.1 DONE === ICD-10:{len(icd10_df)} terms | ICD-9:{len(icd9_df)} terms ✅")
    print("=" * 60)
