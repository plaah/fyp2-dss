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
   PREDICTION PAGE — submitPrediction()
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Read form values, POST to /api/v1/full-assessment, render results.
 */
async function submitPrediction() {
  const btn   = document.getElementById('submit-btn');
  const alert = document.getElementById('error-alert');

  if (alert) { alert.className = 'alert'; alert.textContent = ''; }

  // Clinical-only payload — no grouping result fields needed
  const primaryIcd = _val('primary_icd10').toUpperCase();
  const inacbgIcd  = (_val('inacbg_icd10') || primaryIcd).toUpperCase();

  const body = {
    primary_icd10:  primaryIcd,
    inacbg_icd10:   inacbgIcd,
    icd9_procedure: _val('icd9_procedure') || null,
    care_type:      _val('care_type'),
    entry_type:     _val('entry_type'),
    kelas:          _val('kelas'),
    episodes:       parseInt(_val('episodes')) || 1,
    actual_tariff:  parseFloat(_val('actual_tariff')) || 0,
  };

  // Validate required
  if (!body.primary_icd10) {
    _showAlert(alert, 'Pilih diagnosis utama terlebih dahulu (ketik dan pilih dari dropdown).');
    const diagInput = document.getElementById('diagnosis_search');
    if (diagInput) diagInput.focus();
    return;
  }

  // Loading state
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Memprediksi…';
  }

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

    _renderResult(data);
    _loadRecentPredictions();

  } catch (err) {
    _showAlert(alert, `Gagal memproses prediksi: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🔮 Prediksi CBG & Tarif';
    }
  }
}

/**
 * Render the full-assessment API response (surrogate grouper format).
 * @param {Object} data  API response from /full-assessment
 */
function _renderResult(data) {
  const section = document.getElementById('result-section');
  if (!section) return;

  const pred = data.prediction   || {};
  const fin  = data.financial    || {};
  const rec  = data.recommendation || {};

  const cbgCode     = pred.predicted_cbg_code        || '—';
  const cbgDesc     = pred.predicted_cbg_description || '';
  const mdc         = pred.predicted_mdc             || '?';
  const mdcDesc     = pred.predicted_mdc_description || '';
  const severity    = pred.predicted_severity        || '?';
  const sevLabel    = pred.predicted_severity_label  || '';
  const mdcConf     = Math.round((pred.mdc_confidence     || 0) * 100);
  const sevConf     = Math.round((pred.severity_confidence || 0) * 100);
  const lookupMethod = pred.lookup_method            || 'none';
  const tariffByKelas = pred.tariff_by_kelas         || {};
  const kelas       = document.getElementById('kelas') ? document.getElementById('kelas').value : 'kelas_3';
  const shap        = pred.shap_explanation          || [];

  // ── CBG headline ───────────────────────────────────────────
  const headlineEl = document.getElementById('cbg-headline');
  if (headlineEl) {
    headlineEl.innerHTML = `
      <div class="cbg-code-large">${cbgCode}</div>
      <div class="cbg-desc-text">${cbgDesc}</div>
    `;
  }

  // ── MDC + Severity + Lookup badges ─────────────────────────
  const badgesEl = document.getElementById('badges-row');
  if (badgesEl) {
    let lookupBadge;
    if (lookupMethod === 'exact') {
      lookupBadge = `<span class="badge-pill badge-exact">✓ Exact Match</span>`;
    } else if (lookupMethod === 'none') {
      lookupBadge = `<span class="badge-pill badge-none">⚠ Tidak Ditemukan</span>`;
    } else {
      lookupBadge = `<span class="badge-pill badge-approx">~ Aproximasi</span>`;
    }
    badgesEl.innerHTML = `
      <span class="badge-pill badge-mdc">MDC ${mdc} — ${mdcDesc}</span>
      <span class="badge-pill badge-sev">Severity ${severity} — ${sevLabel}</span>
      ${lookupBadge}
    `;
  }

  // ── Confidence bars ────────────────────────────────────────
  _setWidth('seg-mdc', mdcConf + '%');
  _setText('conf-mdc-label', `MDC: ${mdcConf}% kepercayaan`);
  _setWidth('seg-sev', sevConf + '%');
  _setText('conf-sev-label', `Severity: ${sevConf}% kepercayaan`);

  // ── Tariff metrics ─────────────────────────────────────────
  _setText('metric-base-tariff', formatIDR(pred.predicted_base_tariff || 0));
  _setText('metric-kelas-tariff', formatIDR(tariffByKelas[kelas] || pred.predicted_base_tariff || 0));
  _setHTML('metric-gap',
    formatIDR(fin.financial_gap || 0) +
    `<div class="mt-4">${getRiskBadgeHTML(fin.risk_level)}</div>`
  );

  // ── SHAP chart ─────────────────────────────────────────────
  _renderShapChart(shap);

  // ── Recommendation box ─────────────────────────────────────
  const recBox = document.getElementById('rec-box');
  if (recBox) {
    const action = rec.primary_action || 'REVIEW';
    // Color recommendation box by confidence: green=high, amber=medium, red=low/none
    let recCls = 'valid';
    if (lookupMethod === 'none' || mdcConf < 60)       recCls = 'invalid';
    else if (mdcConf < 80 || lookupMethod !== 'exact')  recCls = 'incomplete';

    recBox.className = `recommendation-box ${recCls}`;

    const recs = (rec.recommendations || []).slice(0, 4);
    const tips = rec.coding_tips || [];

    const recsHtml = recs.map(r =>
      `<li><strong>${r.action}</strong> — <span class="text-muted">${r.reason}</span></li>`
    ).join('');

    const tipsHtml = tips.length ? `
      <div class="coding-tips">
        <div class="coding-tips-title">💡 Coding Tips</div>
        ${tips.map(t => `<div class="coding-tip-item">• ${t}</div>`).join('')}
      </div>` : '';

    recBox.innerHTML = `
      <span class="rec-action-badge ${action}">${action.replace(/_/g, ' ')}</span>
      <div class="rec-summary">${rec.summary || ''}</div>
      <ul class="rec-list">${recsHtml}</ul>
      ${tipsHtml}
      <div class="rec-resolution">⏱ Estimasi resolusi: <strong>${rec.estimated_resolution_days || 14} hari kerja</strong></div>
    `;
  }

  section.className = 'visible';
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Render horizontal SHAP bar chart for top-3 features.
 * @param {Array} explanation  Array of {feature, impact, direction} objects
 */
function _renderShapChart(explanation) {
  const canvas = document.getElementById('shap-chart');
  if (!canvas || !explanation.length) return;

  const labels  = explanation.map(e => e.feature.replace(/_/g, ' '));
  const impacts = explanation.map(e => e.impact);
  const colors  = explanation.map(e =>
    e.direction === 'positive' ? 'rgba(34,197,94,0.8)' : 'rgba(239,68,68,0.8)'
  );

  if (_shapChart) { _shapChart.destroy(); _shapChart = null; }

  _shapChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: impacts,
        backgroundColor: colors,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` Impact: ${ctx.raw.toFixed(4)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(0,0,0,0.05)' },
          ticks: { font: { size: 11 } },
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 11 } },
        },
      },
    },
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
 * When Neurovi API docs are available, this function will fetch encounter
 * data and auto-populate the prediction form fields.
 *
 * @param {string} encounterId  Neurovi encounter / visit ID
 */
async function fetchFromNeurovi(encounterId) {
  // TODO: Connect to Neurovi HIS when API docs available
  // Will auto-populate form fields from real encounter data
  console.log('Neurovi integration pending:', encounterId);
}

/* ══════════════════════════════════════════════════════════════════════════
   CHART INITIALISATION (called on dashboard page load)
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Initialise all Chart.js instances on the dashboard page.
 * Safe to call multiple times — existing charts are destroyed first.
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
   PAGE INIT — called from each page's DOMContentLoaded
   ══════════════════════════════════════════════════════════════════════════ */

/* ══════════════════════════════════════════════════════════════════════════
   ICD SEARCH WIDGET — Sprint 6 / T6.3
   Search-as-you-type ICD code selector (Tier 1 Indonesian + Tier 2 English
   + Tier 3 code prefix). Debounced 300ms fetch to /api/v1/icd-search.
   ══════════════════════════════════════════════════════════════════════════ */

class IcdSearchWidget {
  /**
   * @param {object} config
   *   inputId    — visible text input id
   *   hiddenId   — hidden input that stores the selected ICD code
   *   badgeId    — span that shows the selected code as a pill badge
   *   dropdownId — div container for the dropdown list
   *   type       — 'diagnosis' | 'procedure'
   *   placeholder
   *   onSelect   — optional callback(code, item)
   */
  constructor(config) {
    this.cfg          = config;
    this.debounceTimer = null;
    this.activeIndex  = -1;
    this.results      = [];

    this.input    = document.getElementById(config.inputId);
    this.hidden   = document.getElementById(config.hiddenId);
    this.badge    = document.getElementById(config.badgeId);
    this.dropdown = document.getElementById(config.dropdownId);

    if (!this.input) return;

    if (config.placeholder) {
      this.input.placeholder = config.placeholder;
    }
    this._bindEvents();
  }

  _bindEvents() {
    this.input.addEventListener('input', () => {
      clearTimeout(this.debounceTimer);
      const q = this.input.value.trim();
      if (q.length < 2) { this._close(); return; }
      this.debounceTimer = setTimeout(() => this._search(q), 300);
    });

    this.input.addEventListener('keydown', (e) => {
      if (!this.results.length) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        this.activeIndex = Math.min(this.activeIndex + 1, this.results.length - 1);
        this._highlight();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        this.activeIndex = Math.max(this.activeIndex - 1, -1);
        this._highlight();
      } else if (e.key === 'Enter' && this.activeIndex >= 0) {
        e.preventDefault();
        this._select(this.results[this.activeIndex]);
      } else if (e.key === 'Escape') {
        this._close();
      }
    });

    document.addEventListener('click', (e) => {
      if (this.input && !this.input.contains(e.target) &&
          this.dropdown && !this.dropdown.contains(e.target)) {
        this._close();
      }
    });
  }

  async _search(q) {
    try {
      const type = this.cfg.type || 'diagnosis';
      const res  = await fetch(
        `${API_BASE}/icd-search?q=${encodeURIComponent(q)}&type=${type}&limit=6`
      );
      const data = await res.json();
      this.results     = data.results || [];
      this.activeIndex = -1;
      this._render();
    } catch (err) {
      console.error('ICD search error:', err);
    }
  }

  _render() {
    this.dropdown.innerHTML = '';
    if (!this.results.length) { this._close(); return; }
    this.results.forEach((item, i) => {
      const div = document.createElement('div');
      div.className    = 'icd-dropdown-item';
      div.dataset.index = i;
      const label = item.indonesian_term || item.description || item.code;
      const desc  = item.indonesian_term && item.description ? item.description : '';
      div.innerHTML = `
        <span class="icd-code">${item.code}</span>
        <span>${label}</span>
        ${desc ? `<span class="icd-desc">${desc}</span>` : ''}
      `;
      div.addEventListener('click', () => this._select(item));
      this.dropdown.appendChild(div);
    });
    this.dropdown.classList.remove('hidden');
  }

  _select(item) {
    this.hidden.value = item.code;
    this.input.value  = item.indonesian_term || item.description || item.code;
    if (this.badge) {
      this.badge.textContent = item.code;
      this.badge.classList.remove('hidden');
    }
    this._close();
    if (this.cfg.onSelect) this.cfg.onSelect(item.code, item);
  }

  _highlight() {
    this.dropdown.querySelectorAll('.icd-dropdown-item').forEach((el, i) => {
      el.classList.toggle('active', i === this.activeIndex);
    });
  }

  _close() {
    if (this.dropdown) this.dropdown.classList.add('hidden');
    this.results     = [];
    this.activeIndex = -1;
  }

  clear() {
    if (this.hidden) this.hidden.value = '';
    if (this.input)  this.input.value  = '';
    if (this.badge)  this.badge.classList.add('hidden');
    this._close();
  }

  getValue() { return this.hidden ? this.hidden.value : ''; }
}

/* ── Widget instances (global so HTML onclick="diagnosisWidget.clear()" works) */
let diagnosisWidget, inacbgWidget, procedureWidget;

document.addEventListener('DOMContentLoaded', () => {
  checkApiStatus();

  // Prediction page
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    submitBtn.addEventListener('click', submitPrediction);
    _loadRecentPredictions();

    // Initialise ICD search widgets (prediction page only)
    diagnosisWidget = new IcdSearchWidget({
      inputId:    'diagnosis_search',
      hiddenId:   'primary_icd10',
      badgeId:    'diagnosis_badge',
      dropdownId: 'diagnosis_dropdown',
      type:       'diagnosis',
      placeholder: 'Ketik nama penyakit... (hipertensi, pneumonia...)',
      onSelect: (code, item) => {
        // Auto-sync INACBG field with same code if not already set
        if (inacbgWidget && !inacbgWidget.getValue()) {
          document.getElementById('inacbg_icd10').value = code;
          document.getElementById('inacbg_search').value =
            item.indonesian_term || item.description || code;
          document.getElementById('inacbg_badge').textContent = code;
          document.getElementById('inacbg_badge').classList.remove('hidden');
        }
      },
    });

    inacbgWidget = new IcdSearchWidget({
      inputId:    'inacbg_search',
      hiddenId:   'inacbg_icd10',
      badgeId:    'inacbg_badge',
      dropdownId: 'inacbg_dropdown',
      type:       'diagnosis',
      placeholder: 'Sama dengan diagnosis utama (opsional)',
    });

    procedureWidget = new IcdSearchWidget({
      inputId:    'procedure_search',
      hiddenId:   'icd9_procedure',
      badgeId:    'procedure_badge',
      dropdownId: 'procedure_dropdown',
      type:       'procedure',
      placeholder: 'Ketik tindakan... (nebulisasi, infus, operasi...)',
    });
  }

  // Dashboard page
  if (document.getElementById('kpi-total')) {
    initCharts();
  }
});
