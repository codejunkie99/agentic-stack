"""Static browser assets for Mission Control."""
from __future__ import annotations


def styles() -> str:
    return r"""
    :root {
      color-scheme: dark;
      --bg: #080b0f;
      --panel: #10151c;
      --panel-2: #131a22;
      --line: #26313c;
      --text: #e8edf2;
      --muted: #8f9ca8;
      --muted-2: #596672;
      --accent-good: #36d399;
      --accent-warn: #f5b85b;
      --accent-bad: #ef6b73;
      --accent-info: #8fb7ff;
      --shadow: rgba(0, 0, 0, .34);
    }
    * { box-sizing: border-box; }
    html { background: var(--bg); scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100dvh;
      background: linear-gradient(180deg, #0a0e13 0%, var(--bg) 42%);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }
    a { color: inherit; }
    .shell {
      width: min(1380px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }
    header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: end;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }
    h1, h2, h3, p { margin: 0; }
    h1 {
      font-size: clamp(1.55rem, 2.4vw, 2.4rem);
      line-height: 1.05;
      font-weight: 680;
      letter-spacing: 0;
    }
    .eyebrow, .label {
      color: var(--muted);
      font-size: .72rem;
      font-weight: 650;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .project {
      margin-top: 8px;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      overflow-wrap: anywhere;
    }
    .score {
      display: grid;
      place-items: center;
      min-width: 132px;
      min-height: 86px;
      border: 1px solid rgba(54, 211, 153, .34);
      background: rgba(16, 21, 28, .92);
      box-shadow: 0 18px 40px var(--shadow);
    }
    .score strong {
      display: block;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 2rem;
      font-variant-numeric: tabular-nums;
    }
    button, input {
      font: inherit;
    }
    button {
      cursor: pointer;
    }
    button:disabled {
      cursor: not-allowed;
      opacity: .58;
    }
    .mission-tabs {
      display: flex;
      gap: 6px;
      margin: 18px 0;
      overflow-x: auto;
      padding-bottom: 2px;
    }
    .control-plane {
      display: grid;
      grid-template-columns: minmax(172px, .28fr) minmax(0, 1fr);
      gap: 12px;
      margin: 18px 0 0;
      align-items: stretch;
    }
    .command-rail {
      display: grid;
      gap: 6px;
      align-content: start;
      padding: 10px;
      border: 1px solid var(--line);
      background: rgba(16, 21, 28, .72);
      box-shadow: 0 18px 40px var(--shadow);
    }
    .rail-button {
      width: 100%;
      min-height: 34px;
      padding: 7px 9px;
      border: 1px solid transparent;
      background: transparent;
      color: var(--muted);
      text-align: left;
      transition: border-color .18s ease, color .18s ease, background .18s ease;
    }
    .rail-button:hover, .rail-button:focus-visible, .rail-button[aria-selected="true"] {
      color: var(--text);
      border-color: #405161;
      background: rgba(19, 26, 34, .92);
      outline: none;
    }
    .telemetry-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      min-width: 0;
    }
    .telemetry {
      min-height: 72px;
      padding: 12px;
      border: 1px solid var(--line);
      background: rgba(16, 21, 28, .72);
      box-shadow: 0 18px 40px var(--shadow);
    }
    .telemetry strong {
      display: block;
      margin-top: 6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 1.1rem;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
    }
    .domain-summary {
      margin-bottom: 12px;
      color: var(--muted);
    }
    .ops-log {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .ops-event {
      padding: 8px 10px;
      border: 1px solid var(--line);
      background: #080b0f;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: .82rem;
      overflow-wrap: anywhere;
    }
    .tab-button {
      flex: 0 0 auto;
      padding: 8px 11px;
      border: 1px solid var(--line);
      background: rgba(16, 21, 28, .74);
      color: var(--muted);
      text-decoration: none;
      transition: border-color .18s ease, color .18s ease, background .18s ease;
    }
    .tab-button:hover, .tab-button:focus-visible, .tab-button[aria-selected="true"] {
      color: var(--text);
      border-color: #405161;
      background: var(--panel-2);
      outline: none;
    }
    .controls {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto auto auto;
      gap: 10px;
      align-items: center;
      margin: 0 0 14px;
    }
    .search {
      min-width: 0;
      width: 100%;
      min-height: 38px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      background: rgba(8, 11, 15, .72);
      color: var(--text);
      outline: none;
      transition: border-color .18s ease, background .18s ease;
    }
    .search:focus {
      border-color: #405161;
      background: #080b0f;
    }
    .action-button, .copy-btn {
      min-height: 34px;
      padding: 7px 10px;
      border: 1px solid var(--line);
      background: rgba(16, 21, 28, .82);
      color: var(--text);
      transition: transform .14s ease, border-color .18s ease, background .18s ease;
    }
    .action-button:hover, .copy-btn:hover {
      border-color: #405161;
      background: var(--panel-2);
    }
    .action-button:active, .copy-btn:active {
      transform: translateY(1px) scale(.99);
    }
    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--muted);
      white-space: nowrap;
    }
    .mission-panel {
      opacity: 1;
      transform: translateY(0);
      transition: opacity .18s ease, transform .18s ease;
    }
    .mission-panel[hidden] {
      display: none;
    }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1.65fr) minmax(320px, .85fr);
      gap: 14px;
      align-items: start;
    }
    section, aside {
      border: 1px solid var(--line);
      background: rgba(16, 21, 28, .88);
      box-shadow: 0 18px 40px var(--shadow);
    }
    section { margin-bottom: 14px; }
    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      min-height: 52px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }
    h2 { font-size: 1rem; font-weight: 670; letter-spacing: 0; }
    .section-body { padding: 14px 16px 16px; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .metric {
      min-height: 82px;
      border: 1px solid var(--line);
      background: var(--panel-2);
      padding: 12px;
    }
    .metric strong {
      display: block;
      margin-top: 8px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 1.35rem;
      font-variant-numeric: tabular-nums;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-variant-numeric: tabular-nums;
    }
    th, td {
      padding: 10px 8px;
      border-bottom: 1px solid rgba(38, 49, 60, .72);
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: .72rem;
      font-weight: 650;
      letter-spacing: .06em;
      text-transform: uppercase;
    }
    tr:last-child td { border-bottom: 0; }
    .click-row {
      cursor: pointer;
      transition: background .16s ease;
    }
    .click-row:hover, .click-row:focus {
      background: rgba(143, 183, 255, .08);
      outline: none;
    }
    code, .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: .85rem;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 24px;
      padding: 2px 8px;
      border: 1px solid var(--line);
      color: var(--muted);
      background: rgba(8, 11, 15, .46);
      white-space: nowrap;
    }
    .pass { color: var(--accent-good); border-color: rgba(54, 211, 153, .34); }
    .warn { color: var(--accent-warn); border-color: rgba(245, 184, 91, .34); }
    .fail { color: var(--accent-bad); border-color: rgba(239, 107, 115, .34); }
    .muted { color: var(--muted); }
    .stack { display: grid; gap: 10px; }
    .item {
      padding: 10px;
      border: 1px solid var(--line);
      background: rgba(19, 26, 34, .82);
    }
    .item p { margin-top: 3px; color: var(--muted); }
    aside { position: sticky; top: 16px; }
    .inspector-body {
      display: grid;
      gap: 10px;
    }
    .action-drawer {
      display: grid;
      gap: 10px;
      padding: 10px;
      border: 1px solid var(--line);
      background: rgba(8, 11, 15, .56);
    }
    .action-drawer p {
      margin-top: 4px;
      overflow-wrap: anywhere;
    }
    .raw-json {
      max-height: 420px;
      overflow: auto;
      margin: 0;
      padding: 10px;
      border: 1px solid var(--line);
      background: #080b0f;
      color: var(--text);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .command {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-top: 8px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      background: #080b0f;
      color: var(--text);
      overflow-x: auto;
    }
    .command code {
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .api-copy {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .bottom-ops-console {
      margin-top: 14px;
    }
    .hidden-by-filter {
      display: none !important;
    }
    .footer {
      margin-top: 20px;
      color: var(--muted-2);
      font-size: .82rem;
    }
    @media (max-width: 920px) {
      header, main, .control-plane { grid-template-columns: 1fr; }
      .controls { grid-template-columns: 1fr; }
      aside { position: static; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .command-rail, .telemetry-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 560px) {
      .shell { width: min(100% - 20px, 1380px); padding-top: 14px; }
      .metrics, .command-rail, .telemetry-strip { grid-template-columns: 1fr; }
      th:nth-child(3), td:nth-child(3) { display: none; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: .01ms !important;
      }
    }
"""


def client_script() -> str:
    return r"""
const dataEl = document.getElementById('mission-data');
const state = {
  data: JSON.parse(dataEl.textContent),
  activeTab: 'Command Center',
  inspectorPayload: JSON.parse(dataEl.textContent)['/api/status'],
  autoTimer: null
};

function switchTab(name) {
  state.activeTab = name;
  document.querySelectorAll('[data-tab]').forEach((button) => {
    button.setAttribute('aria-selected', String(button.dataset.tab === name));
  });
  document.querySelectorAll('[data-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
  logEvent('tab', {name});
  applyFilter();
}

function setInspector(kind, payload) {
  state.inspectorPayload = payload;
  const action = actionPayload(payload);
  document.getElementById('inspector-kind').textContent = kind;
  document.getElementById('inspector-title').textContent =
    payload.id || payload.name || payload.label || payload.command || kind;
  document.getElementById('inspector-detail').textContent =
    payload.summary || action.detail || action.claim || action.status || 'Raw payload';
  document.getElementById('inspector-evidence').textContent = formatEvidence(action, payload.source || {});
  document.getElementById('inspector-health-impact').textContent =
    action.health_impact || 'No current health impact recorded.';
  document.getElementById('inspector-next-action').textContent =
    action.next_action || 'No next action recorded.';
  renderRelatedCommands(action.related_commands || []);
  document.getElementById('inspector-json').textContent =
    JSON.stringify(payload, null, 2);
}

function actionPayload(payload) {
  if (payload && payload.payload && typeof payload.payload === 'object' && !Array.isArray(payload.payload)) {
    return payload.payload;
  }
  return payload && typeof payload === 'object' ? payload : {};
}

function formatEvidence(payload, source) {
  const evidence = payload.evidence;
  if (Array.isArray(evidence) && evidence.length) {
    return evidence.slice(0, 3).map((item) => {
      if (typeof item === 'string') return item;
      return JSON.stringify(item);
    }).join(' | ');
  }
  if (payload.source_path) return payload.source_path;
  if (source.path) return source.path;
  if (source.command) return source.command;
  return 'No explicit evidence recorded.';
}

function renderRelatedCommands(commands) {
  const target = document.getElementById('inspector-related-commands');
  target.innerHTML = '';
  if (!commands.length) {
    const empty = document.createElement('p');
    empty.className = 'muted';
    empty.textContent = 'No related commands.';
    target.appendChild(empty);
    return;
  }
  commands.forEach((command) => {
    const row = document.createElement('div');
    row.className = 'command';
    const code = document.createElement('code');
    code.textContent = command;
    const button = document.createElement('button');
    button.className = 'copy-btn';
    button.type = 'button';
    button.dataset.copyKind = 'command';
    button.dataset.copyText = command;
    button.textContent = 'Copy';
    row.append(code, button);
    target.appendChild(row);
  });
}

function activeFilterTargets() {
  const panel = document.querySelector(`[data-panel="${state.activeTab}"]`);
  return panel ? panel.querySelectorAll('[data-search]') : [];
}

function applyFilter() {
  const input = document.getElementById('mission-search');
  const query = input.value.trim().toLowerCase();
  document.querySelectorAll('[data-search]').forEach((node) => {
    node.classList.remove('hidden-by-filter');
  });
  if (!query) return;
  activeFilterTargets().forEach((node) => {
    const haystack = (node.dataset.search || node.textContent || '').toLowerCase();
    node.classList.toggle('hidden-by-filter', !haystack.includes(query));
  });
}

function renderOpsEvent(event) {
  const time = new Date(event.time).toLocaleTimeString();
  return `${time} ${event.type}: ${JSON.stringify(event.payload)}`;
}

function logEvent(type, payload = {}) {
  const event = {time: new Date().toISOString(), type, payload};
  document.querySelectorAll('[data-ops-log]').forEach((log) => {
    const node = document.createElement('div');
    node.className = 'ops-event';
    node.textContent = renderOpsEvent(event);
    log.prepend(node);
    while (log.children.length > 24) {
      log.removeChild(log.lastElementChild);
    }
  });
  persistOpsEvent(event);
}

async function persistOpsEvent(event) {
  try {
    const response = await fetch('/api/ops/events', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify(event)
    });
    if (!response.ok) throw new Error(`ops event ${response.status}`);
  } catch (err) {
    const status = document.getElementById('refresh-status');
    if (status) status.textContent = `ops persist failed: ${err.message}`;
  }
}

async function refreshData() {
  const status = document.getElementById('refresh-status');
  status.textContent = 'refreshing';
  const paths = [
    '/api/status',
    '/api/adapters',
    '/api/doctor',
    '/api/memory/summary',
    '/api/handoff',
    '/api/command-center',
    '/api/command-recipes',
    '/api/brain',
    '/api/brain/lessons',
    '/api/brain/candidates',
    '/api/harnesses',
    '/api/harnesses/codex',
    '/api/trust',
    '/api/trust/verify',
    '/api/runs',
    '/api/skills',
    '/api/skills/example',
    '/api/protocols',
    '/api/protocols/permissions',
    '/api/data-flywheel',
    '/api/ops/events',
    '/api/settings'
  ];
  try {
    const pairs = await Promise.all(paths.map(async (path) => {
      const response = await fetch(path, {cache: 'no-store'});
      if (!response.ok) throw new Error(`${path} ${response.status}`);
      return [path, await response.json()];
    }));
    state.data = Object.fromEntries(pairs);
    dataEl.textContent = JSON.stringify(state.data);
    const latest = state.data['/api/status'];
    document.querySelector('.score strong').textContent = `${latest.score}%`;
    status.textContent = `updated ${new Date().toLocaleTimeString()}`;
    setInspector('status', latest);
    logEvent('refresh', {paths: paths.length, score: latest.score});
  } catch (err) {
    status.textContent = `refresh failed: ${err.message}`;
    logEvent('refresh_error', {message: err.message});
  }
}

async function copyText(value, button) {
  try {
    await navigator.clipboard.writeText(value);
  } catch (err) {
    const area = document.createElement('textarea');
    area.value = value;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }
  const old = button.textContent;
  button.textContent = 'Copied';
  setTimeout(() => { button.textContent = old; }, 1100);
}

document.querySelectorAll('[data-tab]').forEach((button) => {
  button.addEventListener('click', () => switchTab(button.dataset.tab));
});

document.addEventListener('click', (event) => {
  const copy = event.target.closest('[data-copy-kind], [data-copy-api], #copy-inspector');
  const row = event.target.closest('[data-inspect]');
  if (row && !copy) {
    const payload = JSON.parse(row.dataset.inspect);
    setInspector(row.dataset.inspectKind || 'item', payload);
    logEvent('inspector', {kind: row.dataset.inspectKind || 'item', id: payload.id || payload.label || payload.name});
  }
  if (!copy) return;
  if (copy.id === 'copy-inspector') {
    copyText(JSON.stringify(state.inspectorPayload, null, 2), copy);
    logEvent('copy', {kind: 'inspector'});
  } else if (copy.dataset.copyApi) {
    copyText(JSON.stringify(state.data[copy.dataset.copyApi] || {}, null, 2), copy);
    logEvent('copy', {kind: 'api', path: copy.dataset.copyApi});
  } else {
    copyText(copy.dataset.copyText || '', copy);
    logEvent('copy', {kind: copy.dataset.copyKind || 'text', command: copy.dataset.copyText || ''});
  }
});

document.addEventListener('keydown', (event) => {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-inspect]')) {
    event.preventDefault();
    const payload = JSON.parse(event.target.dataset.inspect);
    setInspector(event.target.dataset.inspectKind || 'item', payload);
    logEvent('inspector', {kind: event.target.dataset.inspectKind || 'item', id: payload.id || payload.label || payload.name});
  }
});

document.getElementById('mission-search').addEventListener('input', applyFilter);
document.getElementById('refresh-now').addEventListener('click', refreshData);
document.getElementById('auto-refresh').addEventListener('change', (event) => {
  if (state.autoTimer) {
    clearInterval(state.autoTimer);
    state.autoTimer = null;
  }
  if (event.target.checked) {
    refreshData();
    state.autoTimer = setInterval(refreshData, 15000);
  }
});
logEvent('ready', {project: state.data['/api/status'].project});
"""
