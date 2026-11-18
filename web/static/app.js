"use strict";

/* xrepost · panel local
 * JavaScript nativo, sin dependencias. Toda escritura envía el token CSRF de
 * la sesión; ninguna credencial se guarda en el almacenamiento del navegador.
 */

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const els = {
  // navegación y entorno
  tabs: $$(".tab"),
  panels: $$(".panel"),
  themeToggle: $("#theme-toggle"),
  themeLabel: $("#theme-label"),
  chipEngine: $("#chip-engine"),
  chipChrome: $("#chip-chrome"),
  chipCdp: $("#chip-cdp"),
  chipSession: $("#chip-session"),

  // búsqueda
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
  profileSelect: $("#profile-select"),
  profileHelp: $("#profile-help"),
  previewBtn: $("#preview-btn"),
  applyBtn: $("#apply-btn"),
  cancelBtn: $("#cancel-btn"),
  resultSub: $("#result-sub"),
  exports: $("#exports"),
  exportCsv: $("#export-csv"),
  exportMd: $("#export-md"),
  exportJson: $("#export-json"),
  exportHtml: $("#export-html"),
  exportPdf: $("#export-pdf"),
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

  // bandeja
  inboxTabCount: $("#inbox-tab-count"),
  inboxApply: $("#inbox-apply"),
  inboxImport: $("#inbox-import-file"),
  inboxRefresh: $("#inbox-refresh"),
  inboxStatus: $("#inbox-status"),
  inboxFilter: $("#inbox-filter"),
  inboxCounts: $("#inbox-counts"),
  inboxBulk: $("#inbox-bulk"),
  inboxSelectAll: $("#inbox-select-all"),
  inboxCheckAll: $("#inbox-check-all"),
  inboxApprove: $("#inbox-approve"),
  inboxReject: $("#inbox-reject"),
  inboxReset: $("#inbox-reset"),
  inboxSelected: $("#inbox-selected"),
  inboxEmpty: $("#inbox-empty"),
  inboxWrap: $("#inbox-wrap"),
  inboxBody: $("#inbox-body"),

  // cuentas
  accountsRefresh: $("#accounts-refresh"),
  accountsFilter: $("#accounts-filter"),
  accountsCount: $("#accounts-count"),
  accountsEmpty: $("#accounts-empty"),
  accountsWrap: $("#accounts-wrap"),
  accountsBody: $("#accounts-body"),
  groupForm: $("#group-form"),
  groupName: $("#group-name"),
  groupDescription: $("#group-description"),
  groupMembers: $("#group-members"),
  groupStatus: $("#group-status"),
  groupsRefresh: $("#groups-refresh"),
  groupsEmpty: $("#groups-empty"),
  groupsList: $("#groups-list"),

  // filtros
  profileList: $("#profile-list"),
  profileNew: $("#profile-new"),
  profileDuplicate: $("#profile-duplicate"),
  profileDelete: $("#profile-delete"),
  profileForm: $("#profile-form"),
  profileName: $("#profile-name"),
  fInclude: $("#f-include"),
  fExclude: $("#f-exclude"),
  fExact: $("#f-exact"),
  fHashtags: $("#f-hashtags"),
  fRegex: $("#f-regex"),
  fExcludeRegex: $("#f-exclude-regex"),
  fLang: $("#f-lang"),
  fMinLen: $("#f-min-len"),
  fMaxLen: $("#f-max-len"),
  fMedia: $("#f-media"),
  fVideo: $("#f-video"),
  fKind: $("#f-kind"),
  profileExport: $("#profile-export"),
  profileImport: $("#profile-import-file"),
  filterStatus: $("#filter-status"),

  // programación
  scheduleForm: $("#schedule-form"),
  scheduleName: $("#schedule-name"),
  scheduleFrequency: $("#schedule-frequency"),
  scheduleRunAt: $("#schedule-run-at"),
  scheduleEnabled: $("#schedule-enabled"),
  scheduleNotify: $("#schedule-notify"),
  scheduleCreate: $("#schedule-create"),
  scheduleStatus: $("#schedule-status"),
  scheduleRefresh: $("#schedule-refresh"),
  scheduleEmpty: $("#schedule-empty"),
  scheduleList: $("#schedule-list"),

  // historial
  historyEmpty: $("#history-empty"),
  historyWrap: $("#history-wrap"),
  historyBody: $("#history-body"),
  historyFilter: $("#history-filter"),
  historyMore: $("#history-more"),
  refreshHistory: $("#refresh-history"),
  historyDiagnostic: $("#history-diagnostic"),
  historyDiagBox: $("#history-diag-box"),
  undoLast: $("#undo-last"),

  // estadísticas
  statsRange: $("#stats-range"),
  statsRefresh: $("#stats-refresh"),
  statsKpis: $("#stats-kpis"),
  statsChart: $("#stats-chart"),
  statsSummary: $("#stats-summary"),
  statsAccounts: $("#stats-accounts"),
  statsAccountsEmpty: $("#stats-accounts-empty"),

  // sistema
  networkMode: $("#network-mode"),
  networkApply: $("#network-apply"),
  networkNote: $("#network-note"),
  sessionInfo: $("#session-info"),
  sessionRotate: $("#session-rotate"),
  sessionLogout: $("#session-logout"),
  backupStatus: $("#backup-status"),
  backupCreate: $("#backup-create"),
  backupBundle: $("#backup-bundle"),
  backupsWrap: $("#backups-wrap"),
  backupsBody: $("#backups-body"),
  diagnosticsRefresh: $("#diagnostics-refresh"),
  diagnosticsReport: $("#diagnostics-report"),
  diagnosticsRaw: $("#diagnostics-raw"),
  statePath: $("#state-path"),

  // diálogos
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
  restoreDialog: $("#restore-dialog"),
  restoreText: $("#restore-text"),
  restoreCheck: $("#restore-check"),
  restoreConfirm: $("#restore-confirm"),
  toast: $("#toast"),
};

const state = {
  csrf: "",
  session: null,
  tab: "search",
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
  inbox: [],
  inboxCounts: {},
  inboxSelected: new Set(),
  accounts: [],
  groups: [],
  profiles: [],
  editingProfile: "",
  schedules: [],
  backups: [],
  restorePath: "",
  pendingProfile: "",
  renderingInbox: false,
};

let toastTimer = null;
let sessionTimer = null;

/* ------------------------------------------------------------------ util */

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2), value);
    } else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function fmtNumber(value) {
  return new Intl.NumberFormat("es").format(Number(value) || 0);
}

function toast(message, kind = "") {
  els.toast.textContent = message;
  els.toast.className = "toast " + kind;
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    els.toast.hidden = true;
  }, 7000);
}

function downloadText(filename, text, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("No se pudo leer el archivo."));
    reader.readAsText(file);
  });
}

/* --------------------------------------------------------------- API/CSRF */

async function fetchSession() {
  const response = await fetch("/api/session", { headers: { Accept: "application/json" } });
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }
  if (!response.ok) {
    throw new Error((data && data.error) || `Error ${response.status}`);
  }
  state.csrf = data.csrf || "";
  state.session = data;
  return data;
}

async function ensureSession(force = false) {
  if (state.csrf && !force) return state.csrf;
  await fetchSession();
  updateSessionInfo();
  return state.csrf;
}

async function api(path, { method = "GET", body = null } = {}) {
  const options = { method, headers: { Accept: "application/json" } };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  if (!["GET", "HEAD"].includes(method)) {
    options.headers["X-CSRF-Token"] = await ensureSession();
  }

  let response = await fetch(path, options);
  if (response.status === 401 && path !== "/api/session") {
    // La sesión caducó: se crea otra y se reintenta una sola vez.
    await ensureSession(true);
    if (body !== null) options.body = JSON.stringify(body);
    options.headers["X-CSRF-Token"] = state.csrf;
    response = await fetch(path, options);
  }

  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }
  if (!response.ok) {
    const error = new Error((data && data.error) || `Error ${response.status}`);
    error.status = response.status;
    error.retryAfter = data && data.retry_after;
    throw error;
  }
  return data;
}

/* ------------------------------------------------------------------ tema */

const THEME_KEY = "xrepost.theme";

function systemTheme() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

function applyTheme(theme, persist = false) {
  document.documentElement.dataset.theme = theme;
  const light = theme === "light";
  if (els.themeToggle) {
    els.themeToggle.setAttribute("aria-pressed", light ? "true" : "false");
    els.themeToggle.title = light ? "Cambiar a tema oscuro" : "Cambiar a tema claro";
  }
  if (els.themeLabel) els.themeLabel.textContent = light ? "Tema oscuro" : "Tema claro";
  if (persist) {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch (_) {
      /* modo privado */
    }
  }
}

function initTheme() {
  let stored = null;
  try {
    stored = localStorage.getItem(THEME_KEY);
  } catch (_) {
    stored = null;
  }
  applyTheme(stored === "light" || stored === "dark" ? stored : systemTheme());
}

/* ------------------------------------------------------------------ tabs */

const TAB_LOADERS = {
  inbox: loadInbox,
  accounts: () => Promise.all([loadAccounts(), loadGroups()]),
  filters: loadProfiles,
  schedule: loadSchedules,
  history: loadHistory,
  stats: loadStats,
  system: () => Promise.all([loadNetwork(), loadBackups(), loadDiagnostics(), ensureSession()]),
};

function activateTab(name, { focus = false } = {}) {
  const known = els.tabs.some((tab) => tab.dataset.tab === name);
  if (!known) name = "search";
  state.tab = name;
  for (const tab of els.tabs) {
    const active = tab.dataset.tab === name;
    tab.setAttribute("aria-selected", active ? "true" : "false");
    tab.tabIndex = active ? 0 : -1;
    if (active && focus) tab.focus();
  }
  for (const panel of els.panels) {
    panel.hidden = panel.id !== `panel-${name}`;
  }
  try {
    localStorage.setItem("xrepost.tab", name);
  } catch (_) {
    /* modo privado */
  }
  if (location.hash !== `#${name}`) {
    history.replaceState(null, "", name === "search" ? location.pathname : `#${name}`);
  }
  const loader = TAB_LOADERS[name];
  if (loader) loader().catch((error) => toast(error.message, "bad"));
}

function initTabs() {
  els.tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
    tab.addEventListener("keydown", (event) => {
      let next = null;
      if (event.key === "ArrowRight") next = (index + 1) % els.tabs.length;
      if (event.key === "ArrowLeft") next = (index - 1 + els.tabs.length) % els.tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = els.tabs.length - 1;
      if (next === null) return;
      event.preventDefault();
      activateTab(els.tabs[next].dataset.tab, { focus: true });
    });
  });
  let initial = "search";
  try {
    initial = localStorage.getItem("xrepost.tab") || "search";
  } catch (_) {
    initial = "search";
  }
  if (location.hash) initial = location.hash.slice(1);
  activateTab(initial);
}

/* ------------------------------------------- autocompletado (cuentas/tags) */

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
  const local = {
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
      local.active = -1;
      input.removeAttribute("aria-activedescendant");
      return;
    }
    const next = Math.max(0, Math.min(index, options.length - 1));
    local.active = next;
    options.forEach((option, position) => {
      option.setAttribute("aria-selected", position === next ? "true" : "false");
    });
    const current = options[next];
    input.setAttribute("aria-activedescendant", current.id);
    current.scrollIntoView({ block: "nearest" });
  }

  function hide() {
    local.open = false;
    local.active = -1;
    local.items = [];
    local.seq += 1;
    clearTimeout(local.timer);
    local.timer = null;
    if (local.controller) local.controller.abort();
    local.controller = null;
    list.replaceChildren();
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function render(items, query) {
    list.replaceChildren();
    local.items = items;
    local.active = -1;

    if (!items.length) {
      if (query) {
        const empty = document.createElement("li");
        empty.className = "combo-empty";
        empty.textContent = config.emptyText;
        list.append(empty);
        local.open = true;
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
    local.open = true;
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  async function fetchItems() {
    if (document.activeElement !== input) return;
    const token = currentToken();
    const exclude = usedTokens(token);
    const params = new URLSearchParams({ q: token.query, limit: "8" });
    if (exclude.length) params.set("exclude", exclude.join(","));

    if (local.controller) local.controller.abort();
    local.controller = new AbortController();
    const seq = ++local.seq;
    try {
      const response = await fetch(`${config.endpoint}?${params}`, {
        signal: local.controller.signal,
        headers: { Accept: "application/json" },
      });
      if (seq !== local.seq) return;
      if (!response.ok) {
        hide();
        return;
      }
      const data = await response.json();
      if (seq !== local.seq) return;
      render(data[config.responseKey] || [], token.query);
    } catch (error) {
      if (error.name !== "AbortError" && seq === local.seq) hide();
    }
  }

  function schedule(immediate = false) {
    clearTimeout(local.timer);
    if (immediate) {
      fetchItems();
      return;
    }
    local.timer = setTimeout(fetchItems, 120);
  }

  function choose(index) {
    const item = local.items[index];
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
      if (!local.open) {
        fetchItems().then(() => {
          if (local.open && local.items.length) {
            setActive(delta > 0 ? 0 : local.items.length - 1);
          }
        });
        return;
      }
      const total = local.items.length;
      if (!total) return;
      if (local.active < 0) {
        setActive(delta > 0 ? 0 : total - 1);
      } else {
        setActive((local.active + delta + total) % total);
      }
    } else if (event.key === "Enter" && local.open && local.active >= 0) {
      event.preventDefault();
      choose(local.active);
    } else if (event.key === "Tab" && !event.shiftKey && local.open && local.active >= 0) {
      event.preventDefault();
      choose(local.active);
    } else if (event.key === "Escape" && local.open) {
      event.preventDefault();
      hide();
    }
  }

  input.addEventListener("input", () => schedule());
  input.addEventListener("focus", () => schedule(true));
  input.addEventListener("blur", () => setTimeout(hide, 120));
  input.addEventListener("keydown", onKeydown);

  return { hide, schedule, fetchItems, choose, setActive, state: local, wrap };
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
    if (isAccounts) loadAccounts().catch(() => {});
  } catch (error) {
    toast(error.message, "bad");
  }
}

/* ------------------------------------------------------------------ fechas */

function todayISO() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

const DAY_RE = /^(0[1-9]|[12]\d|3[01])$/;
const MONTH_RE = /^(0[1-9]|1[0-2])$/;

function isoToDMY(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso || "");
}

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

const MAX_QUOTE = 280;
const TAG_RE = /^[^\s#,]{1,50}$/;
const ALNUM_RE = /[\p{L}\p{N}]/u;

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

function dateError(value) {
  const digits = String(value || "").replace(/\D/g, "");
  if (!digits) return "escribe una fecha.";
  if (digits.length !== 8) return "completa la fecha (DD/MM/AAAA).";
  if (!dmyToISO(value)) return "esa fecha no existe en el calendario.";
  const year = Number(digits.slice(4, 8));
  if (year < 2006 || year > 2100) return "el año debe estar entre 2006 y 2100.";
  return "";
}

function maskDate(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 8);
  if (digits.length > 4) return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  if (digits.length > 2) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return digits;
}

function fmtDateTime(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(String(value || ""));
  if (!m) return String(value || "");
  const [, year, month, day, hh, mm] = m;
  return `${day}/${month}/${year}` + (hh ? ` ${hh}:${mm}` : "");
}

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

/* --------------------------------------------------------- formulario/base */

const FORM_KEY = "xrepost.form";
let formTimer = null;

function invalidatePreview() {
  if (!state.preview) return;
  state.previewStale = true;
  els.applyNote.textContent = "Los datos cambiaron; vuelve a previsualizar para repostear.";
  els.resultFoot.hidden = false;
  syncButtons();
}

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
      profile_id: els.profileSelect.value,
    };
    try {
      localStorage.setItem(FORM_KEY, JSON.stringify(data));
    } catch (_) {
      /* modo privado */
    }
  }, 300);
}

function restoreForm() {
  let data = null;
  try {
    data = JSON.parse(localStorage.getItem(FORM_KEY) || "null");
  } catch (_) {
    data = null;
  }
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
  state.pendingProfile = String(data.profile_id || "");
  const scope = data.scope === "all" ? "all" : "originals";
  const radio = document.querySelector(`input[name="scope"][value="${scope}"]`);
  if (radio) radio.checked = true;
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
    profile_id: els.profileSelect.value || "",
  };
}

function validateParams(params, { apply = false } = {}) {
  if (!params.users) throw new Error("Indica al menos una cuenta.");
  const fromError = dateError(els.from.value);
  if (fromError) throw new Error(`Fecha desde: ${fromError}`);
  const toError = dateError(els.to.value);
  if (toError) throw new Error(`Fecha hasta: ${toError}`);
  if (!params.from || !params.to) throw new Error("Completa las dos fechas.");
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

function fillFormFromParams(params) {
  els.users.value = params.users || "";
  els.from.value = isoToDMY(params.from);
  els.to.value = isoToDMY(params.to);
  els.limit.value = String(params.limit ?? 10);
  els.delay.value = String(params.delay ?? 20);
  els.match.value = params.match || "";
  els.exclude.value = params.exclude || "";
  els.quote.value = params.quote || "";
  els.profileSelect.value = params.profile_id || "";
  const radio = document.querySelector(
    `input[name="scope"][value="${params.scope === "all" ? "all" : "originals"}"]`
  );
  if (radio) radio.checked = true;
  updateQuotePreview();
}

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

/* -------------------------------------------------------------- trabajos */

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
  if (job.status === "interrupted") return "Interrumpido (revisa el resultado en X)";
  return "Error";
}

function rememberJob(id) {
  try {
    sessionStorage.setItem("xrepost.job", id);
  } catch (_) {
    /* modo privado */
  }
}

function forgetJob() {
  try {
    sessionStorage.removeItem("xrepost.job");
  } catch (_) {
    /* modo privado */
  }
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
          "ok"
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

    if (job.kind === "undo") loadHistory().catch(() => {});
    if (job.kind === "preview") loadInbox().catch(() => {});
    refreshHealth();
  };

  state.poll = setInterval(tick, 700);
  tick();
}

function updateExports(jobId) {
  const formats = {
    csv: els.exportCsv,
    md: els.exportMd,
    json: els.exportJson,
    html: els.exportHtml,
    pdf: els.exportPdf,
  };
  for (const [format, link] of Object.entries(formats)) {
    link.href = `/api/jobs/${jobId}/export/${format}`;
  }
  els.exports.hidden = false;
}

/* ------------------------------------------------------------- publicaciones */

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
  const profile = params.profile_id ? " · perfil de filtros" : "";
  return `${posts.length} publicación(es) · ${detail} · ${isoToDMY(params.from)} → ${isoToDMY(params.to)} · ${scope}${quote}${profile}`;
}

function statusClass(text) {
  if (/^(reposteado|deshecho|citado)/i.test(text)) return "ok";
  if (/sin confirmar|unconfirmed|no se pudo confirmar|interrump/i.test(text)) return "warn";
  if (/^(ya estaba|no |sin |error|fallo)/i.test(text)) return "bad";
  return "info";
}

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
    view.sort(
      (a, b) =>
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
      checkbox.setAttribute(
        "aria-label",
        `Seleccionar publicación de ${post.usuario || post.autor || "cuenta desconocida"}`
      );
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

/* --------------------------------------------------------------- previsualizar */

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
  updateExports(job.id);
  updateSelectionNote();
  syncButtons();
  loadInbox().catch(() => {});
}

async function resumeJob() {
  let id = null;
  try {
    id = sessionStorage.getItem("xrepost.job");
  } catch (_) {
    id = null;
  }
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
  } else if (job.status === "interrupted") {
    toast("Una ejecución anterior quedó interrumpida: revisa tu perfil de X antes de reintentar.", "bad");
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

/* ------------------------------------------------------------------ aplicar */

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
  if (params.profile_id) rows.push(["Perfil de filtros", params.profile_id]);
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
    (post) => !/^(no procesado|pendiente|solo listado)/i.test(post.estado || "")
  );
  els.resultSub.textContent = `Resultado · ${processed.length} de ${posts.length} publicaciones procesadas`;
  if (posts.length) updateExports(job.id);
  els.applyNote.textContent =
    "La ejecución terminó. Revisa el historial o vuelve a previsualizar para actualizar el listado.";
  els.resultFoot.hidden = false;
  els.logBox.open = true;
  syncButtons();
  loadHistory().catch(() => {});
  loadInbox().catch(() => {});
  loadStats().catch(() => {});
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

/* ------------------------------------------------------------------ deshacer */

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

/* ----------------------------------------------------------------- bandeja */

function inboxStatusLabel(status) {
  return (
    {
      pending: "pendiente",
      approved: "aprobada",
      rejected: "rechazada",
      queued: "en cola",
      executed: "ejecutada",
      verified: "verificada",
      unconfirmed: "sin confirmar",
      failed: "fallida",
    }[status] || status || "—"
  );
}

function inboxStatusClass(status) {
  if (status === "approved" || status === "verified") return "ok";
  if (status === "rejected" || status === "failed") return "bad";
  if (status === "unconfirmed") return "warn";
  if (status === "queued" || status === "executed") return "info";
  return "warn";
}

function updateInboxBadge() {
  const pending = Number(state.inboxCounts.pending || 0);
  els.inboxTabCount.hidden = pending === 0;
  els.inboxTabCount.textContent = String(pending);
}

function renderInboxCounts() {
  const counts = state.inboxCounts || {};
  const parts = ["pending", "approved", "rejected", "queued", "executed", "verified", "unconfirmed", "failed"]
    .filter((key) => Number(counts[key] || 0) > 0)
    .map((key) => `${counts[key]} ${inboxStatusLabel(key)}`);
  els.inboxCounts.textContent = parts.length ? parts.join(" · ") : "Sin elementos";
  updateInboxBadge();
}

function renderInbox() {
  const needle = els.inboxFilter.value.trim().toLowerCase();
  const status = els.inboxStatus.value;
  const view = state.inbox.filter((item) => {
    if (status && item.status !== status) return false;
    if (!needle) return true;
    return [item.text, item.handle, item.author, item.url].some((field) =>
      String(field || "").toLowerCase().includes(needle)
    );
  });

  els.inboxBody.replaceChildren();
  if (!view.length) {
    els.inboxWrap.hidden = true;
    els.inboxEmpty.hidden = false;
    els.inboxBulk.hidden = true;
    els.inboxApply.disabled = true;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const item of view) {
    const id = String(item.id || "");
    const row = document.createElement("tr");
    row.dataset.id = id;

    const pick = document.createElement("td");
    pick.className = "pick";
    pick.dataset.label = "Seleccionar";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.inboxSelected.has(id);
    checkbox.setAttribute("aria-label", `Seleccionar publicación de ${item.handle || "cuenta"}`);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.inboxSelected.add(id);
      else state.inboxSelected.delete(id);
      updateInboxSelection();
    });
    pick.append(checkbox);

    const date = document.createElement("td");
    date.className = "date";
    date.dataset.label = "Fecha";
    date.textContent = fmtDateTime(item.date || item.added);

    const account = document.createElement("td");
    account.className = "author";
    account.dataset.label = "Cuenta";
    const strong = document.createElement("strong");
    strong.textContent = item.author || "—";
    const small = document.createElement("small");
    small.textContent = item.handle ? "@" + item.handle : "";
    account.append(strong, small);

    const body = document.createElement("td");
    body.className = "post";
    body.dataset.label = "Publicación";
    const text = document.createElement("div");
    text.className = "text";
    text.textContent = item.text || "(sin texto)";
    body.append(text);
    if (item.url) {
      const link = document.createElement("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Ver en X ↗";
      body.append(link);
    }

    const estado = document.createElement("td");
    estado.dataset.label = "Estado";
    const pill = document.createElement("span");
    pill.className = "pill " + inboxStatusClass(item.status);
    pill.textContent = inboxStatusLabel(item.status);
    if (item.detail) pill.title = item.detail;
    estado.append(pill);
    if (item.detail) {
      const detail = document.createElement("small");
      detail.className = "history-quote";
      detail.textContent = item.detail;
      estado.append(detail);
    }

    const decide = document.createElement("td");
    decide.dataset.label = "Decisión";
    const actions = document.createElement("div");
    actions.className = "actions compact";
    if (["pending", "rejected"].includes(item.status)) {
      actions.append(
        h("button", {
          type: "button",
          class: "btn tiny",
          "data-decide": "approved",
          text: "Aprobar",
        })
      );
    }
    if (item.status !== "rejected" && ["pending", "approved"].includes(item.status)) {
      actions.append(
        h("button", {
          type: "button",
          class: "btn tiny danger-ghost",
          "data-decide": "rejected",
          text: "Rechazar",
        })
      );
    }
    actions.querySelectorAll("button[data-decide]").forEach((button) => {
      button.addEventListener("click", () => decideInbox([id], button.dataset.decide));
    });
    decide.append(actions);

    row.append(pick, date, account, body, estado, decide);
    fragment.append(row);
  }

  els.inboxBody.append(fragment);
  els.inboxWrap.hidden = false;
  els.inboxEmpty.hidden = true;
  els.inboxBulk.hidden = false;
  els.inboxApply.disabled = Number(state.inboxCounts.approved || 0) === 0;
  updateInboxSelection();
}

function updateInboxSelection() {
  const visible = state.inbox.filter((item) => {
    const status = els.inboxStatus.value;
    return !status || item.status === status;
  });
  const chosen = state.inboxSelected.size;
  els.inboxSelected.textContent = chosen ? `${chosen} seleccionadas` : "";
  const allChosen = visible.length > 0 && visible.every((item) => state.inboxSelected.has(String(item.id)));
  els.inboxSelectAll.checked = allChosen;
  els.inboxSelectAll.indeterminate = chosen > 0 && !allChosen;
  els.inboxCheckAll.checked = allChosen;
  els.inboxCheckAll.indeterminate = chosen > 0 && !allChosen;
  els.inboxApprove.disabled = chosen === 0;
  els.inboxReject.disabled = chosen === 0;
  els.inboxReset.disabled = chosen === 0;
}

async function loadInbox() {
  const params = new URLSearchParams();
  if (els.inboxStatus.value) params.set("status", els.inboxStatus.value);
  if (els.inboxFilter.value.trim()) params.set("q", els.inboxFilter.value.trim());
  params.set("limit", "500");
  const data = await api(`/api/inbox?${params}`);
  state.inbox = data.items || [];
  state.inboxCounts = data.counts || {};
  state.inboxSelected = new Set(
    Array.from(state.inboxSelected).filter((id) =>
      state.inbox.some((item) => String(item.id) === id)
    )
  );
  renderInboxCounts();
  renderInbox();
}

async function decideInbox(ids, status) {
  if (!ids.length) return;
  try {
    const data = await api("/api/inbox/decide", { method: "POST", body: { ids, status } });
    toast(`${data.changed} publicación(es) actualizadas.`, "ok");
    await loadInbox();
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function applyInbox() {
  const approved = Number(state.inboxCounts.approved || 0);
  if (!approved) {
    toast("No hay publicaciones aprobadas.", "bad");
    return;
  }
  if (
    !window.confirm(
      `Se repostearán ${approved} publicaciones aprobadas en la cuenta real de Chrome.\n` +
        "Revisa la bandeja antes de continuar. ¿Aplicar ahora?"
    )
  ) {
    return;
  }
  try {
    const { id, count } = await api("/api/inbox/apply", {
      method: "POST",
      body: { delay: Number(els.delay.value || 20) },
    });
    toast(`Aplicando ${count} publicaciones aprobadas…`, "ok");
    activateTab("search");
    showJobPanel("Reposteando…", { openLog: true });
    watchJob(id, finishApply);
  } catch (error) {
    toast(error.message, "bad");
  }
}

/* ------------------------------------------------------------------ cuentas */

function renderAccounts() {
  const needle = els.accountsFilter.value.trim().toLowerCase();
  const list = state.accounts.filter((item) => {
    if (!needle) return true;
    return [item.handle, item.alias].some((field) =>
      String(field || "").toLowerCase().includes(needle)
    );
  });
  els.accountsBody.replaceChildren();
  if (!list.length) {
    els.accountsWrap.hidden = true;
    els.accountsEmpty.hidden = false;
    els.accountsCount.textContent = state.accounts.length ? "Sin coincidencias" : "";
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const item of list) {
    const row = document.createElement("tr");

    const account = document.createElement("td");
    account.className = "author";
    const strong = document.createElement("strong");
    strong.textContent = item.alias || item.handle;
    const small = document.createElement("small");
    small.textContent = "@" + item.handle + (item.count ? ` · ${item.count} usos` : "");
    account.append(strong, small);

    const aliasCell = document.createElement("td");
    const alias = document.createElement("input");
    alias.type = "text";
    alias.className = "alias-input";
    alias.maxLength = 60;
    alias.value = item.alias || "";
    alias.setAttribute("aria-label", `Alias de @${item.handle}`);
    aliasCell.append(alias);

    const favCell = document.createElement("td");
    const fav = document.createElement("input");
    fav.type = "checkbox";
    fav.checked = Boolean(item.favorite);
    fav.setAttribute("aria-label", `Marcar @${item.handle} como favorita`);
    favCell.append(fav);

    const activity = document.createElement("td");
    activity.textContent = `${item.reposts || 0} reposts · ${item.quotes || 0} citas`;
    if (item.errors) activity.textContent += ` · ${item.errors} fallos`;

    const saveCell = document.createElement("td");
    const save = document.createElement("button");
    save.type = "button";
    save.className = "btn tiny ghost";
    save.textContent = "Guardar";
    save.addEventListener("click", () => saveAccountMeta(item.handle, alias.value, fav.checked, save));
    saveCell.append(save);

    row.append(account, aliasCell, favCell, activity, saveCell);
    fragment.append(row);
  }

  els.accountsBody.append(fragment);
  els.accountsWrap.hidden = false;
  els.accountsEmpty.hidden = true;
  els.accountsCount.textContent = `${list.length} de ${state.accounts.length} cuentas`;
}

async function saveAccountMeta(handle, alias, favorite, button) {
  button.disabled = true;
  try {
    await api("/api/accounts/meta", {
      method: "POST",
      body: { handle, alias, favorite },
    });
    const item = state.accounts.find((account) => account.handle.toLowerCase() === handle.toLowerCase());
    if (item) {
      item.alias = alias.trim();
      item.favorite = Boolean(favorite);
    }
    renderAccounts();
    toast(`@${handle} actualizada.`, "ok");
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    button.disabled = false;
  }
}

async function loadAccounts() {
  const data = await api("/api/accounts/all");
  state.accounts = data.accounts || [];
  renderAccounts();
}

function renderGroups() {
  els.groupsList.replaceChildren();
  if (!state.groups.length) {
    els.groupsList.hidden = true;
    els.groupsEmpty.hidden = false;
    return;
  }
  els.groupsEmpty.hidden = true;
  els.groupsList.hidden = false;

  for (const group of state.groups) {
    const card = document.createElement("article");
    card.className = "group-card";

    const header = document.createElement("header");
    const info = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = group.name || "Grupo";
    const desc = document.createElement("p");
    desc.textContent = group.description || `${(group.members || []).length} cuentas`;
    info.append(title, desc);

    const actions = document.createElement("div");
    actions.className = "actions compact";
    const use = document.createElement("button");
    use.type = "button";
    use.className = "btn tiny ghost";
    use.textContent = "Usar en búsqueda";
    use.addEventListener("click", () => {
      els.users.value = (group.members || []).map((member) => "@" + groupHandle(member)).join(", ");
      els.users.dispatchEvent(new Event("input", { bubbles: true }));
      activateTab("search");
      els.users.focus();
    });
    const exportCsv = document.createElement("a");
    exportCsv.className = "btn tiny ghost";
    exportCsv.href = `/api/groups/${group.id}/export?format=csv`;
    exportCsv.textContent = "CSV";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn tiny danger-ghost";
    remove.textContent = "Borrar";
    remove.addEventListener("click", () => deleteGroup(group));
    actions.append(use, exportCsv, remove);
    header.append(info, actions);

    const chips = document.createElement("div");
    chips.className = "member-chips";
    for (const member of group.members || []) {
      const handle = groupHandle(member);
      const chip = document.createElement("span");
      chip.className = "member-chip";
      const alias = (member && member.alias) || "";
      chip.append(document.createTextNode("@" + handle + (alias ? ` · ${alias}` : "")));
      const removeMember = document.createElement("button");
      removeMember.type = "button";
      removeMember.textContent = "×";
      removeMember.setAttribute("aria-label", `Quitar @${handle} del grupo`);
      removeMember.addEventListener("click", () =>
        updateGroupMembers(group.id, [handle], "remove")
      );
      chip.append(removeMember);
      chips.append(chip);
    }

    const add = document.createElement("form");
    add.className = "group-add";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "@cuenta1, @cuenta2";
    input.setAttribute("aria-label", `Añadir cuentas a ${group.name}`);
    const button = document.createElement("button");
    button.type = "submit";
    button.className = "btn tiny";
    button.textContent = "Añadir";
    add.append(input, button);
    add.addEventListener("submit", (event) => {
      event.preventDefault();
      const handles = input.value
        .split(",")
        .map((value) => value.trim().replace(/^@/, ""))
        .filter(Boolean);
      if (!handles.length) return;
      updateGroupMembers(group.id, handles, "add").then(() => {
        input.value = "";
      });
    });

    card.append(header, chips, add);
    els.groupsList.append(card);
  }
}

async function loadGroups() {
  const data = await api("/api/groups");
  state.groups = data.groups || [];
  renderGroups();
}

async function updateGroupMembers(groupId, handles, action) {
  try {
    await api(`/api/groups/${groupId}/members`, {
      method: "POST",
      body: { handles, action },
    });
    await loadGroups();
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function deleteGroup(group) {
  if (!window.confirm(`¿Borrar el grupo «${group.name}»? Las cuentas no se borran.`)) return;
  try {
    await api(`/api/groups/${group.id}/delete`, { method: "POST", body: {} });
    toast("Grupo borrado.", "ok");
    await loadGroups();
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function createGroup(event) {
  event.preventDefault();
  const members = els.groupMembers.value
    .split(",")
    .map((value) => value.trim().replace(/^@/, ""))
    .filter(Boolean);
  els.groupStatus.textContent = "Creando…";
  try {
    await api("/api/groups", {
      method: "POST",
      body: {
        name: els.groupName.value.trim(),
        description: els.groupDescription.value.trim(),
        members,
      },
    });
    els.groupForm.reset();
    els.groupStatus.textContent = "Grupo creado.";
    toast("Grupo creado.", "ok");
    await loadGroups();
  } catch (error) {
    els.groupStatus.textContent = "";
    toast(error.message, "bad");
  }
}

/* ------------------------------------------------------------------ filtros */

function filterSpec() {
  return {
    include: els.fInclude.value,
    exclude: els.fExclude.value,
    exact: els.fExact.value,
    hashtags: els.fHashtags.value,
    regex: els.fRegex.value,
    exclude_regex: els.fExcludeRegex.value,
    lang: els.fLang.value,
    min_len: Number(els.fMinLen.value || 0),
    max_len: Number(els.fMaxLen.value || 0),
    media: els.fMedia.value,
    video: els.fVideo.value,
    kind: els.fKind.value,
  };
}

function fillFilterForm(spec = {}) {
  els.fInclude.value = (spec.include || []).join(", ");
  els.fExclude.value = (spec.exclude || []).join(", ");
  els.fExact.value = (spec.exact || []).join(", ");
  els.fHashtags.value = (spec.hashtags || []).join(", ");
  els.fRegex.value = spec.regex || "";
  els.fExcludeRegex.value = spec.exclude_regex || "";
  els.fLang.value = (spec.lang || []).join(", ");
  els.fMinLen.value = String(spec.min_len || 0);
  els.fMaxLen.value = String(spec.max_len || 0);
  els.fMedia.value = spec.media || "";
  els.fVideo.value = spec.video || "";
  els.fKind.value = spec.kind || "";
}

function renderProfileOptions() {
  const current = els.profileSelect.value;
  const editing = state.editingProfile;
  els.profileSelect.replaceChildren(new Option("Sin perfil (solo los filtros de arriba)", ""));
  els.profileList.replaceChildren(new Option("Nuevo perfil…", ""));
  for (const profile of state.profiles) {
    els.profileSelect.append(new Option(profile.name, profile.id));
    els.profileList.append(new Option(profile.name, profile.id));
  }
  if (current && state.profiles.some((profile) => profile.id === current)) {
    els.profileSelect.value = current;
  }
  if (editing && state.profiles.some((profile) => profile.id === editing)) {
    els.profileList.value = editing;
  } else {
    state.editingProfile = "";
    els.profileList.value = "";
  }
}

async function loadProfiles() {
  const data = await api("/api/profiles");
  state.profiles = data.profiles || [];
  renderProfileOptions();
  if (state.pendingProfile) {
    els.profileSelect.value = state.pendingProfile;
    state.pendingProfile = "";
  }
}

function selectProfile(profileId) {
  state.editingProfile = profileId;
  const profile = state.profiles.find((item) => item.id === profileId);
  if (profile) {
    els.profileName.value = profile.name || "";
    fillFilterForm(profile.filters || {});
    els.profileExport.href = "#";
    els.profileExport.dataset.profile = profile.id;
    els.filterStatus.textContent = `Editando «${profile.name}».`;
  } else {
    els.profileName.value = "";
    fillFilterForm({});
    els.profileExport.dataset.profile = "";
    els.filterStatus.textContent = "";
  }
}

async function saveProfile(event) {
  event.preventDefault();
  const name = els.profileName.value.trim();
  if (!name) {
    toast("El perfil necesita un nombre.", "bad");
    return;
  }
  els.filterStatus.textContent = "Guardando…";
  try {
    const body = { name, filters: filterSpec() };
    if (state.editingProfile) body.id = state.editingProfile;
    const data = await api("/api/profiles", { method: "POST", body });
    state.editingProfile = data.profile.id;
    els.filterStatus.textContent = "Perfil guardado.";
    toast("Perfil guardado.", "ok");
    await loadProfiles();
    selectProfile(data.profile.id);
  } catch (error) {
    els.filterStatus.textContent = "";
    toast(error.message, "bad");
  }
}

async function duplicateProfile() {
  if (!state.editingProfile) {
    toast("Selecciona un perfil para duplicar.", "bad");
    return;
  }
  try {
    const data = await api(`/api/profiles/${state.editingProfile}/duplicate`, {
      method: "POST",
      body: {},
    });
    await loadProfiles();
    selectProfile(data.profile.id);
    toast("Perfil duplicado.", "ok");
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function deleteProfile() {
  if (!state.editingProfile) {
    toast("Selecciona un perfil para borrar.", "bad");
    return;
  }
  const profile = state.profiles.find((item) => item.id === state.editingProfile);
  if (!window.confirm(`¿Borrar el perfil «${profile ? profile.name : ""}»?`)) return;
  try {
    await api(`/api/profiles/${state.editingProfile}`, { method: "POST", body: {} });
    state.editingProfile = "";
    await loadProfiles();
    selectProfile("");
    toast("Perfil borrado.", "ok");
  } catch (error) {
    toast(error.message, "bad");
  }
}

function exportProfile() {
  const spec = filterSpec();
  const payload = {
    version: 1,
    profiles: [
      {
        name: els.profileName.value.trim() || "Perfil sin nombre",
        filters: spec,
      },
    ],
  };
  downloadText(
    "xrepost-perfil.json",
    JSON.stringify(payload, null, 2) + "\n",
    "application/json"
  );
}

async function importProfiles(file) {
  try {
    const data = JSON.parse(await readFile(file));
    const result = await api("/api/profiles/import", { method: "POST", body: data });
    await loadProfiles();
    toast(`${result.profiles.length} perfil(es) importados.`, "ok");
  } catch (error) {
    toast(error.message || "Archivo de perfiles no válido.", "bad");
  }
}

async function validateFilterSpec() {
  try {
    const data = await api("/api/filters/validate", {
      method: "POST",
      body: { filters: filterSpec() },
    });
    const active = Object.entries(data.filters || {}).filter(([, value]) => {
      if (Array.isArray(value)) return value.length > 0;
      return value !== "" && value !== 0 && value !== null;
    });
    els.filterStatus.textContent = active.length
      ? `Válido · ${active.length} criterio(s) activos.`
      : "Válido · sin criterios activos.";
  } catch (error) {
    els.filterStatus.textContent = error.message;
  }
}

/* -------------------------------------------------------------- programación */

function toLocalInput(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

function resetScheduleTime() {
  if (!els.scheduleRunAt.value) {
    els.scheduleRunAt.value = toLocalInput(new Date(Date.now() + 3600 * 1000));
  }
}

function frequencyLabel(value) {
  return { once: "una vez", daily: "cada día", weekly: "cada semana", monthly: "cada mes" }[value] || value;
}

function groupHandle(member) {
  return String((member && member.handle) || member || "").replace(/^@/, "");
}

function renderSchedules() {
  els.scheduleList.replaceChildren();
  if (!state.schedules.length) {
    els.scheduleList.hidden = true;
    els.scheduleEmpty.hidden = false;
    return;
  }
  els.scheduleEmpty.hidden = true;
  els.scheduleList.hidden = false;

  for (const item of state.schedules) {
    const card = document.createElement("article");
    card.className = "group-card";
    const header = document.createElement("header");
    const info = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = item.name || "Programación";
    const desc = document.createElement("p");
    const next = item.next_run ? fmtDateTime(item.next_run) : "sin próxima ejecución";
    desc.textContent = `${frequencyLabel(item.frequency)} · próxima: ${next}`;
    if (item.last_result) desc.textContent += ` · última: ${item.last_result}`;
    info.append(title, desc);

    const actions = document.createElement("div");
    actions.className = "actions compact";

    const run = document.createElement("button");
    run.type = "button";
    run.className = "btn tiny";
    run.textContent = "Ejecutar ahora";
    run.addEventListener("click", () => runSchedule(item));

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn tiny ghost";
    toggle.textContent = item.enabled ? "Pausar" : "Activar";
    toggle.addEventListener("click", () => toggleSchedule(item));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn tiny danger-ghost";
    remove.textContent = "Borrar";
    remove.addEventListener("click", () => deleteSchedule(item));

    actions.append(run, toggle, remove);
    header.append(info, actions);
    card.append(header);
    els.scheduleList.append(card);
  }
}

async function loadSchedules() {
  const data = await api("/api/schedules");
  state.schedules = data.schedules || [];
  resetScheduleTime();
  renderSchedules();
}

async function createSchedule(event) {
  event.preventDefault();
  let params;
  try {
    params = formParams();
    validateParams(params);
  } catch (error) {
    toast(error.message, "bad");
    return;
  }
  const runAt = els.scheduleRunAt.value;
  if (!runAt) {
    toast("Indica la primera ejecución.", "bad");
    return;
  }
  els.scheduleStatus.textContent = "Guardando…";
  try {
    await api("/api/schedules", {
      method: "POST",
      body: {
        name: els.scheduleName.value.trim(),
        params,
        frequency: els.scheduleFrequency.value,
        run_at: new Date(runAt).toISOString(),
        enabled: els.scheduleEnabled.checked,
        notify: els.scheduleNotify.checked,
      },
    });
    els.scheduleForm.reset();
    els.scheduleEnabled.checked = true;
    els.scheduleNotify.checked = true;
    els.scheduleStatus.textContent = "Programación creada.";
    toast("Programación creada. Solo ejecutará previsualizaciones.", "ok");
    await loadSchedules();
  } catch (error) {
    els.scheduleStatus.textContent = "";
    toast(error.message, "bad");
  }
}

async function runSchedule(item) {
  try {
    const { id } = await api(`/api/schedules/${item.id}/run`, { method: "POST", body: {} });
    toast("Previsualización programada iniciada.", "ok");
    activateTab("search");
    showJobPanel("Buscando en X…");
    watchJob(id, adoptPreview);
    await loadSchedules();
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function toggleSchedule(item) {
  try {
    await api(`/api/schedules/${item.id}`, {
      method: "POST",
      body: { enabled: !item.enabled },
    });
    await loadSchedules();
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function deleteSchedule(item) {
  if (!window.confirm(`¿Borrar la programación «${item.name}»?`)) return;
  try {
    await api(`/api/schedules/${item.id}/delete`, { method: "POST", body: {} });
    toast("Programación borrada.", "ok");
    await loadSchedules();
  } catch (error) {
    toast(error.message, "bad");
  }
}

/* ---------------------------------------------------------------- historial */

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
        [entry.author, entry.handle, entry.result_label, entry.result, entry.quote, entry.url].some(
          (field) => String(field || "").toLowerCase().includes(needle)
        )
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
    when.dataset.label = "Cuándo";
    when.textContent = fmtDateTime(entry.ts);
    when.title = entry.ts || "";

    const action = document.createElement("td");
    action.dataset.label = "Acción";
    const actionPill = document.createElement("span");
    actionPill.className = "pill " + (entry.action === "undo" ? "bad" : "info");
    actionPill.textContent = historyAction(entry.action);
    action.append(actionPill);

    const result = document.createElement("td");
    result.dataset.label = "Resultado";
    const resultPill = document.createElement("span");
    resultPill.className = "pill " + statusClass(entry.result_label || "");
    resultPill.textContent = entry.result_label || entry.result || "—";
    result.append(resultPill);

    const account = document.createElement("td");
    account.className = "author";
    account.dataset.label = "Cuenta";
    const accountName = document.createElement("strong");
    accountName.textContent = entry.author || "—";
    const accountHandle = document.createElement("small");
    accountHandle.textContent = entry.handle ? "@" + entry.handle : "";
    account.append(accountName, accountHandle);

    const post = document.createElement("td");
    post.className = "post";
    post.dataset.label = "Publicación";
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
    controls.dataset.label = "Acciones";
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
  const data = await api(`/api/history?n=${state.historyLimit}`);
  state.historyEntries = data.entries || [];
  renderHistory(state.historyEntries);
}

async function showHistoryDiagnostic() {
  try {
    const report = await api("/api/history/diagnostic");
    els.historyDiagBox.replaceChildren();
    const head = document.createElement("strong");
    head.textContent = report.exists
      ? `Historial: ${report.total_events} eventos válidos, ${report.corrupt_events} corruptos, ${report.archives.length} archivo(s) rotados.`
      : "El historial todavía no existe.";
    els.historyDiagBox.append(head);
    if (Array.isArray(report.warnings) && report.warnings.length) {
      const list = document.createElement("ul");
      for (const warning of report.warnings) list.append(h("li", { text: warning }));
      els.historyDiagBox.append(list);
    }
    els.historyDiagBox.hidden = false;
  } catch (error) {
    toast(error.message, "bad");
  }
}

/* -------------------------------------------------------------- estadísticas */

function statCard(label, value, tone = "") {
  return h("div", { class: `kpi ${tone}`.trim() }, h("strong", { text: fmtNumber(value) }), h("span", { text: label }));
}

function renderStats(data) {
  els.statsKpis.replaceChildren(
    statCard("Confirmados", data.confirmed_total, "green"),
    statCard("Reposts", data.reposts_confirmed, "blue"),
    statCard("Citas", data.quotes, "blue"),
    statCard("Deshechos", data.undone),
    statCard("Sin confirmar / fallos", data.errors, "amber")
  );

  const previousLegend = els.statsChart.parentElement.querySelector(".chart-legend");
  if (previousLegend) previousLegend.remove();
  els.statsChart.replaceChildren();
  const daily = Array.isArray(data.daily) ? data.daily : [];
  const max = Math.max(1, ...daily.map((item) => Number(item.events) || 0));
  for (const item of daily) {
    const events = Number(item.events) || 0;
    const bar = document.createElement("div");
    bar.className = "bar";
    bar.style.height = `${Math.max(events ? 6 : 2, Math.round((events / max) * 100))}%`;
    bar.dataset.empty = events ? "0" : "1";
    bar.title = `${fmtDateTime(item.date)}: ${events} evento(s)`;
    bar.setAttribute("aria-label", `${item.date}: ${events} eventos`);
    els.statsChart.append(bar);
  }
  const legend = h(
    "div",
    { class: "chart-legend" },
    h("span", { text: daily.length ? fmtDateTime(daily[0].date) : "—" }),
    h("span", { text: daily.length ? fmtDateTime(daily[daily.length - 1].date) : "—" })
  );
  els.statsChart.after(legend);

  els.statsSummary.replaceChildren();
  const rows = [
    ["Tasa de confirmación", `${data.confirmation_rate}% (${data.confirmed_total}/${data.rate_denominator})`],
    ["Encontrados en previsualizaciones", fmtNumber(data.found)],
    ["Eventos totales", fmtNumber(data.total_events)],
    ["Bandeja aprobada", fmtNumber(data.approved)],
    ["Bandeja verificada", fmtNumber(data.verified)],
    ["Bandeja pendiente", fmtNumber(data.inbox_pending)],
    ["Última actividad", data.last_activity ? fmtDateTime(data.last_activity) : "—"],
    ["Trabajos", `${data.jobs.total} (${data.jobs.previews} preview · ${data.jobs.applies} apply · ${data.jobs.undos} undo)`],
    ["Programaciones", `${data.schedules.total} · ${data.schedules.enabled} activas`],
  ];
  if (data.schedules.next) rows.push(["Próxima programación", fmtDateTime(data.schedules.next)]);
  for (const [label, value] of rows) {
    els.statsSummary.append(h("dt", { text: label }), h("dd", { text: value }));
  }

  els.statsAccounts.replaceChildren();
  const accounts = Array.isArray(data.by_account) ? data.by_account : [];
  els.statsAccountsEmpty.hidden = accounts.length > 0;
  for (const item of accounts) {
    const row = document.createElement("tr");
    const cells = [
      "@" + item.handle,
      item.reposts,
      item.quotes,
      item.undone,
      item.failed,
      item.unknown,
      item.last ? fmtDateTime(item.last) : "—",
    ];
    cells.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = index === 0 ? value : fmtNumber(value);
      row.append(cell);
    });
    els.statsAccounts.append(row);
  }
}

async function loadStats() {
  const days = els.statsRange.value || "30";
  const data = await api(`/api/stats?days=${encodeURIComponent(days)}`);
  renderStats(data);
  if (data.jobs) {
    for (const [stateName, count] of Object.entries(data.jobs.states || {})) {
      if (count) els.statsSummary.append(h("dt", { text: `Trabajos ${stateName}` }), h("dd", { text: fmtNumber(count) }));
    }
  }
}

/* ------------------------------------------------------------------ sistema */

const NETWORK_LABELS = {
  direct: "Casa · sin proxy",
  pac: "Empresa · PAC",
  auto: "Automático · PAC",
  server: "Empresa · servidor",
};

function setChip(element, ok, text) {
  if (!element) return;
  element.classList.toggle("ok", ok === true);
  element.classList.toggle("bad", ok === false);
  element.classList.toggle("warn", ok === "warn");
  const dot = element.querySelector(".dot");
  if (dot) dot.setAttribute("aria-hidden", "true");
  const label = element.lastChild;
  if (label && label.nodeType === Node.TEXT_NODE) {
    label.textContent = " " + text;
  } else {
    element.textContent = text;
  }
}

async function loadNetwork() {
  try {
    const net = await api("/api/network");
    els.networkMode.value = net.mode;
    const etiqueta = NETWORK_LABELS[net.mode] || net.mode;
    const detalle = net.mode === "server" ? `${net.proxy_scheme}://${net.proxy}` : net.mode === "direct" ? "" : "PAC";
    els.networkNote.textContent = detalle ? `${etiqueta} · ${detalle}` : etiqueta;
  } catch (_) {
    els.networkNote.textContent = "configuración no disponible";
  }
}

async function applyNetwork() {
  const mode = els.networkMode.value;
  const confirmar = window.confirm(
    "Se reiniciará Chrome con la configuración de red elegida.\n" +
      "Se cerrarán las pestañas de ese perfil de Chrome.\n" +
      "Si tienes OTROS Chrome abiertos, ciérralos antes o el nuevo no arrancará.\n\n¿Continuar?"
  );
  if (!confirmar) {
    await loadNetwork();
    return;
  }
  els.networkApply.disabled = true;
  try {
    await api("/api/network", { method: "POST", body: { mode } });
    await api("/api/network/restart", { method: "POST", body: {} });
    toast(`Red aplicada: ${NETWORK_LABELS[mode] || mode}. Chrome reiniciado.`, "ok");
    await loadNetwork();
    await refreshHealth();
  } catch (error) {
    toast(error.message || "No se pudo aplicar la red", "bad");
    await loadNetwork();
  } finally {
    els.networkApply.disabled = false;
  }
}

function updateSessionInfo() {
  const session = state.session;
  if (!session || !session.authenticated) {
    els.sessionInfo.textContent = "Sin sesión activa.";
    setChip(els.chipSession, false, "Sesión");
    return;
  }
  const minutes = Math.max(0, Math.round(Number(session.expires_in || 0) / 60));
  const idle = Math.max(0, Math.round(Number(session.idle_expires_in || 0) / 60));
  els.sessionInfo.textContent = `Autenticada · caduca en ${minutes} min · inactiva ${idle} min · ${session.rotations || 0} rotaciones.`;
  setChip(els.chipSession, true, "Sesión activa");
}

async function rotateSession() {
  try {
    const data = await api("/api/session/rotate", { method: "POST", body: {} });
    state.session = { ...data, authenticated: true };
    state.csrf = data.csrf || state.csrf;
    updateSessionInfo();
    toast("Sesión rotada.", "ok");
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function logoutSession() {
  if (!window.confirm("¿Cerrar la sesión de este panel? Tendrás que abrir un enlace con token de nuevo.")) return;
  try {
    await api("/api/session/logout", { method: "POST", body: {} });
    state.csrf = "";
    state.session = null;
    toast("Sesión cerrada. Recarga con el enlace de arranque para volver a entrar.", "ok");
    updateSessionInfo();
    els.sessionInfo.textContent = "Sesión cerrada. Abre de nuevo el enlace con token.";
  } catch (error) {
    toast(error.message, "bad");
  }
}

async function refreshHealth() {
  try {
    const health = await api("/api/health");
    state.engineOk = health.engine_ok;
    setChip(els.chipEngine, health.engine_ok, health.engine_ok ? "Motor listo" : "Motor no encontrado");
    setChip(els.chipChrome, health.chrome, health.chrome ? "Chrome conectado" : "Chrome no detectado");
    if (els.statePath && health.state_dir) els.statePath.textContent = health.state_dir;
    syncButtons();
  } catch (_) {
    state.engineOk = false;
    setChip(els.chipEngine, false, "Servidor sin respuesta");
    syncButtons();
  }
  if (state.tab === "system") {
    loadDiagnostics().catch(() => {});
  } else {
    try {
      const cdp = await api("/api/cdp");
      setChip(
        els.chipCdp,
        cdp.secure && cdp.reachable ? true : cdp.secure ? "warn" : false,
        cdp.secure ? (cdp.reachable ? "CDP seguro" : "CDP sin conexión") : "CDP no seguro"
      );
    } catch (_) {
      setChip(els.chipCdp, false, "CDP desconocido");
    }
  }
}

function diagItem(title, value, tone = "") {
  return h(
    "div",
    { class: "diag-item" },
    h("strong", { text: title }),
    h("span", { class: tone, text: value })
  );
}

function renderDiagnostics(data) {
  els.diagnosticsReport.replaceChildren();
  const history = data.history || {};
  const cdp = data.cdp || {};
  const engine = data.engine || {};
  const storage = data.storage || {};
  const jobs = data.jobs || {};
  const auth = data.auth || {};

  els.diagnosticsReport.append(
    diagItem(
      "Historial",
      history.exists
        ? `${history.total_events} eventos · ${history.corrupt_events} corruptos`
        : "sin historial todavía",
      history.exists && !history.corrupt_events ? "ok" : "warn"
    ),
    diagItem(
      "CDP",
      cdp.secure
        ? cdp.reachable
          ? "loopback verificado y accesible"
          : "loopback válido, Chrome no conectado"
        : (cdp.problems || []).join("; ") || "no seguro",
      cdp.secure && cdp.reachable ? "ok" : cdp.secure ? "warn" : "bad"
    ),
    diagItem(
      "Motor",
      engine.exists ? (engine.executable ? "existe y es ejecutable" : "existe pero no es ejecutable") : "no encontrado",
      engine.exists && engine.executable ? "ok" : "bad"
    ),
    diagItem("Almacenamiento", storage.state_dir || "—", ""),
    diagItem("Sesiones activas", String(auth.sessions || 0), ""),
    diagItem(
      "Trabajos",
      `${jobs.runtime || 0} en memoria · ${jobs.persistent || 0} persistentes`,
      ""
    )
  );

  if (history.warnings && history.warnings.length) {
    const list = h("div", { class: "diag-item" }, h("strong", { text: "Avisos del historial" }));
    list.append(h("ul", {}, ...history.warnings.map((warning) => h("li", { text: warning }))));
    els.diagnosticsReport.append(list);
  }

  setChip(
    els.chipCdp,
    cdp.secure && cdp.reachable ? true : cdp.secure ? "warn" : false,
    cdp.secure ? (cdp.reachable ? "CDP seguro" : "CDP sin conexión") : "CDP no seguro"
  );
  els.diagnosticsRaw.textContent = JSON.stringify(data, null, 2);
}

async function loadDiagnostics() {
  const data = await api("/api/diagnostics");
  renderDiagnostics(data);
}

function renderBackups() {
  els.backupsBody.replaceChildren();
  if (!state.backups.length) {
    els.backupsWrap.hidden = true;
    els.backupStatus.textContent = "Sin copias de seguridad.";
    return;
  }
  els.backupsWrap.hidden = false;
  els.backupStatus.textContent = `${state.backups.length} copia(s) verificables.`;
  for (const backup of state.backups) {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = backup.name;
    const created = document.createElement("td");
    created.textContent = fmtDateTime(backup.created);
    const size = document.createElement("td");
    size.textContent = `${Math.max(1, Math.round(Number(backup.bytes || 0) / 1024))} KB`;
    const actions = document.createElement("td");
    const restore = document.createElement("button");
    restore.type = "button";
    restore.className = "btn tiny ghost";
    restore.textContent = "Restaurar";
    restore.addEventListener("click", () => openRestore(backup.path || backup.name));
    actions.append(restore);
    row.append(name, created, size, actions);
    els.backupsBody.append(row);
  }
}

async function loadBackups() {
  const data = await api("/api/backups");
  state.backups = data.backups || [];
  renderBackups();
}

async function createBackup(mode) {
  try {
    await api("/api/backup", { method: "POST", body: { mode } });
    toast(mode === "bundle" ? "Backup completo creado." : "Backup del historial creado.", "ok");
    await loadBackups();
  } catch (error) {
    toast(error.message, "bad");
  }
}

function openRestore(path) {
  state.restorePath = path;
  els.restoreText.textContent =
    `Se restaurará «${path}». El historial actual se guarda antes como copia de seguridad.`;
  els.restoreCheck.checked = false;
  els.restoreConfirm.disabled = true;
  els.restoreDialog.showModal();
}

async function confirmRestore() {
  if (!state.restorePath || !els.restoreCheck.checked) return;
  els.restoreDialog.close();
  try {
    const data = await api("/api/restore", {
      method: "POST",
      body: { path: state.restorePath, force: false },
    });
    toast(`Historial restaurado (${data.restore.valid_events ?? data.restore.restored ?? "ok"} eventos).`, "ok");
    await Promise.all([loadBackups(), loadHistory(), loadStats().catch(() => {})]);
  } catch (error) {
    toast(error.message, "bad");
  }
}

/* -------------------------------------------------------------------- init */

function initSearchForm() {
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
  [els.users, els.quote, els.limit, els.delay, els.match, els.exclude, els.profileSelect].forEach(
    (input) => {
      input.addEventListener("input", () => {
        invalidatePreview();
        saveForm();
      });
      input.addEventListener("change", () => {
        invalidatePreview();
        saveForm();
      });
    }
  );
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
  els.historyFilter.addEventListener("input", () => renderHistory(state.historyEntries));
  els.historyMore.addEventListener("click", () => {
    state.historyLimit = Math.min(200, state.historyLimit + 40);
    loadHistory();
  });
  els.historyDiagnostic.addEventListener("click", showHistoryDiagnostic);
  els.historyBody.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-undo]");
    if (button) openUndo({ mode: "url", url: button.dataset.undo });
  });
}

function initInbox() {
  els.inboxRefresh.addEventListener("click", () => loadInbox().catch((error) => toast(error.message, "bad")));
  els.inboxStatus.addEventListener("change", () => loadInbox().catch(() => {}));
  let timer = null;
  els.inboxFilter.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => loadInbox().catch(() => {}), 250);
  });
  const selectAll = (checked) => {
    state.inboxSelected = new Set(
      checked
        ? state.inbox
            .filter((item) => !els.inboxStatus.value || item.status === els.inboxStatus.value)
            .map((item) => String(item.id))
        : []
    );
    renderInbox();
  };
  els.inboxSelectAll.addEventListener("change", () => selectAll(els.inboxSelectAll.checked));
  els.inboxCheckAll.addEventListener("change", () => selectAll(els.inboxCheckAll.checked));
  els.inboxApprove.addEventListener("click", () =>
    decideInbox(Array.from(state.inboxSelected), "approved")
  );
  els.inboxReject.addEventListener("click", () =>
    decideInbox(Array.from(state.inboxSelected), "rejected")
  );
  els.inboxReset.addEventListener("click", () =>
    decideInbox(Array.from(state.inboxSelected), "pending")
  );
  els.inboxApply.addEventListener("click", applyInbox);
  els.inboxImport.addEventListener("change", async () => {
    const file = els.inboxImport.files && els.inboxImport.files[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await readFile(file));
      const items = Array.isArray(parsed) ? parsed : parsed.items;
      if (!Array.isArray(items)) throw new Error("El archivo no contiene una lista de elementos.");
      const data = await api("/api/inbox/import", { method: "POST", body: { items } });
      toast(`${data.imported} publicaciones importadas.`, "ok");
      await loadInbox();
    } catch (error) {
      toast(error.message || "Archivo no válido.", "bad");
    } finally {
      els.inboxImport.value = "";
    }
  });
}

function initAccounts() {
  els.accountsRefresh.addEventListener("click", () => loadAccounts().catch((error) => toast(error.message, "bad")));
  els.accountsFilter.addEventListener("input", renderAccounts);
  els.groupForm.addEventListener("submit", createGroup);
  els.groupsRefresh.addEventListener("click", () => loadGroups().catch((error) => toast(error.message, "bad")));
  els.accountsBody.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.target.matches(".alias-input")) {
      event.preventDefault();
      const row = event.target.closest("tr");
      const save = row && row.querySelector("button");
      if (save) save.click();
    }
  });
}

function initFilters() {
  els.profileList.addEventListener("change", () => selectProfile(els.profileList.value));
  els.profileNew.addEventListener("click", () => {
    state.editingProfile = "";
    els.profileList.value = "";
    els.profileName.value = "";
    fillFilterForm({});
    els.filterStatus.textContent = "";
    els.profileName.focus();
  });
  els.profileDuplicate.addEventListener("click", duplicateProfile);
  els.profileDelete.addEventListener("click", deleteProfile);
  els.profileForm.addEventListener("submit", saveProfile);
  els.profileExport.addEventListener("click", (event) => {
    event.preventDefault();
    exportProfile();
  });
  els.profileImport.addEventListener("change", async () => {
    const file = els.profileImport.files && els.profileImport.files[0];
    if (file) await importProfiles(file);
    els.profileImport.value = "";
  });
  let timer = null;
  const scheduleValidate = () => {
    clearTimeout(timer);
    timer = setTimeout(() => validateFilterSpec(), 400);
  };
  [
    els.fInclude,
    els.fExclude,
    els.fExact,
    els.fHashtags,
    els.fRegex,
    els.fExcludeRegex,
    els.fLang,
    els.fMinLen,
    els.fMaxLen,
    els.fMedia,
    els.fVideo,
    els.fKind,
  ].forEach((input) => {
    input.addEventListener("input", scheduleValidate);
    input.addEventListener("change", scheduleValidate);
  });
}

function initSchedules() {
  els.scheduleForm.addEventListener("submit", createSchedule);
  els.scheduleRefresh.addEventListener("click", () => loadSchedules().catch((error) => toast(error.message, "bad")));
  resetScheduleTime();
}

function initStats() {
  els.statsRefresh.addEventListener("click", () => loadStats().catch((error) => toast(error.message, "bad")));
  els.statsRange.addEventListener("change", () => loadStats().catch(() => {}));
}

function initSystem() {
  els.networkApply.addEventListener("click", applyNetwork);
  els.sessionRotate.addEventListener("click", rotateSession);
  els.sessionLogout.addEventListener("click", logoutSession);
  els.backupCreate.addEventListener("click", () => createBackup("history"));
  els.backupBundle.addEventListener("click", () => createBackup("bundle"));
  els.diagnosticsRefresh.addEventListener("click", () =>
    loadDiagnostics().catch((error) => toast(error.message, "bad"))
  );
  els.restoreCheck.addEventListener("change", () => {
    els.restoreConfirm.disabled = !els.restoreCheck.checked;
  });
  els.restoreConfirm.addEventListener("click", confirmRestore);
}

function initThemeToggle() {
  els.themeToggle.addEventListener("click", () => {
    const current = document.documentElement.dataset.theme || systemTheme();
    applyTheme(current === "light" ? "dark" : "light", true);
  });
}

async function init() {
  initTheme();
  try {
    await ensureSession();
  } catch (error) {
    toast("No se pudo abrir la sesión del panel: " + error.message, "bad");
  }
  initSearchForm();
  initInbox();
  initAccounts();
  initFilters();
  initSchedules();
  initStats();
  initSystem();
  initThemeToggle();
  initTabs();

  setChip(els.chipEngine, null, "Comprobando…");
  setChip(els.chipChrome, null, "Comprobando…");
  setChip(els.chipCdp, null, "Comprobando…");
  syncButtons();
  updateSessionInfo();
  refreshHealth();
  loadProfiles().catch((error) => toast(error.message, "bad"));
  loadInbox().catch(() => {});
  loadHistory().catch(() => {});
  resumeJob();
  if (sessionTimer) clearInterval(sessionTimer);
  sessionTimer = setInterval(() => refreshHealth(), 30000);
}

document.addEventListener("DOMContentLoaded", init);
