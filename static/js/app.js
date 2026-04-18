/**
 * DSS Casemix — Shared Application JavaScript
 * =============================================
 * Handles all API communication, DOM rendering, and Chart.js initialisation
 * for both the Prediction page (/) and the Analytics Dashboard (/dashboard).
 *
 * Architecture:
 *  - submitPrediction()    POST /api/v1/full-assessment → render results
 *  - loadStats()           GET  /api/v1/stats           → KPI cards + charts
 *  - loadRecentTable()     Renders recent predictions table
 *  - formatIDR(n)          Indonesian Rupiah formatter
 *  - getRiskBadgeHTML(r)   Returns colored badge HTML
 *  - initCharts()          Initialises all Chart.js instances
 *
 * NEUROVI INTEGRATION HOOK
 * When Neurovi HIS API reference is available:
 * 1. Replace manual form submission with Neurovi patient data fetch
 * 2. Auto-populate ICD codes from Neurovi encounter data
 * 3. Add patient context panel (anonymized: encounter_id only)
 * 4. Connect source='neurovi' flag in Prediction model
 * TODO: Awaiting Neurovi API documentation from Tamtech
 */

'use strict';

/* ── Constants ────────────────────────────────────────────────────────────── */
const API_BASE = '/api/v1';

const OUTCOME_LABELS = {
  grouping_valid:    'Grouping Valid',
  coding_incomplete: 'Coding Incomplete',
  grouping_invalid:  'Grouping Invalid',
};

const OUTCOME_ICONS = {
  grouping_valid:    '✅',
  coding_incomplete: '⚠️',
  grouping_invalid:  '❌',
};

const OUTCOME_CLASS = {
  grouping_valid:    'valid',
  coding_incomplete: 'incomplete',
  grouping_invalid:  'invalid',
};

/* ── Chart instances (module-level so they can be destroyed on re-render) ─── */
let _shapChart      = null;
let _donutChart     = null;
let _lineChart      = null;
let _riskChart      = null;
let _dashboardLoaded = false;
let _allPredictions  = [];   // cache for paginated table
let _currentPage     = 1;
const PAGE_SIZE      = 20;

/* ── ICD search debounce timers ────────────────────────────────────────────── */
let _diagTimer = null;
let _procTimer = null;

/* ══════════════════════════════════════════════════════════════════════════
   UTILITY FUNCTIONS
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Format a number as Indonesian Rupiah.
 * @param {number} amount
 * @returns {string}  e.g. "Rp 196.100"
 */
function formatIDR(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) return 'Rp 0';
  const abs = Math.abs(Math.round(amount));
  const formatted = abs.toLocaleString('id-ID');
  return (amount < 0 ? '-' : '') + 'Rp\u00a0' + formatted;
}

/**
 * Return a colored risk badge HTML string.
 * @param {string} risk  'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
 * @returns {string}
 */
function getRiskBadgeHTML(risk) {
  if (!risk) return '';
  return `<span class="risk-badge ${risk}">${risk}</span>`;
}

/**
 * Return prediction outcome badge HTML (big, centered).
 * @param {string} outcome
 * @returns {string}
 */
function getOutcomeBadgeHTML(outcome) {
  const cls   = OUTCOME_CLASS[outcome]  || 'valid';
  const icon  = OUTCOME_ICONS[outcome]  || '✅';
  const label = OUTCOME_LABELS[outcome] || outcome;
  return `<div class="outcome-badge ${cls}">
    <span class="outcome-icon">${icon}</span>
    <span>${label}</span>
  </div>`;
}

/**
 * Format a date string for display (HH:mm · DD/MM).
 * @param {string} iso  ISO 8601 string
 * @returns {string}
 */
function formatDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
  const time = d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
  const date = d.toLocaleDateString('id-ID', { day: '2-digit', month: '2-digit' });
  return `${time} · ${date}`;
}

/* ══════════════════════════════════════════════════════════════════════════
   API STATUS CHECK
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Check API health and update the sidebar status dot.
 */
async function checkApiStatus() {
  const dot  = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  try {
    const resp = await fetch(`${API_BASE}/health`);
    const data = await resp.json();
    if (data.status === 'ok') {
      if (dot)  { dot.className  = 'status-dot online'; }
      if (text) { text.textContent = `API online · ${data.model_name}`; }
    } else { throw new Error('not ok'); }
  } catch {
    if (dot)  { dot.className  = 'status-dot offline'; }
    if (text) { text.textContent = 'API offline'; }
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   ICD SEARCH — pill-based suggestion (replaces IcdSearchWidget)
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Fetch ICD search results and render as clickable pills.
 * @param {string} query         Search term (min 2 chars)
 * @param {string} type          'diagnosis' | 'procedure'
 * @param {string} pillsId       ID of the pills container div
 * @param {string} hiddenId      ID of the hidden input to store selected code
 * @param {Function|null} onSelect  Optional callback(item) after selection
 */
async function _fetchPills(query, type, pillsId, hiddenId, onSelect) {
  if (query.length < 2) {
    const c = document.getElementById(pillsId);
    if (c) c.innerHTML = '';
    return;
  }
  try {
    const res  = await fetch(`${API_BASE}/icd-search?q=${encodeURIComponent(query)}&type=${type}&limit=3`);
    const data = await res.json();
    _renderPills(data.results || [], pillsId, hiddenId, onSelect);
  } catch (err) {
    console.error('ICD search error:', err);
  }
}

/**
 * Render clickable suggestion pills into a container.
 * @param {Array}    results    Array of {code, description, indonesian_term, source, confidence}
 * @param {string}   containerId
 * @param {string}   hiddenId   Hidden input to store the selected code
 * @param {Function|null} onSelect  Optional callback(item)
 */
function _renderPills(results, containerId, hiddenId, onSelect) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  if (!results.length) return;

  results.forEach(item => {
    const pill  = document.createElement('button');
    pill.type   = 'button';
    pill.className = 'icd-pill';
    const label = item.indonesian_term || item.description || item.code;
    const extra = (item.indonesian_term && item.description && item.indonesian_term !== item.description)
      ? ` <span class="icd-pill-desc">${item.description}</span>` : '';
    pill.innerHTML = `<strong>${item.code}</strong> ${label}${extra}`;

    pill.addEventListener('click', () => {
      // Deselect siblings, select this
      container.querySelectorAll('.icd-pill').forEach(p => p.classList.remove('selected'));
      pill.classList.add('selected');
      const hidden = document.getElementById(hiddenId);
      if (hidden) hidden.value = item.code;
      if (onSelect) onSelect(item);
    });
    container.appendChild(pill);
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   PREDICTION PAGE — submitPrediction()
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Read form values, resolve ICD codes, POST to /api/v1/full-assessment, render results.
 * If the user hasn't clicked a pill, auto-resolves via API (first result).
 * If no API result, uses the raw text as-is.
 */
async function submitPrediction() {
  const btn   = document.getElementById('submit-btn');
  const alert = document.getElementById('error-alert');
  if (alert) { alert.className = 'alert'; alert.textContent = ''; }

  // ── Resolve diagnosis ICD-10 ──────────────────────────────────────────
  let primaryIcd = (document.getElementById('primary_icd10') || {}).value.trim().toUpperCase();
  const diagText = ((document.getElementById('diag-input') || {}).value || '').trim();

  if (!primaryIcd && diagText.length >= 2) {
    try {
      const res  = await fetch(`${API_BASE}/icd-search?q=${encodeURIComponent(diagText)}&type=diagnosis&limit=3`);
      const data = await res.json();
      const results = data.results || [];
      if (results.length > 0) {
        primaryIcd = results[0].code;
        // Show pills and auto-select first
        _renderPills(results, 'diag-pills', 'primary_icd10', null);
        const firstPill = document.getElementById('diag-pills').querySelector('.icd-pill');
        if (firstPill) firstPill.classList.add('selected');
      } else {
        primaryIcd = diagText;  // fallback: use raw text
      }
    } catch (e) {
      primaryIcd = diagText;
    }
  }

  if (!primaryIcd) {
    _showAlert(alert, 'Ketik nama penyakit atau kode ICD-10 di kolom Diagnosis Utama.');
    const diagInput = document.getElementById('diag-input');
    if (diagInput) diagInput.focus();
    return;
  }

  // ── Resolve procedure ICD-9 ───────────────────────────────────────────
  let procCode = (document.getElementById('icd9_procedure') || {}).value.trim();
  const procText = ((document.getElementById('proc-input') || {}).value || '').trim();

  if (!procCode && procText.length >= 2) {
    try {
      const res  = await fetch(`${API_BASE}/icd-search?q=${encodeURIComponent(procText)}&type=procedure&limit=1`);
      const data = await res.json();
      if ((data.results || []).length > 0) {
        procCode = data.results[0].code;
      }
    } catch (e) { /* ignore */ }
  }

  const kelas    = (document.getElementById('kelas') || {}).value    || 'kelas_3';
  const careType = (document.getElementById('care_type') || {}).value || 'outp';
  const actualTariff = parseFloat((document.getElementById('actual_tariff') || {}).value) || 0;

  const body = {
    primary_icd10:  primaryIcd,
    inacbg_icd10:   primaryIcd,
    icd9_procedure: procCode || null,
    care_type:      careType,
    entry_type:     careType,
    kelas:          kelas,
    episodes:       1,
    actual_tariff:  actualTariff,
  };

  // Loading state
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Memprediksi…'; }

  try {
    const resp = await fetch(`${API_BASE}/full-assessment`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok || data.status !== 'success') {
      throw new Error(data.message || `HTTP ${resp.status}`);
    }
    _renderResult(data, primaryIcd, procCode, actualTariff, kelas);
    _loadRecentPredictions();
  } catch (err) {
    _showAlert(alert, `Gagal memproses prediksi: ${err.message}`);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '🔮 Prediksi CBG & Tarif'; }
  }
}

/**
 * Render the full-assessment API response into the result card.
 * Uses exact field names from SurrogateGrouper + FinancialEstimator + RecommendationEngine.
 *
 * prediction fields used:
 *   predicted_cbg_code, predicted_cbg_description,
 *   predicted_mdc, predicted_mdc_description,
 *   predicted_severity, predicted_severity_label,
 *   predicted_base_tariff, tariff_by_kelas
 *
 * financial fields used:
 *   reimbursement_amount  (kelas-adjusted BPJS ceiling),
 *   financial_gap, risk_level
 *
 * recommendation fields used:
 *   primary_action, summary
 *
 * @param {Object} data         Full /full-assessment response
 * @param {string} icd10Code    Resolved ICD-10 code
 * @param {string} icd9Code     Resolved ICD-9 code (may be empty)
 * @param {number} actualTariff User-submitted tariff (0 if not provided)
 * @param {string} kelas        Selected ward class
 */
function _renderResult(data, icd10Code, icd9Code, actualTariff, kelas) {
  const card = document.getElementById('result-card');
  if (!card) return;

  const pred = data.prediction     || {};
  const fin  = data.financial      || {};
  const rec  = data.recommendation || {};

  // ── Selected ICD codes row ──────────────────────────────────────────
  const codesRow = document.getElementById('res-codes-row');
  if (codesRow) {
    codesRow.innerHTML =
      `<span class="badge-pill badge-mdc">ICD-10: ${icd10Code}</span>` +
      (icd9Code ? `<span class="badge-pill" style="background:#f0f9ff;color:#0369a1;border-color:#bae6fd">ICD-9: ${icd9Code}</span>` : '');
  }

  // ── CBG headline ──────────────────────────────────────────────────
  const headlineEl = document.getElementById('cbg-headline');
  if (headlineEl) {
    headlineEl.innerHTML = `
      <div class="cbg-code-large">${pred.predicted_cbg_code || '—'}</div>
      <div class="cbg-desc-text">${pred.predicted_cbg_description || ''}</div>
    `;
  }

  // ── MDC + Severity badges ─────────────────────────────────────────
  const badgesEl = document.getElementById('badges-row');
  if (badgesEl) {
    const mdc    = pred.predicted_mdc             || '?';
    const mdcD   = pred.predicted_mdc_description || '';
    const sev    = pred.predicted_severity        || '?';
    const sevL   = pred.predicted_severity_label  || '';
    const mdcPct = Math.round((pred.mdc_confidence      || 0) * 100);
    const sevPct = Math.round((pred.severity_confidence || 0) * 100);
    const lookup = pred.lookup_method || 'none';
    const lookupBadge = lookup === 'exact'
      ? `<span class="badge-pill badge-exact">✓ Exact Match</span>`
      : lookup === 'none'
        ? `<span class="badge-pill badge-none">⚠ CBG Tidak Ditemukan</span>`
        : `<span class="badge-pill badge-approx">~ Aproximasi (${lookup})</span>`;
    badgesEl.innerHTML = `
      <span class="badge-pill badge-mdc">MDC ${mdc} — ${mdcD} (${mdcPct}%)</span>
      <span class="badge-pill badge-sev">Severity ${sev} — ${sevL} (${sevPct}%)</span>
      ${lookupBadge}
    `;
  }

  // ── Tariff metrics ─────────────────────────────────────────────────
  // predicted_base_tariff = always kelas_3 rate
  const baseTariff  = pred.predicted_base_tariff || 0;
  // reimbursement_amount = kelas-adjusted BPJS ceiling (from FinancialEstimator)
  const kelasCeiling = fin.reimbursement_amount || (pred.tariff_by_kelas || {})[kelas] || baseTariff;

  _setText('res-base-tariff',  formatIDR(baseTariff));
  _setText('res-kelas-tariff', formatIDR(kelasCeiling));

  // ── Tariff status (vs user-submitted tariff) ───────────────────────
  const statusEl = document.getElementById('res-tariff-status');
  if (statusEl) {
    if (actualTariff > 0) {
      const gap = actualTariff - kelasCeiling;
      if (gap > 0) {
        statusEl.innerHTML = `<span style="color:#ef4444;font-weight:600">⚠️ MELEBIHI PLAFON</span>
          <div style="font-size:13px;color:#ef4444;margin-top:4px">Selisih: ${formatIDR(gap)}</div>`;
      } else {
        statusEl.innerHTML = `<span style="color:#22c55e;font-weight:600">✅ AMAN</span>
          <div style="font-size:13px;color:#22c55e;margin-top:4px">Dalam plafon BPJS</div>`;
      }
    } else {
      statusEl.innerHTML = `<span style="color:var(--color-text-muted);font-size:13px">Tarif tidak diisi</span>`;
    }
  }

  // ── Risk badge ────────────────────────────────────────────────────
  _setHTML('res-risk', getRiskBadgeHTML(fin.risk_level));

  // ── Primary action badge ──────────────────────────────────────────
  const actionEl = document.getElementById('res-action');
  if (actionEl && rec.primary_action) {
    actionEl.innerHTML =
      `<span class="rec-action-badge ${rec.primary_action}">${rec.primary_action.replace(/_/g, ' ')}</span>`;
  }

  // ── Recommendation summary ────────────────────────────────────────
  _setText('res-summary', rec.summary || '');

  // ── Show card ─────────────────────────────────────────────────────
  card.classList.remove('hidden');
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });

  _renderShapChart((data.prediction || {}).shap_explanation || []);
  _initFeedbackForm((data.prediction || {}).predicted_cbg_code || '');
}

function _renderShapChart(shap) {
    const section = document.getElementById('shap-section');
    if (!section) return;
    if (!shap || shap.length === 0) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');
    const top3   = shap.slice(0, 3);
    const labels = top3.map(function(s) { return s.feature.replace(/_/g, ' '); });
    const values = top3.map(function(s) { return s.impact; });
    const colors = top3.map(function(s) { return s.direction === 'positive' ? '#16a34a' : '#dc2626'; });
    if (typeof _shapChart !== 'undefined' && _shapChart) { _shapChart.destroy(); }
    _shapChart = new Chart(document.getElementById('shap-chart'), {
        type: 'bar',
        data: { labels: labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 3 }] },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: function(ctx) { return ' Impact: ' + ctx.raw.toFixed(4); } } }
            },
            scales: {
                x: { display: false },
                y: { ticks: { font: { size: 11 } } }
            }
        }
    });
}

function _initFeedbackForm(submittedCbg) {
    const toggleBtn  = document.getElementById('feedback-toggle-btn');
    const form       = document.getElementById('feedback-form');
    const statusSpan = document.getElementById('feedback-status');
    if (!toggleBtn || !form || !statusSpan) return;

    form.classList.add('hidden');
    statusSpan.style.display = 'none';
    var ccbg = document.getElementById('feedback-correct-cbg');
    var cnotes = document.getElementById('feedback-notes');
    if (ccbg) ccbg.value = '';
    if (cnotes) cnotes.value = '';

    var freshToggle = toggleBtn.cloneNode(true);
    toggleBtn.replaceWith(freshToggle);
    freshToggle.addEventListener('click', function() { form.classList.toggle('hidden'); });

    var submitBtn = document.getElementById('feedback-submit-btn');
    var freshBtn  = submitBtn.cloneNode(true);
    submitBtn.replaceWith(freshBtn);
    freshBtn.addEventListener('click', function() {
        var correctCbg = document.getElementById('feedback-correct-cbg').value.trim();
        if (!correctCbg) { alert('Masukkan CBG yang benar terlebih dahulu.'); return; }
        fetch('/api/v1/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prediction_id: null,
                submitted_cbg: submittedCbg,
                correct_cbg:   correctCbg,
                is_correct:    false,
                notes:         document.getElementById('feedback-notes').value.trim()
            })
        }).then(function() {
            statusSpan.style.display = 'inline';
            form.classList.add('hidden');
        }).catch(function() {
            alert('Gagal mengirim laporan. Coba lagi.');
        });
    });
}

/* ══════════════════════════════════════════════════════════════════════════
   RECENT PREDICTIONS TABLE (prediction page)
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Load and render the 10-row recent predictions table on the prediction page.
 */
async function _loadRecentPredictions() {
  const tbody = document.getElementById('recent-tbody');
  if (!tbody) return;

  try {
    const resp = await fetch(`${API_BASE}/stats`);
    const data = await resp.json();
    const rows = (data.recent_predictions || []).slice(0, 10);

    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-muted" style="text-align:center;padding:16px">Belum ada prediksi hari ini</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(r => {
      const cls = OUTCOME_CLASS[r.ml_prediction] || 'valid';
      return `<tr class="row-${cls}">
        <td>${formatDateTime(r.created_at)}</td>
        <td><code>${r.idrg_primary_icd10 || '—'}</code></td>
        <td>${getOutcomeMiniLabel(r.ml_prediction)}</td>
        <td>${getRiskBadgeHTML(r.risk_level)}</td>
        <td class="idr">${formatIDR(r.financial_gap)}</td>
        <td><strong>${r.primary_action || '—'}</strong></td>
      </tr>`;
    }).join('');

  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-muted">Gagal memuat riwayat: ${e.message}</td></tr>`;
  }
}

/** Small inline label for outcome column. */
function getOutcomeMiniLabel(outcome) {
  const icon  = OUTCOME_ICONS[outcome]  || '?';
  const label = OUTCOME_LABELS[outcome] || outcome;
  return `${icon} ${label}`;
}

/* ══════════════════════════════════════════════════════════════════════════
   STATS / ANALYTICS DASHBOARD
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Fetch /api/v1/stats and update all KPI cards and charts on /dashboard.
 */
async function loadStats() {
  try {
    const resp = await fetch(`${API_BASE}/stats`);
    const data = await resp.json();

    if (data.status !== 'success') throw new Error(data.message);

    // KPI cards
    _setText('kpi-total',   data.total_predictions || 0);
    _setText('kpi-valid',   (data.grouping_valid_pct   || 0).toFixed(1) + '%');
    _setText('kpi-prob',    ((data.avg_reimbursement_probability || 0) * 100).toFixed(1) + '%');
    _setText('kpi-gap',     formatIDR(data.total_financial_gap_idr || 0));
    _setText('kpi-today',   `${data.today_predictions || 0} hari ini`);

    // Charts
    _renderDonutChart(data);
    _renderLineChart(data.prediction_history || []);
    _renderRiskChart(data.risk_distribution  || {});

  } catch (e) {
    console.error('loadStats error:', e);
  }
}

/**
 * Render the donut chart — prediction label distribution.
 * @param {Object} data  Stats API response
 */
function _renderDonutChart(data) {
  const canvas = document.getElementById('donut-chart');
  if (!canvas) return;

  const vals = [
    data.grouping_valid_count    || 0,
    data.coding_incomplete_count || 0,
    data.grouping_invalid_count  || 0,
  ];

  if (_donutChart) { _donutChart.destroy(); _donutChart = null; }

  _donutChart = new Chart(canvas.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: ['Grouping Valid', 'Coding Incomplete', 'Grouping Invalid'],
      datasets: [{
        data: vals,
        backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
        borderWidth: 2,
        borderColor: '#ffffff',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { font: { size: 11 }, padding: 12 },
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct   = total ? ((ctx.raw / total) * 100).toFixed(1) : '0';
              return ` ${ctx.label}: ${ctx.raw} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

/**
 * Render the line chart — predictions per day over last 7 days.
 * @param {Array} history  Array of {date, count} objects
 */
function _renderLineChart(history) {
  const canvas = document.getElementById('line-chart');
  if (!canvas) return;

  const labels = history.map(h => {
    const d = new Date(h.date + 'T00:00:00');
    return d.toLocaleDateString('id-ID', { day: '2-digit', month: 'short' });
  });
  const counts = history.map(h => h.count);
  const valid  = history.map(h => h.valid || 0);

  if (_lineChart) { _lineChart.destroy(); _lineChart = null; }

  _lineChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label:           'Total Prediksi',
          data:            counts,
          borderColor:     '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.1)',
          fill:            true,
          tension:         0.4,
          pointRadius:     4,
        },
        {
          label:           'Grouping Valid',
          data:            valid,
          borderColor:     '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.08)',
          fill:            true,
          tension:         0.4,
          pointRadius:     4,
        },
      ],
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { font: { size: 11 }, usePointStyle: true },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { precision: 0, font: { size: 11 } },
          grid:  { color: 'rgba(0,0,0,0.05)' },
        },
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 } },
        },
      },
    },
  });
}

/**
 * Render the grouped bar chart — risk level distribution.
 * @param {Object} riskDist  { LOW: n, MEDIUM: n, HIGH: n, CRITICAL: n }
 */
function _renderRiskChart(riskDist) {
  const canvas = document.getElementById('risk-chart');
  if (!canvas) return;

  const levels = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
  const counts = levels.map(l => riskDist[l] || 0);
  const colors = ['#22c55e', '#f59e0b', '#f97316', '#ef4444'];

  if (_riskChart) { _riskChart.destroy(); _riskChart = null; }

  _riskChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: levels,
      datasets: [{
        label:           'Jumlah Klaim',
        data:            counts,
        backgroundColor: colors,
        borderRadius:    6,
        borderSkipped:   false,
      }],
    },
    options: {
      responsive:          true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks:  { precision: 0, font: { size: 11 } },
          grid:   { color: 'rgba(0,0,0,0.05)' },
        },
        x: {
          grid:  { display: false },
          ticks: { font: { size: 12, weight: '600' } },
        },
      },
    },
  });
}

/* ══════════════════════════════════════════════════════════════════════════
   FULL PREDICTIONS TABLE (dashboard — paginated)
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Load all predictions from /api/v1/stats and render paginated table.
 */
async function loadFullTable() {
  const tbody = document.getElementById('full-tbody');
  if (!tbody) return;

  try {
    const resp = await fetch(`${API_BASE}/stats`);
    const data = await resp.json();
    _allPredictions = data.recent_predictions || [];
    _currentPage    = 1;
    _renderPage();
    _renderPagination();
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="8">Gagal memuat data: ${e.message}</td></tr>`;
  }
}

/** Render the current page of _allPredictions into the full table. */
function _renderPage() {
  const tbody = document.getElementById('full-tbody');
  if (!tbody) return;

  const start = (_currentPage - 1) * PAGE_SIZE;
  const rows  = _allPredictions.slice(start, start + PAGE_SIZE);

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-muted" style="text-align:center;padding:20px">Belum ada data prediksi</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const cls = OUTCOME_CLASS[r.ml_prediction] || 'valid';
    return `<tr class="row-${cls}">
      <td>${r.id || '—'}</td>
      <td>${formatDateTime(r.created_at)}</td>
      <td><code>${r.idrg_primary_icd10 || '—'}</code></td>
      <td>${getOutcomeMiniLabel(r.ml_prediction)}</td>
      <td>${getRiskBadgeHTML(r.risk_level)}</td>
      <td class="idr">${formatIDR(r.financial_gap)}</td>
      <td>${((r.reimbursement_probability || 0) * 100).toFixed(0)}%</td>
      <td><strong>${r.primary_action || '—'}</strong></td>
    </tr>`;
  }).join('');
}

/** Render pagination controls. */
function _renderPagination() {
  const container = document.getElementById('pagination');
  if (!container) return;

  const totalPages = Math.ceil(_allPredictions.length / PAGE_SIZE);
  const info  = document.getElementById('page-info');
  if (info) info.textContent = `Halaman ${_currentPage} dari ${totalPages}`;

  const prev = document.getElementById('page-prev');
  const next = document.getElementById('page-next');
  if (prev) prev.disabled = _currentPage <= 1;
  if (next) next.disabled = _currentPage >= totalPages;
}

/** Go to previous page. */
function prevPage() {
  if (_currentPage > 1) { _currentPage--; _renderPage(); _renderPagination(); }
}

/** Go to next page. */
function nextPage() {
  const total = Math.ceil(_allPredictions.length / PAGE_SIZE);
  if (_currentPage < total) { _currentPage++; _renderPage(); _renderPagination(); }
}

/* ══════════════════════════════════════════════════════════════════════════
   EXPORT CSV
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Export _allPredictions to a CSV file and trigger browser download.
 */
function exportCSV() {
  const headers = [
    'id','created_at','idrg_primary_icd10','inacbg_primary_icd10',
    'kelas','ml_prediction','risk_level','financial_gap',
    'reimbursement_probability','primary_action','source',
  ];
  const rows = _allPredictions.map(r =>
    headers.map(h => JSON.stringify(r[h] ?? '')).join(',')
  );
  const csv  = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `dss_predictions_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ══════════════════════════════════════════════════════════════════════════
   NEUROVI INTEGRATION STUB
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Placeholder for future Neurovi HIS integration.
 * @param {string} encounterId  Neurovi encounter / visit ID
 */
async function fetchFromNeurovi(encounterId) {
  // TODO: Connect to Neurovi HIS when API docs available
  console.log('Neurovi integration pending:', encounterId);
}

/* ══════════════════════════════════════════════════════════════════════════
   CHART INITIALISATION (called on dashboard page load)
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Initialise all Chart.js instances on the dashboard page.
 */
function initCharts() {
  loadStats();
  loadFullTable();
}

/* ══════════════════════════════════════════════════════════════════════════
   DOM HELPERS
   ══════════════════════════════════════════════════════════════════════════ */

function _val(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function _setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function _setHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function _setWidth(id, width) {
  const el = document.getElementById(id);
  if (el) el.style.width = width;
}

function _showAlert(el, msg) {
  if (!el) return;
  el.textContent = msg;
  el.className   = 'alert error visible';
}

/* ══════════════════════════════════════════════════════════════════════════
   PAGE INIT
   ══════════════════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  checkApiStatus();

  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    // Prediction page
    submitBtn.addEventListener('click', submitPrediction);
    _loadRecentPredictions();

    // Wire up diagnosis search → pills
    const diagInput = document.getElementById('diag-input');
    if (diagInput) {
      diagInput.addEventListener('input', () => {
        // Clear selected code when user types new text
        const hidden = document.getElementById('primary_icd10');
        if (hidden) hidden.value = '';
        clearTimeout(_diagTimer);
        const q = diagInput.value.trim();
        if (q.length < 2) {
          const pills = document.getElementById('diag-pills');
          if (pills) pills.innerHTML = '';
          return;
        }
        _diagTimer = setTimeout(() => {
          _fetchPills(q, 'diagnosis', 'diag-pills', 'primary_icd10', null);
        }, 350);
      });
    }

    // Wire up procedure search → pills
    const procInput = document.getElementById('proc-input');
    if (procInput) {
      procInput.addEventListener('input', () => {
        const hidden = document.getElementById('icd9_procedure');
        if (hidden) hidden.value = '';
        clearTimeout(_procTimer);
        const q = procInput.value.trim();
        if (q.length < 2) {
          const pills = document.getElementById('proc-pills');
          if (pills) pills.innerHTML = '';
          return;
        }
        _procTimer = setTimeout(() => {
          _fetchPills(q, 'procedure', 'proc-pills', 'icd9_procedure', null);
        }, 350);
      });
    }
  }

  // Dashboard page
  if (document.getElementById('kpi-total')) {
    initCharts();
  }
});
