# Save as scripts/extract_icd_reference.py
# Run: python scripts/extract_icd_reference.py

import pdfplumber
import re
import pandas as pd
import os
from collections import defaultdict


# ── ICD-9-CM Procedures ───────────────────────────────────────────────────────

def extract_icd9_procedures(pdf_path):
    """
    Extract ICD-9-CM procedure codes and descriptions.
    Pattern: code (e.g. 00.01) followed by description text.
    """
    records = []

    code_re = re.compile(r'^(\d{2}\.\d{1,2})\s+(.+)$')
    cat_re  = re.compile(r'^(\d{2}\.\d)\s+(.+)$')

    skip_prefixes = (
        'Excludes', 'Includes', 'Note', 'Code also',
        'Use additional', 'New code', 'Revised code',
        'ICD-9-CM', 'PROCEDURES', 'See also', 'Omit code',
    )

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[8:]:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split('\n'):
                line = line.strip()
                if not line or len(line) < 5:
                    continue
                if any(line.startswith(p) for p in skip_prefixes):
                    continue
                if re.match(r'^\d+$', line):
                    continue

                for pattern in [code_re, cat_re]:
                    m = pattern.match(line)
                    if m:
                        code = m.group(1).strip()
                        desc = re.sub(r'\s+', ' ', m.group(2)).strip().rstrip('®').strip()
                        if len(desc) > 3:
                            records.append({
                                'code': code,
                                'description_en': desc,
                                'category': 'icd9_procedure',
                            })
                        break

    return pd.DataFrame(records).drop_duplicates(subset='code')


# ── ICD-10 Volume 3 — word-level two-column extraction ────────────────────────

_ICD10_CODE = re.compile(r'^[A-Z]\d{2}\.?\d*[†*]?$')
_SKIP_WORDS = {'INTERNATIONAL', 'CLASSIFICATION', 'DISEASES', 'ALPHABETICAL',
               'INDEX', 'INJURY', 'NATURE', 'OF', 'TO', 'AND'}


def _row_to_entry(words: list, current_lead: str) -> tuple:
    """
    Convert a list of words (one column row, already x-sorted) into
    (full_term, code, new_lead_term).
    Returns (None, None, current_lead) when nothing useful is found.
    """
    if not words:
        return None, None, current_lead

    texts = [w['text'].rstrip('†*') for w in words]

    # Last token must be an ICD-10 code
    last = texts[-1]
    if not re.match(r'^[A-Z]\d{2}\.?\d*$', last):
        # No code — update lead term if this is a lead line
        raw = ' '.join(texts).strip()
        if raw and not raw.startswith('–') and not raw.startswith('-'):
            new_lead = raw.rstrip(',').strip()
            return None, None, new_lead
        return None, None, current_lead

    code = last
    term_parts = ' '.join(texts[:-1]).strip()

    # Determine indent level
    if term_parts.startswith('–') or term_parts.startswith('-'):
        sub = term_parts.lstrip('–- ').rstrip(',').strip()
        full_term = f"{current_lead}, {sub}" if current_lead else sub
        new_lead = current_lead
    else:
        full_term = term_parts.rstrip(',').strip()
        new_lead = full_term  # Update lead term

    full_term = re.sub(r'\s+', ' ', full_term).strip()

    if full_term and re.match(r'^[A-Z]\d{2}\.?\d*$', code):
        return full_term, code, new_lead
    return None, None, new_lead


def extract_icd10_index(pdf_path):
    """
    Extract ICD-10 Volume 3 alphabetical index using word-level extraction.
    Groups words by row (top coordinate) and separates left/right columns
    by x-coordinate (split at ~x=240 for this PDF's layout).
    """
    records = []
    COLUMN_SPLIT_X = 240  # Determined by inspecting word x0 values

    skip_pages = {'INTERNATIONAL CLASSIFICATION', 'ALPHABETICAL INDEX'}

    # Track lead terms independently per column across the page
    left_lead  = ''
    right_lead = ''

    with pdfplumber.open(pdf_path) as pdf:
        print(f"  ICD-10 V3: {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages[15:], start=16):
            if page_num > 662:
                break

            words = page.extract_words(keep_blank_chars=False)
            if not words:
                continue

            # Group words by row (round top to nearest 2px to handle sub-pixel drift)
            rows = defaultdict(list)
            for w in words:
                row_key = round(w['top'] / 2) * 2
                rows[row_key].append(w)

            for top in sorted(rows.keys()):
                row_words = sorted(rows[top], key=lambda w: w['x0'])

                # Skip header rows
                row_text = ' '.join(w['text'] for w in row_words)
                if any(h in row_text for h in skip_pages):
                    continue

                # Split into left and right column by x0
                left_words  = [w for w in row_words if w['x0'] < COLUMN_SPLIT_X]
                right_words = [w for w in row_words if w['x0'] >= COLUMN_SPLIT_X]

                # Process left column
                if left_words:
                    term, code, left_lead = _row_to_entry(left_words, left_lead)
                    if term and code:
                        records.append({'term_en': term, 'icd10_code': code,
                                        'category': 'icd10_diagnosis'})

                # Process right column
                if right_words:
                    term, code, right_lead = _row_to_entry(right_words, right_lead)
                    if term and code:
                        records.append({'term_en': term, 'icd10_code': code,
                                        'category': 'icd10_diagnosis'})

    df = pd.DataFrame(records).drop_duplicates(subset=['term_en', 'icd10_code'])
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)

    print("Extracting ICD-9-CM procedures...")
    icd9_df = extract_icd9_procedures(
        os.environ.get('ICD9_PDF', 'data/ICD9CM.pdf')
    )
    icd9_df.to_csv('data/icd9_cm_procedures.csv', index=False)
    print(f"  ICD-9 procedures: {len(icd9_df)} codes extracted")
    print(icd9_df.head(8).to_string())

    print("\nExtracting ICD-10 Volume 3 alphabetical index...")
    icd10_df = extract_icd10_index(
        os.environ.get('ICD10_PDF', 'data/icd10-V3.pdf')
    )
    icd10_df.to_csv('data/icd10_2010_reference.csv', index=False)
    print(f"\n  ICD-10 terms: {len(icd10_df)} entries extracted")
    print(icd10_df.head(12).to_string())

    # Spot-check a few known codes
    print("\n  Spot-check known codes:")
    known = ['I10', 'J18.0', 'E11', 'N20.0', 'K80.2', 'Z09']
    for c in known:
        matches = icd10_df[icd10_df['icd10_code'] == c]
        if not matches.empty:
            print(f"  {c}: {matches['term_en'].iloc[0]}")
        else:
            print(f"  {c}: NOT FOUND")

    print("\nDone. Files saved to data/")
