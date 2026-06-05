/* ── State ─────────────────────────────────────────────────── */
const state = {
  loading: false,
  lastResult: null,
};

/* ── DOM refs ─────────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
  ip:         $('#ip'),
  date:       $('#date'),
  previewBtn: $('#btn-preview'),
  execBtn:    $('#btn-exec'),
  alert:      $('#alert'),
  alertMsg:   $('#alert-msg'),
  resultCard: $('#result-card'),
  resultBody: $('#result-body'),
  execResult: $('#exec-result'),
  optionsList: $('#options-list'),
  optionsCard: $('#options-card'),
  optionInput: $('#option-input'),
  addOptBtn:  $('#btn-add-opt'),
  refreshOptBtn: $('#btn-refresh-opt'),
  spinner:    $('#spinner'),
  btnText:    (btn) => btn.querySelector('.btn-text'),
  spinnerOf:  (btn) => btn.querySelector('.spinner'),
};

/* ─── Helpers ──────────────────────────────────────────── */

function showAlert(msg, type = 'info') {
  dom.alert.className = `alert show alert-${type}`;
  dom.alertMsg.textContent = msg;
  setTimeout(() => dom.alert.classList.remove('show'), 5000);
}

function setLoading(loading) {
  state.loading = loading;
  dom.previewBtn.disabled = loading;
  dom.execBtn.disabled = loading;
  dom.spinner.classList.toggle('show', loading);
}

function setBtnLoading(btn, loading) {
  btn.disabled = loading;
  dom.spinnerOf(btn).classList.toggle('show', loading);
  dom.btnText(btn).textContent = loading ? 'Procesando…' : btn.dataset.label;
}

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

/* ─── Preview ──────────────────────────────────────────── */

async function handlePreview(execute = false) {
  const ip   = dom.ip.value.trim();
  const date = dom.date.value || todayStr();

  if (!ip) { showAlert('Ingresá la IP del MikroTik', 'error'); return; }

  const btn = execute ? dom.execBtn : dom.previewBtn;
  setBtnLoading(btn, true);

  try {
    const endpoint = execute ? '/script' : '/preview';
    const result = await api('POST', endpoint, {
      IP_MIKROTIK: ip,
      DATE: date,
    });

    if (execute) {
      dom.execResult.textContent = '✅ ' + (result.message || 'Ejecutado correctamente');
      dom.execResult.style.color = 'var(--success)';
      showAlert('Suspensión ejecutada con éxito', 'success');
      return;
    }

    // Preview mode — render table
    state.lastResult = result;
    renderPreview(result);
    dom.resultCard.style.display = 'block';
    showAlert(`Se encontraron ${result[0]?.length || 0} IPs para suspender`, 'info');
  } catch (err) {
    showAlert(`Error: ${err.message}`, 'error');
  } finally {
    setBtnLoading(btn, false);
  }
}

function renderPreview([currentComments, finalComments]) {
  const tbody = dom.resultBody;

  if (!currentComments || currentComments.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" class="empty-state">No hay IPs para suspender</td></tr>`;
    return;
  }

  tbody.innerHTML = currentComments.map((curr, i) => {
    const final = finalComments[i] || {};
    return `<tr>
      <td><code>${escHtml(curr.id)}</code></td>
      <td><code>${escHtml(final.comment || curr.comment)}</code></td>
    </tr>`;
  }).join('');
}

/* ─── Options ──────────────────────────────────────────── */

async function loadOptions() {
  try {
    const data = await api('GET', '/readOptions');
    renderOptions(data.data || []);
  } catch (err) {
    showAlert(`Error al leer opciones: ${err.message}`, 'error');
  }
}

function renderOptions(options) {
  if (!options || options.length === 0) {
    dom.optionsList.innerHTML = `<div class="empty-state">
      <div class="icon">📭</div>
      <div>No hay opciones guardadas</div>
    </div>`;
    return;
  }
  dom.optionsList.innerHTML = options.map(opt =>
    `<span class="option-tag">${escHtml(opt)}</span>`
  ).join('');
}

async function addOption() {
  const val = dom.optionInput.value.trim();
  if (!val) { showAlert('Ingresá una IP', 'error'); return; }

  setBtnLoading(dom.addOptBtn, true);
  try {
    await api('POST', '/addDoc', { option: val });
    dom.optionInput.value = '';
    showAlert('IP agregada correctamente', 'success');
    await loadOptions();
  } catch (err) {
    showAlert(`Error: ${err.message}`, 'error');
  } finally {
    setBtnLoading(dom.addOptBtn, false);
  }
}

/* ─── Misc ─────────────────────────────────────────────── */

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

/* ─── Init ─────────────────────────────────────────────── */

function init() {
  dom.date.value = todayStr();

  // Eventos principales
  dom.previewBtn.addEventListener('click', () => handlePreview(false));
  dom.execBtn.addEventListener('click', () => handlePreview(true));
  dom.addOptBtn.addEventListener('click', addOption);
  dom.refreshOptBtn.addEventListener('click', loadOptions);

  // Enter en inputs
  dom.ip.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handlePreview(false);
  });
  dom.optionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addOption();
  });

  // Cargar opciones al inicio
  loadOptions();
}

document.addEventListener('DOMContentLoaded', init);
