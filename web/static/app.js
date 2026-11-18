"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const els = {
  form: $("#search-form"),
  users: $("#users"),
  usersCombo: $("#users-combo"),
  usersList: $("#users-list"),
  usersClear: $("#users-clear"),
  quote: $("#quote"),
  quoteCombo: $("#quote-combo"),
  quoteList: $("#quote-list"),
  quoteClear: $("#quote-clear"),
  quotePreview: $("#quote-preview"),
  from: $("#from"),
  fromError: $("#from-error"),
  to: $("#to"),
  toError: $("#to-error"),
  limit: $("#limit"),
  delay: $("#delay"),
  match: $("#match"),
  exclude: $("#exclude"),
  previewBtn: $("#preview-btn"),
  applyBtn: $("#apply-btn"),
  cancelBtn: $("#cancel-btn"),
  resultSub: $("#result-sub"),
  exports: $("#exports"),
  exportCsv: $("#export-csv"),
  exportMd: $("#export-md"),
  jobPanel: $("#job-panel"),
  jobSpinner: $("#job-spinner"),
  jobStatus: $("#job-status-text"),
  jobElapsed: $("#job-elapsed"),
  jobCancel: $("#job-cancel"),
  jobProgress: $("#job-progress"),
  jobProgressBar: $("#job-progress-bar"),
  jobProgressText: $("#job-progress-text"),
  logBox: $("#log-box"),
  jobLog: $("#job-log"),
  empty: $("#empty"),
  tableTools: $("#table-tools"),
  postsFilter: $("#posts-filter"),
  postsSort: $("#posts-sort"),
  postsCount: $("#posts-count"),
  pickTh: $("#pick-th"),
  pickAll: $("#pick-all"),
  tableWrap: $("#table-wrap"),
  postsBody: $("#posts-body"),
  resultFoot: $("#result-foot"),
  applyNote: $("#apply-note"),
  chipEngine: $("#chip-engine"),
  chipChrome: $("#chip-chrome"),
  historyEmpty: $("#history-empty"),
  historyWrap: $("#history-wrap"),
  historyBody: $("#history-body"),
  historyFilter: $("#history-filter"),
  historyMore: $("#history-more"),
  refreshHistory: $("#refresh-history"),
  undoLast: $("#undo-last"),
  confirmDialog: $("#confirm-dialog"),
  confirmSummary: $("#confirm-summary"),
  confirmCheck: $("#confirm-check"),
  confirmGo: $("#confirm-go"),
  confirmCancel: $("#confirm-cancel"),
  undoDialog: $("#undo-dialog"),
  undoTitle: $("#undo-title"),
  undoText: $("#undo-text"),
  undoDetail: $("#undo-detail"),
  undoNLabel: $("#undo-n-label"),
  undoN: $("#undo-n"),
  undoConfirm: $("#undo-confirm"),
  toast: $("#toast"),
};

const state = {
  preview: null,
  previewParams: null,
  previewStale: false,
  busy: false,
  engineOk: null,
  jobId: null,
  poll: null,
  undoTarget: null,
  posts: [],
  selected: new Set(),
  selectable: false,
  historyEntries: [],
  historyLimit: 40,
};

let toastTimer = null;

// --- autocompletado (cuentas y hashtags) -----------------------------------

// Los campos con sugerencias (Cuentas y Hashtag de la cita) comparten la misma
// mecánica: se busca el token bajo el cursor, se piden coincidencias a la API y
// se elige con teclado o ratón.
function appendHighlighted(element, text, query) {
  const needle = (query || "").toLowerCase();
  const index = needle ? text.toLowerCase().indexOf(needle) : -1;
  if (index < 0) {
    element.textContent = text;
    return;
  }
  element.append(text.slice(0, index));
  const mark = document.createElement("mark");
  mark.textContent = text.slice(index, index + needle.length);
  element.append(mark, text.slice(index + needle.length));
}

function createCombo(config) {
  const { input, list, wrap } = config;
  const prefixRe = new RegExp("^" + config.prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const state = {
    items: [],
    active: -1,
    open: false,
    timer: null,
    controller: null,
    seq: 0,
  };

  function tokenBounds(value, caret) {
    let start = 0;
    for (let index = caret - 1; index >= 0; index -= 1) {
      if (config.separator.test(value[index])) {
        start = index + 1;
        break;
      }
    }
    let end = value.length;
    for (let index = caret; index < value.length; index += 1) {
      if (config.separator.test(value[index])) {
        end = index;
        break;
      }
    }
    return { start, end };
  }

  function currentToken() {
    const value = input.value;
    const caret = input.selectionStart ?? value.length;
    const { start, end } = tokenBounds(value, caret);
    const raw = value.slice(start, end);
    const lead = (raw.match(/^\s*/) || [""])[0];
    const query = raw.trim().replace(prefixRe, "");
    return { start, end, query, caret, lead, raw };
  }

  function usedTokens(token) {
    const out = [];
    const seen = new Set();
    for (const part of input.value.split(config.split)) {
      const item = part.trim().replace(prefixRe, "");
      if (!config.tokenRe.test(item)) continue;
      const key = item.toLowerCase();
      if (key === token.query.toLowerCase() || seen.has(key)) continue;
      seen.add(key);
      out.push(item);
    }
    return out;
  }

  function setActive(index) {
    const options = Array.from(list.querySelectorAll(".combo-option"));
    if (!options.length) {
      state.active = -1;
      input.removeAttribute("aria-activedescendant");
      return;
    }
    const next = Math.max(0, Math.min(index, options.length - 1));
    state.active = next;
    options.forEach((option, position) => {
      option.setAttribute("aria-selected", position === next ? "true" : "false");
    });
    const current = options[next];
    input.setAttribute("aria-activedescendant", current.id);
    current.scrollIntoView({ block: "nearest" });
  }

  function hide() {
    state.open = false;
    state.active = -1;
    state.items = [];
    state.seq += 1;
    clearTimeout(state.timer);
    state.timer = null;
    if (state.controller) state.controller.abort();
    state.controller = null;
    list.replaceChildren();
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function render(items, query) {
    list.replaceChildren();
    state.items = items;
    state.active = -1;

    if (!items.length) {
      if (query) {
        const empty = document.createElement("li");
        empty.className = "combo-empty";
        empty.textContent = config.emptyText;
        list.append(empty);
        state.open = true;
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
      } else {
        hide();
      }
      return;
    }

    const fragment = document.createDocumentFragment();
    items.forEach((item, index) => {
      const value = String(item[config.itemKey] || "");
      const option = document.createElement("li");
      option.className = "combo-option";
      option.id = `${config.optionPrefix}-${index}`;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", "false");
      option.dataset.value = value;

      const name = document.createElement("strong");
      appendHighlighted(name, config.prefix + value, query);
      option.append(name);

      const uses = Number(item.count || 0);
      if (uses > 1) {
        const meta = document.createElement("small");
        meta.textContent = `${uses} usos`;
        option.append(meta);
      }

      option.addEventListener("mousedown", (event) => event.preventDefault());
      option.addEventListener("mouseenter", () => setActive(index));
      option.addEventListener("click", () => choose(index));
      fragment.append(option);
    });

    list.append(fragment);
    state.open = true;
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  async function fetchItems() {
    if (document.activeElement !== input) return;
    const token = currentToken();
    const exclude = usedTokens(token);
    const params = new URLSearchParams({ q: token.query, limit: "8" });
    if (exclude.length) params.set("exclude", exclude.join(","));

    if (state.controller) state.controller.abort();
    state.controller = new AbortController();
    const seq = ++state.seq;
    try {
      const response = await fetch(`${config.endpoint}?${params}`, {
        signal: state.controller.signal,
        headers: { Accept: "application/json" },
      });
      if (seq !== state.seq) return;
      if (!response.ok) {
        hide();
        return;
      }
      const data = await response.json();
      if (seq !== state.seq) return;
      render(data[config.responseKey] || [], token.query);
    } catch (error) {
      if (error.name !== "AbortError" && seq === state.seq) hide();
    }
  }

  function schedule(immediate = false) {
    clearTimeout(state.timer);
    if (immediate) {
      fetchItems();
      return;
    }
    state.timer = setTimeout(fetchItems, 120);
  }

  function choose(index) {
    const item = state.items[index];
    if (!item) return;
    const value = String(item[config.itemKey] || "");
    const token = currentToken();
    const suffix = input.value.slice(token.end);
    let replacement = token.lead + config.prefix + value;
    let caret = token.start + replacement.length;
    if (!config.joinerCheck.test(suffix)) {
      replacement += config.joiner;
      caret += config.joiner.length;
    }
    input.value = input.value.slice(0, token.start) + replacement + suffix;
    input.setSelectionRange(caret, caret);
    hide();
    input.dispatchEvent(new Event("input", { bubbles: true }));
    schedule(true);
  }

  function onKeydown(event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const delta = event.key === "ArrowDown" ? 1 : -1;
      if (!state.open) {
        fetchItems().then(() => {
          if (state.open && state.items.length) {
            setActive(delta > 0 ? 0 : state.items.length - 1);
          }
        });
        return;
      }
      const total = state.items.length;
      if (!total) return;
      if (state.active < 0) {
        setActive(delta > 0 ? 0 : total - 1);
      } else {
        setActive((state.active + delta + total) % total);
      }
    } else if (event.key === "Enter" && state.open && state.active >= 0) {
      event.preventDefault();
      choose(state.active);
    } else if (event.key === "Tab" && !event.shiftKey && state.open && state.active >= 0) {
      event.preventDefault();
      choose(state.active);
    } else if (event.key === "Escape" && state.open) {
      event.preventDefault();
      hide();
    }
  }

  input.addEventListener("input", () => schedule());
  input.addEventListener("focus", () => schedule(true));
  input.addEventListener("blur", () => setTimeout(hide, 120));
  input.addEventListener("keydown", onKeydown);

  return { hide, schedule, fetchItems, choose, setActive, state, wrap };
}

const usersCombo = createCombo({
  input: els.users,
  list: els.usersList,
  wrap: els.usersCombo,
  endpoint: "/api/accounts",
  responseKey: "accounts",
  itemKey: "handle",
  prefix: "@",
  separator: /,/,
  split: ",",
  tokenRe: /^[A-Za-z0-9_]{1,15}$/,
  joiner: ", ",
  joinerCheck: /^,/,
  emptyText: "Sin cuentas usadas que coincidan.",
  optionPrefix: "users-option",
});

const quoteCombo = createCombo({
  input: els.quote,
  list: els.quoteList,
  wrap: els.quoteCombo,
  endpoint: "/api/hashtags",
  responseKey: "hashtags",
  itemKey: "tag",
  prefix: "#",
  separator: /[\s,]/,
  split: /[\s,]+/,
  tokenRe: /^[^\s#,]{1,50}$/,
  joiner: " ",
  joinerCheck: /^[\s,]/,
  emptyText: "Sin hashtags usados que coincidan.",
  optionPrefix: "quote-option",
});

function hideCombos() {
  usersCombo.hide();
  quoteCombo.hide();
}

// Borra el historial guardado de uno de los dos campos con sugerencias.
async function clearHistory(kind) {
  const isAccounts = kind === "accounts";
  const question = isAccounts
    ? "¿Borrar el historial de cuentas guardadas? Dejarán de aparecer en las sugerencias."
    : "¿Borrar el historial de hashtags guardados? Dejarán de aparecer en las sugerencias.";
  if (!window.confirm(question)) return;

  const endpoint = isAccounts ? "/api/accounts/clear" : "/api/hashtags/clear";
  const combo = isAccounts ? usersCombo : quoteCombo;
  const input = isAccounts ? els.users : els.quote;
  try {
    await api(endpoint, { method: "POST", body: {} });
    combo.hide();
    if (document.activeElement === input) combo.schedule(true);
    toast(isAccounts ? "Historial de cuentas borrado." : "Historial de hashtags borrado.", "ok");
  } catch (error) {
    toast(error.message, "bad");
  }
}

function todayISO() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

// --- fechas: la interfaz usa DD/MM/AAAA; la API y el motor trabajan en ISO ---

const DAY_RE = /^(0[1-9]|[12]\d|3[01])$/;
const MONTH_RE = /^(0[1-9]|1[0-2])$/;

function isoToDMY(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso || "");
}

// "28/10/2026" -> "2026-10-28". Devuelve "" si está incompleta o no existe.
function dmyToISO(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (digits.length !== 8) return "";
  const day = digits.slice(0, 2);
  const month = digits.slice(2, 4);
  const year = digits.slice(4, 8);
  const probe = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    probe.getFullYear() !== Number(year) ||
    probe.getMonth() !== Number(month) - 1 ||
    probe.getDate() !== Number(day)
  ) {
    return "";
  }
  return `${year}-${month}-${day}`;
}

// --- comentario de la cita: cada palabra se convierte en hashtag ------------

const MAX_QUOTE = 280;
const TAG_RE = /^[^\s#,]{1,50}$/;
const ALNUM_RE = /[\p{L}\p{N}]/u;

// "ETECSA, cuba" -> "#ETECSA #cuba" (igual que xrepost_hashtags.clean_text).
function normalizeQuote(value) {
  const seen = new Set();
  const tags = [];
  for (const part of String(value || "").split(/[\s,]+/)) {
    const tag = part.trim().replace(/^#+/, "");
    if (!TAG_RE.test(tag) || !ALNUM_RE.test(tag)) continue;
    const key = tag.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    tags.push(tag);
  }
  return tags.map((tag) => "#" + tag).join(" ");
}

// Motivo por el que una fecha DD/MM/AAAA no sirve ("" si es correcta).
function dateError(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (!digits) return "escribe una fecha.";
  if (digits.length !== 8) return "completa la fecha (DD/MM/AAAA).";
  if (!dmyToISO(value)) return "esa fecha no existe en el calendario.";
  const year = Number(digits.slice(4, 8));
  if (year < 2006 || year > 2100) return "el año debe estar entre 2006 y 2100.";
  return "";
}

// Dibuja DD/MM/AAAA a partir de los dígitos tecleados.
function maskDate(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 8);
  if (digits.length > 4) return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  if (digits.length > 2) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return digits;
}

// Marca de tiempo ISO -> DD/MM/YYYY HH:MM (para el historial).
function fmtDateTime(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(String(value || ""));
  if (!m) return String(value || "");
  const [, year, month, day, hh, mm] = m;
  return `${day}/${month}/${year}` + (hh ? ` ${hh}:${mm}` : "");
}

// Máscara DD/MM/AAAA: barras automáticas y rechazo de días/meses imposibles
// mientras se escribe (90/90/... no llega a mostrarse).
function attachDateMask(input, errorEl) {
  let last = maskDate(input.value);

  const paint = () => {
    input.value = last;
    input.setSelectionRange(last.length, last.length);
    const error = last.replace(/\D/g, "").length === 8 ? dateError(last) : "";
    input.classList.toggle("invalid", Boolean(error));
    input.title = error ? error.charAt(0).toUpperCase() + error.slice(1) : "";
    if (errorEl) {
      errorEl.textContent = error ? error.charAt(0).toUpperCase() + error.slice(1) : "";
      errorEl.hidden = !error;
      input.setAttribute("aria-invalid", error ? "true" : "false");
    }
  };

  input.addEventListener("input", () => {
    let digits = input.value.replace(/\D/g, "").slice(0, 8);
    // Auto-relleno: "9" pasa a "09" (día o mes) para no trabar el tecleo.
    if (digits.length === 1 && digits > "3") {
      digits = "0" + digits;
    } else if (digits.length === 3 && digits[2] > "1") {
      digits = digits.slice(0, 2) + "0" + digits[2];
    }
    const day = digits.slice(0, 2);
    const month = digits.slice(2, 4);
    const dayOk = day.length < 2 || DAY_RE.test(day);
    const monthOk = month.length < 2 || MONTH_RE.test(month);
    if (dayOk && monthOk) last = maskDate(digits);
    paint();
  });

  input.addEventListener("blur", paint);
  paint();
}

// Calendario nativo: el botón abre el selector y vuelca el valor como DD/MM/AAAA.
function attachDatePicker(input, native) {
  const sync = () => {
    const iso = dmyToISO(input.value);
    if (iso) native.value = iso;
  };

  native.addEventListener("pointerdown", sync);
  native.addEventListener("focus", sync);

  native.addEventListener("input", () => {
    if (!native.value) return;
    input.value = isoToDMY(native.value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });

  return () => {
    sync();
    try {
      if (typeof native.showPicker === "function") native.showPicker();
      else native.click();
    } catch (error) {
      native.click();
    }
  };
}

function toast(message, kind = "") {
  els.toast.textContent = message;
  els.toast.className = "toast " + kind;
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    els.toast.hidden = true;
  }, 6500);
}

async function api(path, { method = "GET", body = null } = {}) {
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }
  if (!response.ok) {
    throw new Error((data && data.error) || `Error ${response.status}`);
  }
  return data;
}

function syncButtons() {
  els.previewBtn.disabled = state.busy || state.engineOk === false;
  const nothingSelected = state.selectable && state.selected.size === 0;
  els.applyBtn.disabled = state.busy || !state.preview || state.previewStale || nothingSelected;
  els.cancelBtn.hidden = !state.busy;
}

function setBusy(busy) {
  state.busy = busy;
  syncButtons();
}

function formParams() {
  const scope = (document.querySelector('input[name="scope"]:checked') || {}).value || "originals";
  return {
    users: els.users.value.trim(),
    from: dmyToISO(els.from.value),
    to: dmyToISO(els.to.value),
    scope,
    limit: Number(els.limit.value || 10),
    delay: Number(els.delay.value || 20),
    match: els.match.value.trim(),
    exclude: els.exclude.value.trim(),
    quote: els.quote.value.trim(),
  };
}

function validateParams(params, { apply = false } = {}) {
  if (!params.users) throw new Error("Indica al menos una cuenta.");
  const fromError = dateError(els.from.value);
  if (fromError) throw new Error(`Fecha desde: ${fromError}`);
  const toError = dateError(els.to.value);
  if (toError) throw new Error(`Fecha hasta: ${toError}`);
  if (params.from > params.to) throw new Error("La fecha inicial no puede ser posterior a la final.");
  if (!(params.limit >= 1 && params.limit <= 50)) throw new Error("El máximo debe estar entre 1 y 50.");
  const minDelay = apply ? 5 : 0;
  if (!(params.delay >= minDelay && params.delay <= 300)) {
    throw new Error(`La pausa debe estar entre ${minDelay} y 300 segundos.`);
  }
  const quote = normalizeQuote(params.quote);
  if (params.quote && !quote) {
    throw new Error("El comentario debe ser un hashtag, por ejemplo #ETECSA.");
  }
  if (quote.length > MAX_QUOTE) {
    throw new Error(`El comentario es demasiado largo (máximo ${MAX_QUOTE} caracteres).`);
  }
  params.quote = quote;
}

function invalidatePreview() {
  if (!state.preview) return;
  state.previewStale = true;
  els.applyNote.textContent = "Los datos cambiaron; vuelve a previsualizar para repostear.";
  els.resultFoot.hidden = false;
  syncButtons();
}

function showJobPanel(label, { openLog = false } = {}) {
  els.jobPanel.hidden = false;
  els.jobSpinner.hidden = false;
  els.jobCancel.hidden = false;
  els.jobStatus.textContent = label;
  els.jobElapsed.textContent = "";
  els.jobLog.textContent = "";
  els.jobProgress.hidden = true;
  els.jobProgressBar.style.width = "0%";
  els.jobProgressText.textContent = "";
  els.logBox.open = openLog;
}

function hideJobPanel() {
  els.jobPanel.hidden = true;
  els.jobSpinner.hidden = true;
  els.jobCancel.hidden = true;
}

function renderLog(lines) {
  const nearBottom =
    els.jobLog.scrollTop + els.jobLog.clientHeight >= els.jobLog.scrollHeight - 24;
  els.jobLog.textContent = lines.join("\n");
  if (nearBottom) els.jobLog.scrollTop = els.jobLog.scrollHeight;
}

function statusLabel(job) {
  if (job.status === "running") {
    if (job.kind === "apply") return "Reposteando…";
    if (job.kind === "undo") return "Deshaciendo…";
    return "Buscando en X…";
  }
  if (job.status === "done") return "Completado";
  if (job.status === "cancelled") return "Cancelado";
  return "Error";
}

function watchJob(id, onDone, onFail) {
  state.jobId = id;
  rememberJob(id);
  setBusy(true);
  if (state.poll) clearInterval(state.poll);

  let pollErrors = 0;
  const tick = async () => {
    let job;
    try {
      job = await api(`/api/jobs/${id}`);
      pollErrors = 0;
    } catch (error) {
      // Un fallo puntual de red no debe abandonar un trabajo que sigue
      // corriendo en el servidor: se toleran varios antes de rendirse.
      pollErrors += 1;
      if (pollErrors < 3) return;
      clearInterval(state.poll);
      state.poll = null;
      state.jobId = null;
      forgetJob();
      setBusy(false);
      toast(error.message, "bad");
      return;
    }

    renderLog(job.lines || []);
    els.jobElapsed.textContent = job.elapsed_label || "";
    els.jobStatus.textContent = statusLabel(job);
    els.jobSpinner.hidden = job.status !== "running";
    els.jobCancel.hidden = job.status !== "running";

    if (job.kind === "apply" && job.posts && job.posts.length) {
      updatePostStatuses(job.posts);
      const progress = job.progress || { done: 0, total: job.posts.length };
      if (progress.total > 0) {
        els.jobProgress.hidden = false;
        els.jobProgressBar.style.width =
          Math.min(100, Math.round((100 * progress.done) / progress.total)) + "%";
        els.jobProgressText.textContent = `${progress.done} de ${progress.total}`;
        if (job.status === "running") {
          els.resultSub.textContent = `Reposteando… ${progress.done} de ${progress.total}`;
        }
      }
    }

    if (job.status === "running") return;

    clearInterval(state.poll);
    state.poll = null;
    state.jobId = null;
    forgetJob();
    setBusy(false);

    if (job.status === "done") {
      if (job.kind === "apply") {
        const okPosts = (job.posts || []).filter((post) => /^(reposteado|citado)/i.test(post.estado || ""));
        const quoted = okPosts.some((post) => /^citado/i.test(post.estado || ""));
        const kind = quoted ? "cita(s)" : "repost(s)";
        toast(
          okPosts.length
            ? `${okPosts.length} ${kind} completados.`
            : "Ejecución terminada sin reposts nuevos.",
          "ok",
        );
      } else if (job.kind === "undo") {
        toast("Deshacer completado.", "ok");
      } else {
        toast("Previsualización lista.", "ok");
      }
      if (onDone) onDone(job);
    } else if (job.status === "cancelled") {
      toast("Ejecución cancelada.", "bad");
      if (onFail) onFail(job);
    } else {
      toast(job.error || "La ejecución falló.", "bad");
      els.logBox.open = true;
      if (onFail) onFail(job);
    }

    if (job.kind === "undo") loadHistory();
    refreshHealth();
  };

  state.poll = setInterval(tick, 700);
  tick();
}

// --- recordar el trabajo en curso y el formulario (sobreviven a recargas) ---

function rememberJob(id) {
  try { sessionStorage.setItem("xrepost.job", id); } catch (_) { /* modo privado */ }
}

function forgetJob() {
  try { sessionStorage.removeItem("xrepost.job"); } catch (_) { /* modo privado */ }
}

const FORM_KEY = "xrepost.form";
let formTimer = null;

function saveForm() {
  clearTimeout(formTimer);
  formTimer = setTimeout(() => {
    const data = {
      users: els.users.value,
      from: els.from.value,
      to: els.to.value,
      scope: (document.querySelector('input[name="scope"]:checked') || {}).value || "originals",
      limit: els.limit.value,
      delay: els.delay.value,
      match: els.match.value,
      exclude: els.exclude.value,
      quote: els.quote.value,
    };
    try { localStorage.setItem(FORM_KEY, JSON.stringify(data)); } catch (_) { /* modo privado */ }
  }, 300);
}

function restoreForm() {
  let data = null;
  try { data = JSON.parse(localStorage.getItem(FORM_KEY) || "null"); } catch (_) { data = null; }
  const today = isoToDMY(todayISO());
  if (!data || typeof data !== "object") {
    els.from.value = today;
    els.to.value = today;
    return;
  }
  els.users.value = String(data.users || "");
  els.from.value = String(data.from || today);
  els.to.value = String(data.to || today);
  els.limit.value = String(data.limit || 10);
  els.delay.value = String(data.delay || 20);
  els.match.value = String(data.match || "");
  els.exclude.value = String(data.exclude || "");
  els.quote.value = String(data.quote || "");
  const scope = data.scope === "all" ? "all" : "originals";
  const radio = document.querySelector(`input[name="scope"][value="${scope}"]`);
  if (radio) radio.checked = true;
}

// Rellena el formulario con los parámetros de un trabajo (reconexión).
function fillFormFromParams(params) {
  els.users.value = params.users || "";
  els.from.value = isoToDMY(params.from);
  els.to.value = isoToDMY(params.to);
  els.limit.value = String(params.limit ?? 10);
  els.delay.value = String(params.delay ?? 20);
  els.match.value = params.match || "";
  els.exclude.value = params.exclude || "";
  els.quote.value = params.quote || "";
  const radio = document.querySelector(
    `input[name="scope"][value="${params.scope === "all" ? "all" : "originals"}"]`
  );
  if (radio) radio.checked = true;
  updateQuotePreview();
}

// Adopta una previsualización (nueva o recuperada tras recargar la página).
function adoptPreview(job) {
  const posts = job.posts || [];
  if (!posts.length) {
    state.preview = null;
    state.previewParams = null;
    renderPosts([]);
    els.exports.hidden = true;
    els.resultSub.textContent = "Sin resultados";
    els.empty.hidden = false;
    els.empty.querySelector("p").textContent =
      "No hay publicaciones en ese rango con los filtros actuales.";
    els.resultFoot.hidden = true;
    syncButtons();
    return;
  }
  state.preview = job;
  state.previewParams = job.params;
  state.previewStale = false;
  fillFormFromParams(job.params);
  els.postsFilter.value = "";
  renderPosts(posts, { selectable: true });
  els.resultSub.textContent = summaryText(posts, job.params);
  els.exports.hidden = false;
  els.exportCsv.href = `/api/jobs/${job.id}/export/csv`;
  els.exportMd.href = `/api/jobs/${job.id}/export/md`;
  updateSelectionNote();
  syncButtons();
}

async function resumeJob() {
  let id = null;
  try { id = sessionStorage.getItem("xrepost.job"); } catch (_) { id = null; }
  if (!id) return;
  let job;
  try {
    job = await api(`/api/jobs/${id}`);
  } catch (_) {
    forgetJob();
    return;
  }
  if (job.status === "running") {
    showJobPanel(statusLabel(job), { openLog: job.kind === "apply" });
    if (job.kind === "apply") {
      state.selectable = false;
      els.pickTh.hidden = true;
      if (job.posts && job.posts.length) renderPosts(job.posts, { selectable: false });
    }
    watchJob(id, job.kind === "preview" ? adoptPreview : finishApply);
    return;
  }
  forgetJob();
  if (job.status === "done" && job.kind === "preview" && (job.posts || []).length) {
    adoptPreview(job);
  } else if (job.status === "done" && job.kind === "apply") {
    finishApply(job);
  }
}

async function runPreview(event) {
  event.preventDefault();
  hideCombos();
  if (state.busy) return;

  let params;
  try {
    params = formParams();
    validateParams(params);
  } catch (error) {
    toast(error.message, "bad");
    return;
  }

  state.preview = null;
  state.previewParams = null;
  state.previewStale = false;
  state.selectable = false;
  els.applyBtn.disabled = true;
  els.exports.hidden = true;
  els.tableTools.hidden = true;
  els.pickTh.hidden = true;
  els.tableWrap.hidden = true;
  els.empty.hidden = true;
  els.resultFoot.hidden = true;
  els.resultSub.textContent = "Buscando publicaciones en X…";
  showJobPanel("Buscando en X…");
  setBusy(true);

  try {
    const { id } = await api("/api/preview", { method: "POST", body: params });
    watchJob(id, adoptPreview, (job) => {
      renderPosts([]);
      els.resultSub.textContent = "No se pudo previsualizar.";
      els.empty.hidden = false;
      els.empty.querySelector("p").textContent =
        job.error || "El motor no pudo completar la búsqueda. Revisa el registro.";
      els.applyBtn.disabled = true;
    });
  } catch (error) {
    setBusy(false);
    hideJobPanel();
    els.empty.hidden = false;
    els.resultSub.textContent = "No se pudo previsualizar.";
    toast(error.message, "bad");
  }
}

function summaryText(posts, params) {
  const byUser = new Map();
  for (const post of posts) {
    const key = post.usuario || post.autor || "—";
    byUser.set(key, (byUser.get(key) || 0) + 1);
  }
  const detail = Array.from(byUser.entries())
    .map(([user, count]) => `${count} de ${user}`)
    .join(" · ");
  const scope = params.scope === "all" ? "con retweets" : "solo originales";
  const quote = params.quote ? ` · cita ${params.quote}` : "";
  return `${posts.length} publicación(es) · ${detail} · ${isoToDMY(params.from)} → ${isoToDMY(params.to)} · ${scope}${quote}`;
}

function statusClass(text) {
  if (/^(reposteado|deshecho)$/i.test(text) || /^citado/i.test(text)) return "ok";
  if (/^(ya estaba|no |sin )/i.test(text)) return "bad";
  return "info";
}

// Clave ordenable para fechas DD/MM/AAAA HH:MM (o ISO como respaldo).
function postSortKey(post) {
  const value = String(post.fecha || "");
  const dmy = /^(\d{2})\/(\d{2})\/(\d{4})(?:[ T](\d{2}):(\d{2}))?/.exec(value);
  if (dmy) return `${dmy[3]}${dmy[2]}${dmy[1]}${dmy[4] || "00"}${dmy[5] || "00"}`;
  const iso = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(value);
  if (iso) return `${iso[1]}${iso[2]}${iso[3]}${iso[4] || "00"}${iso[5] || "00"}`;
  return value;
}

function postsView() {
  const needle = els.postsFilter.value.trim().toLowerCase();
  let view = state.posts;
  if (needle) {
    view = view.filter((post) =>
      [post.texto, post.autor, post.usuario].some((field) =>
        String(field || "").toLowerCase().includes(needle)
      )
    );
  }
  const order = els.postsSort.value;
  view = [...view];
  if (order === "date-asc") view.sort((a, b) => postSortKey(a).localeCompare(postSortKey(b)));
  else if (order === "author") {
    view.sort((a, b) =>
      String(a.usuario || a.autor || "").localeCompare(String(b.usuario || b.autor || "")) ||
      postSortKey(b).localeCompare(postSortKey(a))
    );
  } else view.sort((a, b) => postSortKey(b).localeCompare(postSortKey(a)));
  return view;
}

function renderPosts(posts, { selectable = false } = {}) {
  state.posts = posts || [];
  state.selectable = selectable && state.posts.length > 0;
  if (state.selectable) {
    state.selected = new Set(state.posts.map((post) => post.url));
  }
  drawPosts();
}

// Dibuja las filas según filtro/orden actuales, sin tocar la selección.
function drawPosts() {
  els.pickTh.hidden = !state.selectable;
  els.tableTools.hidden = state.posts.length === 0;
  els.postsBody.replaceChildren();

  if (!state.posts.length) {
    els.tableWrap.hidden = true;
    els.postsCount.textContent = "";
    return;
  }

  const view = postsView();
  const fragment = document.createDocumentFragment();
  for (const post of view) {
    const row = document.createElement("tr");
    row.dataset.url = post.url || "";

    if (state.selectable) {
      const pick = document.createElement("td");
      pick.className = "pick";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = state.selected.has(post.url);
      checkbox.setAttribute("aria-label", `Seleccionar publicación de ${post.usuario || post.autor || "cuenta desconocida"}`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.selected.add(post.url);
        else state.selected.delete(post.url);
        updateSelectionNote();
        syncButtons();
      });
      pick.append(checkbox);
      row.append(pick);
    }

    const date = document.createElement("td");
    date.className = "date";
    date.dataset.label = "Fecha";
    date.textContent = fmtDateTime(post.fecha);

    const author = document.createElement("td");
    author.className = "author";
    author.dataset.label = "Autor";
    const name = document.createElement("strong");
    name.textContent = post.autor || "—";
    const handle = document.createElement("small");
    handle.textContent = post.usuario || "";
    author.append(name, handle);

    const body = document.createElement("td");
    body.className = "post";
    body.dataset.label = "Publicación";
    const text = document.createElement("div");
    text.className = "text";
    text.textContent = post.texto || "(sin texto)";
    const link = document.createElement("a");
    link.href = post.url || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Ver en X ↗";
    body.append(text, link);

    const status = document.createElement("td");
    status.dataset.label = "Estado";
    const pill = document.createElement("span");
    pill.className = "pill " + statusClass(post.estado || "");
    pill.textContent = post.estado || "—";
    status.append(pill);

    row.append(date, author, body, status);
    fragment.append(row);
  }

  els.postsBody.append(fragment);
  els.tableWrap.hidden = false;
  els.empty.hidden = true;
  updatePostsCount(view.length);
  syncPickAll();
}

function updatePostsCount(visible) {
  const total = state.posts.length;
  let text = visible === total ? `${total} publicaciones` : `${visible} de ${total} publicaciones`;
  if (state.selectable) text += ` · ${state.selected.size} seleccionadas`;
  els.postsCount.textContent = text;
}

function syncPickAll() {
  if (!state.selectable) return;
  const total = state.posts.length;
  const chosen = state.selected.size;
  els.pickAll.checked = total > 0 && chosen === total;
  els.pickAll.indeterminate = chosen > 0 && chosen < total;
}

function updateSelectionNote() {
  syncPickAll();
  updatePostsCount(postsView().length);
  if (!state.preview || !state.selectable) return;
  const params = state.previewParams || {};
  const chosen = state.selected.size;
  const cap = Math.min(Number(params.limit) || chosen, chosen);
  const what = params.quote ? `citas con el comentario «${params.quote}»` : "reposts";
  els.applyNote.textContent = chosen
    ? `${chosen} de ${state.posts.length} publicaciones seleccionadas · se publicarán como máximo ${cap} ${what}, exactamente las marcadas.`
    : "No hay publicaciones seleccionadas; marca al menos una para repostear.";
  els.resultFoot.hidden = false;
}

// Actualiza solo los estados de las filas existentes (progreso en vivo).
function updatePostStatuses(posts) {
  const byUrl = new Map(posts.map((post) => [post.url, post.estado || ""]));
  for (const row of els.postsBody.querySelectorAll("tr[data-url]")) {
    const stateText = byUrl.get(row.dataset.url);
    if (stateText === undefined) continue;
    const pill = row.querySelector(".pill");
    if (pill && pill.textContent !== stateText) {
      pill.textContent = stateText;
      pill.className = "pill " + statusClass(stateText);
    }
  }
}

function fmtDuration(seconds) {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `~${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) {
    const rest = total % 60;
    return `~${minutes} min${rest ? ` ${rest} s` : ""}`;
  }
  return `~${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

function openConfirm() {
  if (!state.preview || state.previewStale || state.busy) return;
  if (state.selectable && state.selected.size === 0) {
    toast("Selecciona al menos una publicación para repostear.", "bad");
    return;
  }
  const params = state.previewParams;
  const total = state.posts.length;
  const chosen = state.selectable ? state.selected.size : total;
  const cap = Math.min(Number(params.limit) || chosen, chosen);

  els.confirmSummary.replaceChildren();
  const rows = [
    ["Cuentas", params.users],
    ["Fechas", `${isoToDMY(params.from)} → ${isoToDMY(params.to)}`],
    ["Cita", params.quote || "Sin cita (repost normal)"],
    ["Alcance", params.scope === "all" ? "Originales y retweets de otras cuentas" : "Solo publicaciones originales"],
    ["Se publicarán", `${cap} de ${chosen} seleccionadas (${total} revisadas)`],
    ["Pausa", `${params.delay} s entre reposts`],
    ["Duración estimada", fmtDuration(cap * (Number(params.delay) + 8))],
  ];
  if (params.match) rows.push(["Incluir", params.match]);
  if (params.exclude) rows.push(["Excluir", params.exclude]);

  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    els.confirmSummary.append(dt, dd);
  }

  els.confirmCheck.checked = false;
  els.confirmGo.disabled = true;
  els.confirmDialog.showModal();
}

function finishApply(job) {
  state.preview = null;
  state.previewParams = null;
  state.previewStale = false;
  state.selectable = false;
  els.pickTh.hidden = true;
  const posts = job.posts || [];
  renderPosts(posts, { selectable: false });
  const processed = posts.filter(
    (post) => !/^(no procesado|pendiente|solo listado)/i.test(post.estado || ""),
  );
  els.resultSub.textContent = `Resultado · ${processed.length} de ${posts.length} publicaciones procesadas`;
  if (job.exports && job.exports.csv) {
    els.exportCsv.href = `/api/jobs/${job.id}/export/csv`;
    els.exportMd.href = `/api/jobs/${job.id}/export/md`;
    els.exports.hidden = false;
  }
  els.applyNote.textContent = "La ejecución terminó. Revisa el historial o vuelve a previsualizar para actualizar el listado.";
  els.resultFoot.hidden = false;
  els.logBox.open = true;
  syncButtons();
  loadHistory();
}

async function confirmApply() {
  if (!state.preview || !state.previewParams || state.busy) return;
  if (!els.confirmCheck.checked) return;
  if (state.selectable && state.selected.size === 0) {
    toast("Selecciona al menos una publicación para repostear.", "bad");
    return;
  }

  const params = state.previewParams;
  try {
    validateParams(params, { apply: true });
  } catch (error) {
    toast(error.message, "bad");
    return;
  }
  const previewId = state.preview.id;
  const selectedUrls = state.selectable ? Array.from(state.selected) : null;
  els.confirmDialog.close();

  // Durante la tanda la tabla muestra el progreso, no casillas de selección.
  renderPosts(state.posts, { selectable: false });
  showJobPanel("Reposteando…", { openLog: true });
  setBusy(true);

  try {
    const body = { ...params, preview_id: previewId, confirm: true };
    if (selectedUrls) body.selected_urls = selectedUrls;
    const { id } = await api("/api/apply", { method: "POST", body });
    watchJob(id, finishApply);
  } catch (error) {
    setBusy(false);
    hideJobPanel();
    toast(error.message, "bad");
  }
}

async function openUndo(target) {
  if (state.busy) return;
  state.undoTarget = target;
  els.undoDetail.replaceChildren();
  els.undoDetail.hidden = true;
  els.undoN.value = "";
  els.undoConfirm.disabled = false;

  if (target.mode === "last") {
    els.undoTitle.textContent = "Deshacer la última tanda";
    els.undoText.textContent =
      "Se quitarán los reposts que la herramienta hizo en la última ejecución y que sigan vigentes. No se tocan los reposts que ya estaban antes en la cuenta.";
    els.undoNLabel.hidden = false;
    els.undoDialog.showModal();
    try {
      const data = await api("/api/history?n=200");
      const entries = data.entries || [];
      const undoable = entries.filter((entry) => entry.undoable && entry.url);
      const lastRun = undoable.length ? undoable[0].run : "";
      const batch = lastRun ? undoable.filter((entry) => entry.run === lastRun) : undoable;
      renderUndoDetail(batch);
    } catch (_) {
      // Sin detalle el diálogo sigue siendo usable: el motor decide al ejecutar.
    }
  } else {
    els.undoTitle.textContent = "Deshacer este repost";
    els.undoText.textContent =
      "Se quitará el repost de esta publicación. Solo se deshace si lo hizo la herramienta.";
    els.undoNLabel.hidden = true;
    const line = document.createElement("p");
    line.textContent = target.url;
    els.undoDetail.append(line);
    els.undoDetail.hidden = false;
    els.undoDialog.showModal();
  }
}

function renderUndoDetail(batch) {
  els.undoDetail.replaceChildren();
  if (!batch.length) {
    const empty = document.createElement("p");
    empty.textContent = "No hay reposts vigentes de la herramienta que deshacer.";
    els.undoDetail.append(empty);
    els.undoConfirm.disabled = true;
  } else {
    const head = document.createElement("p");
    head.textContent = `Se desharán ${batch.length} repost(s) de la última tanda:`;
    const list = document.createElement("ul");
    for (const entry of batch.slice(0, 6)) {
      const item = document.createElement("li");
      const who = entry.handle ? `@${entry.handle}` : entry.author || entry.id;
      item.textContent = `${who} · ${fmtDateTime(entry.posted_at || entry.ts)}`;
      list.append(item);
    }
    els.undoDetail.append(head, list);
    if (batch.length > 6) {
      const more = document.createElement("p");
      more.className = "muted";
      more.textContent = `… y ${batch.length - 6} más.`;
      els.undoDetail.append(more);
    }
  }
  els.undoDetail.hidden = false;
}

async function doUndo() {
  if (!state.undoTarget || state.busy) return;
  const target = state.undoTarget;
  let n = 0;
  if (target.mode === "last" && els.undoN.value) {
    n = Number(els.undoN.value);
    if (!Number.isInteger(n) || n < 1 || n > 50) {
      toast("El número de reposts a deshacer debe estar entre 1 y 50.", "bad");
      return;
    }
  }
  els.undoDialog.close();
  showJobPanel("Deshaciendo…");
  setBusy(true);
  try {
    const body = target.mode === "last" ? { mode: "last", n } : { mode: "url", url: target.url };
    const { id } = await api("/api/undo", { method: "POST", body });
    watchJob(id, () => loadHistory());
  } catch (error) {
    setBusy(false);
    hideJobPanel();
    toast(error.message, "bad");
  }
}

async function cancelJob() {
  try {
    await api("/api/cancel", { method: "POST", body: {} });
    toast("Cancelando la ejecución…");
  } catch (error) {
    toast(error.message, "bad");
  }
}

function setChip(element, ok, text) {
  element.classList.toggle("ok", ok === true);
  element.classList.toggle("bad", ok === false);
  const dot = element.querySelector(".dot");
  const label = element.lastChild;
  if (dot) dot.setAttribute("aria-hidden", "true");
  if (label && label.nodeType === Node.TEXT_NODE) {
    label.textContent = " " + text;
  } else {
    element.textContent = text;
  }
}

async function refreshHealth() {
  try {
    const health = await api("/api/health");
    state.engineOk = health.engine_ok;
    setChip(els.chipEngine, health.engine_ok, health.engine_ok ? "Motor listo" : "Motor no encontrado");
    setChip(els.chipChrome, health.chrome, health.chrome ? "Chrome conectado" : "Chrome no detectado");
    syncButtons();
  } catch (_) {
    state.engineOk = false;
    setChip(els.chipEngine, false, "Servidor sin respuesta");
    syncButtons();
  }
}

function historyAction(action) {
  if (action === "repost") return "repost";
  if (action === "undo") return "undo";
  return action || "—";
}

function renderHistory(entries) {
  els.historyBody.replaceChildren();
  const needle = els.historyFilter.value.trim().toLowerCase();
  const view = needle
    ? entries.filter((entry) =>
        [entry.author, entry.handle, entry.result_label, entry.result, entry.quote, entry.url]
          .some((field) => String(field || "").toLowerCase().includes(needle))
      )
    : entries;

  if (!view.length) {
    els.historyWrap.hidden = true;
    els.historyEmpty.hidden = false;
    els.historyEmpty.querySelector("p").textContent = entries.length
      ? "Ninguna entrada coincide con el filtro."
      : "Todavía no hay movimientos registrados.";
    els.historyMore.hidden = true;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const entry of view) {
    const row = document.createElement("tr");

    const when = document.createElement("td");
    when.className = "date";
    when.textContent = fmtDateTime(entry.ts);
    when.title = entry.ts || "";

    const action = document.createElement("td");
    const actionPill = document.createElement("span");
    actionPill.className = "pill " + (entry.action === "undo" ? "bad" : "info");
    actionPill.textContent = historyAction(entry.action);
    action.append(actionPill);

    const result = document.createElement("td");
    const resultPill = document.createElement("span");
    resultPill.className = "pill " + statusClass(entry.result_label || "");
    resultPill.textContent = entry.result_label || entry.result || "—";
    result.append(resultPill);

    const account = document.createElement("td");
    account.className = "author";
    const accountName = document.createElement("strong");
    accountName.textContent = entry.author || "—";
    const accountHandle = document.createElement("small");
    accountHandle.textContent = entry.handle ? "@" + entry.handle : "";
    account.append(accountName, accountHandle);

    const post = document.createElement("td");
    post.className = "post";
    if (entry.url) {
      const link = document.createElement("a");
      link.href = entry.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Ver en X ↗";
      post.append(link);
    } else {
      post.textContent = entry.id || "—";
    }
    if (entry.quote) {
      const quote = document.createElement("small");
      quote.className = "history-quote";
      quote.textContent = `cita: «${entry.quote}»`;
      post.append(quote);
    }

    const controls = document.createElement("td");
    if (entry.undoable && entry.url) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn tiny danger-ghost";
      button.dataset.undo = entry.url;
      button.textContent = "Deshacer";
      controls.append(button);
    }

    row.append(when, action, result, account, post, controls);
    fragment.append(row);
  }

  els.historyBody.append(fragment);
  els.historyWrap.hidden = false;
  els.historyEmpty.hidden = true;
  els.historyMore.hidden = !(entries.length >= state.historyLimit && state.historyLimit < 200);
}

async function loadHistory() {
  try {
    const data = await api(`/api/history?n=${state.historyLimit}`);
    state.historyEntries = data.entries || [];
    renderHistory(state.historyEntries);
  } catch (error) {
    toast(error.message, "bad");
  }
}

// Vista previa en vivo del comentario de la cita (normalizado + contador).
function updateQuotePreview() {
  const raw = els.quote.value.trim();
  if (!raw) {
    els.quotePreview.hidden = true;
    els.quotePreview.textContent = "";
    return;
  }
  const normalized = normalizeQuote(raw);
  const over = normalized.length > MAX_QUOTE;
  els.quotePreview.hidden = false;
  els.quotePreview.classList.toggle("bad", over || !normalized);
  els.quotePreview.textContent = !normalized
    ? "El comentario debe ser un hashtag, por ejemplo #ETECSA."
    : `Se publicará: ${normalized} · ${normalized.length}/${MAX_QUOTE} caracteres${over ? " (demasiado largo)" : ""}`;
}

function init() {
  restoreForm();
  attachDateMask(els.from, els.fromError);
  attachDateMask(els.to, els.toError);
  updateQuotePreview();

  const openFrom = attachDatePicker(els.from, $("#from-native"));
  const openTo = attachDatePicker(els.to, $("#to-native"));
  $$(".date-pick").forEach((button) => {
    button.addEventListener("click", button.dataset.pick === "from" ? openFrom : openTo);
  });

  els.from.addEventListener("input", () => {
    const from = dmyToISO(els.from.value);
    const to = dmyToISO(els.to.value);
    if (from && to && from > to) {
      els.to.value = isoToDMY(from);
      els.to.dispatchEvent(new Event("input", { bubbles: true }));
    }
    invalidatePreview();
    saveForm();
  });
  els.to.addEventListener("input", () => {
    invalidatePreview();
    saveForm();
  });
  [els.users, els.quote, els.limit, els.delay, els.match, els.exclude].forEach((input) => {
    input.addEventListener("input", () => {
      invalidatePreview();
      saveForm();
    });
  });
  els.quote.addEventListener("input", updateQuotePreview);
  document.addEventListener("pointerdown", (event) => {
    if (!els.usersCombo.contains(event.target)) usersCombo.hide();
    if (!els.quoteCombo.contains(event.target)) quoteCombo.hide();
  });
  $$('input[name="scope"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      invalidatePreview();
      saveForm();
    });
  });

  els.postsFilter.addEventListener("input", drawPosts);
  els.postsSort.addEventListener("change", drawPosts);
  els.pickAll.addEventListener("change", () => {
    state.selected = els.pickAll.checked
      ? new Set(state.posts.map((post) => post.url))
      : new Set();
    drawPosts();
    updateSelectionNote();
    syncButtons();
  });
  els.historyFilter.addEventListener("input", () => renderHistory(state.historyEntries));
  els.historyMore.addEventListener("click", () => {
    state.historyLimit = Math.min(200, state.historyLimit + 40);
    loadHistory();
  });

  els.form.addEventListener("submit", runPreview);
  els.applyBtn.addEventListener("click", openConfirm);
  els.cancelBtn.addEventListener("click", cancelJob);
  els.jobCancel.addEventListener("click", cancelJob);
  els.confirmCheck.addEventListener("change", () => {
    els.confirmGo.disabled = !els.confirmCheck.checked;
  });
  els.confirmGo.addEventListener("click", confirmApply);
  els.undoLast.addEventListener("click", () => openUndo({ mode: "last" }));
  els.undoConfirm.addEventListener("click", doUndo);
  els.refreshHistory.addEventListener("click", loadHistory);
  els.usersClear.addEventListener("click", () => clearHistory("accounts"));
  els.quoteClear.addEventListener("click", () => clearHistory("hashtags"));
  els.historyBody.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-undo]");
    if (button) openUndo({ mode: "url", url: button.dataset.undo });
  });

  setChip(els.chipEngine, null, "Comprobando…");
  setChip(els.chipChrome, null, "Comprobando…");
  syncButtons();
  refreshHealth();
  setInterval(refreshHealth, 15000);
  loadHistory();
  resumeJob();
}

document.addEventListener("DOMContentLoaded", init);
