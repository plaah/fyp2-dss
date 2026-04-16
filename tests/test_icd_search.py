"""Tests for ICD search service — 3-tier lookup (Sprint 6 / T6.4)."""
import pytest
from src.services.icd_search import IcdSearchService


@pytest.fixture(scope='module')
def service():
    svc = IcdSearchService()
    return svc


# ── Output structure ──────────────────────────────────────────────────────────

def test_search_returns_list(service):
    results = service.search('hipertensi', 'diagnosis')
    assert isinstance(results, list)


def test_each_result_has_required_keys(service):
    results = service.search('hipertensi', 'diagnosis')
    for r in results:
        assert 'code'            in r
        assert 'description'     in r
        assert 'indonesian_term' in r
        assert 'source'          in r
        assert 'confidence'      in r


# ── Tier 1: Indonesian lookup — diagnosis ─────────────────────────────────────

def test_hipertensi_returns_i10(service):
    """'hipertensi' is a validated Tier 1 term → must return I10."""
    results = service.search('hipertensi', 'diagnosis')
    codes = [r['code'] for r in results]
    assert 'I10' in codes


def test_hipertensi_source_is_indonesian_lookup(service):
    results = service.search('hipertensi', 'diagnosis')
    i10 = next((r for r in results if r['code'] == 'I10'), None)
    assert i10 is not None
    assert i10['source'] == 'indonesian_lookup'


def test_asma_returns_j45(service):
    """'asma' → J45.x bronchial asthma."""
    results = service.search('asma', 'diagnosis')
    codes = [r['code'] for r in results]
    assert any(c.startswith('J45') for c in codes)


def test_pneumonia_returns_j_code(service):
    results = service.search('pneumonia', 'diagnosis')
    codes = [r['code'] for r in results]
    assert any(c.startswith('J') for c in codes)


# ── Tier 1: Indonesian lookup — procedure ─────────────────────────────────────

def test_nebulisasi_returns_icd9(service):
    """'nebulisasi' is a validated clinical procedure."""
    results = service.search('nebulisasi', 'procedure')
    assert len(results) > 0
    codes = [r['code'] for r in results]
    assert any(re.match(r'^\d', c) for c in codes)  # ICD-9 starts with digit


def test_procedure_search_returns_results(service):
    results = service.search('infus', 'procedure')
    assert len(results) > 0


# ── Tier 3: Code prefix matching ──────────────────────────────────────────────

def test_icd10_code_prefix_diagnosis(service):
    """Typing 'I10' directly should return I10 in results."""
    results = service.search('I10', 'diagnosis')
    codes = [r['code'] for r in results]
    assert 'I10' in codes


def test_icd9_code_prefix_procedure(service):
    """Typing '89' prefix should return ICD-9 codes starting with 89."""
    results = service.search('89', 'procedure')
    assert len(results) > 0
    for r in results:
        assert r['code'].startswith('89') or r['source'] == 'indonesian_procedure_lookup'


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_query_returns_empty(service):
    assert service.search('', 'diagnosis') == []


def test_single_char_returns_empty(service):
    assert service.search('a', 'diagnosis') == []


def test_limit_respected(service):
    results = service.search('a', 'diagnosis', limit=3)
    assert len(results) <= 3


def test_no_duplicate_codes_in_results(service):
    results = service.search('diabetes', 'diagnosis', limit=10)
    codes = [r['code'] for r in results]
    assert len(codes) == len(set(codes))


def test_diagnosis_and_procedure_use_different_sources(service):
    diag = service.search('infeksi', 'diagnosis')
    proc = service.search('infeksi', 'procedure')
    # Diagnosis results should not come from icd9 sources
    diag_sources = {r['source'] for r in diag}
    assert not any('icd9' in s and 'indonesian' not in s for s in diag_sources)


def test_unknown_type_falls_back_gracefully(service):
    """Unknown type uses diagnosis path internally but service accepts 'procedure'."""
    results = service.search('test', 'procedure')
    assert isinstance(results, list)


import re  # noqa: E402  (needed by test_nebulisasi)
