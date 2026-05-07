"""HTML rendering for the local Mission Control web UI."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .mission_control_collectors import API_PATHS, DOMAINS, build_payloads
from .mission_control_static import client_script, styles


def render_page(target_root: Path | str, stack_root: Path | str) -> str:
    payloads = build_payloads(target_root, stack_root)
    status = payloads["/api/status"]
    adapters = payloads["/api/adapters"]
    doctor = payloads["/api/doctor"]
    memory = payloads["/api/memory/summary"]
    handoff = payloads["/api/handoff"]
    embedded = _json_for_script(payloads)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agentic Stack Mission Control</title>
  <style>{styles()}</style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <p class="eyebrow">local control plane</p>
        <h1>Agentic Stack Mission Control</h1>
        <p class="project">{_esc(status["project"])}</p>
      </div>
      <div class="score" aria-label="health score">
        <span class="label">health</span>
        <strong>{status["score"]}%</strong>
      </div>
    </header>

    <div class="control-plane">
      <nav class="command-rail" aria-label="Control Plane domains" role="tablist">
        {_domain_rail()}
      </nav>
      <div class="telemetry-strip">
        <div class="telemetry"><span class="label">brain</span><strong>{_esc(memory["accepted"])} lessons</strong></div>
        <div class="telemetry"><span class="label">harnesses</span><strong>{_esc(status["installed_adapters"])} installed</strong></div>
        <div class="telemetry"><span class="label">trust</span><strong>{_esc(doctor["failures"])} fail / {_esc(doctor["warnings"])} warn</strong></div>
        <div class="telemetry"><span class="label">runs</span><strong>{_esc(memory["instances"]["count"])} tracked</strong></div>
      </div>
    </div>

    <nav class="mission-tabs" aria-label="Mission Control sections" role="tablist">
      {_tab_button("Overview")}
      {_tab_button("Memory")}
      {_tab_button("Adapters")}
      {_tab_button("Trust")}
      {_tab_button("Handoff")}
    </nav>

    <div class="controls" aria-label="Mission Control controls">
      <input id="mission-search" class="search" type="search" placeholder="Filter visible rows and commands" autocomplete="off">
      <button id="refresh-now" class="action-button" type="button">Refresh</button>
      <label class="toggle"><input id="auto-refresh" type="checkbox"> Auto-refresh</label>
      <span id="refresh-status" class="muted mono" aria-live="polite">idle</span>
    </div>

    <main>
      <div>
        {_domain_panels(payloads)}

        <section id="overview" class="mission-panel" data-panel="Overview" role="tabpanel" hidden>
          <div class="section-head">
            <h2>Overview</h2>
            <span class="pill pass">agentic-stack v{_esc(status["version"])}</span>
          </div>
          <div class="section-body">
            <div class="metrics">
              {_metric("Warnings", status["warnings"])}
              {_metric("Failures", status["failures"])}
              {_metric("Adapters", status["installed_adapters"])}
              {_metric("Lessons", status["lessons"])}
            </div>
          </div>
        </section>

        <section id="memory" class="mission-panel" data-panel="Memory" role="tabpanel" hidden>
          <div class="section-head">
            <h2>Memory</h2>
            <span class="pill">{memory["episodes"]} episodes</span>
          </div>
          <div class="section-body">
            <table>
              <thead><tr><th>Type</th><th>Count</th><th>Detail</th></tr></thead>
              <tbody>
                <tr><td>Accepted lessons</td><td>{memory["accepted"]}</td><td>{memory["provisional"]} provisional</td></tr>
                <tr><td>Candidates</td><td>{memory["candidates"]}</td><td>{_candidate_detail(memory["candidate_counts"])}</td></tr>
                <tr><td>Skills</td><td>{memory["skills"]["count"]}</td><td>{_esc(", ".join(memory["skills"]["names"][:5]) or "none")}</td></tr>
                <tr><td>Instances</td><td>{memory["instances"]["count"]}</td><td>active: {_esc(memory["instances"].get("active_instance") or "none")}</td></tr>
              </tbody>
            </table>
            {_memory_table(memory)}
          </div>
        </section>

        <section id="adapters" class="mission-panel" data-panel="Adapters" role="tabpanel" hidden>
          <div class="section-head">
            <h2>Adapters</h2>
            <span class="pill">{len(adapters["available"])} available</span>
          </div>
          <div class="section-body">
            {_adapter_table(adapters["rows"])}
          </div>
        </section>

        <section id="trust" class="mission-panel" data-panel="Trust" role="tabpanel" hidden>
          <div class="section-head">
            <h2>Trust</h2>
            <span class="pill {_status_class(doctor["failures"], doctor["warnings"])}">{doctor["failures"]} fail / {doctor["warnings"]} warn</span>
          </div>
          <div class="section-body">
            {_check_table(doctor["checks"])}
          </div>
        </section>

        <section id="handoff-panel" class="mission-panel" data-panel="Handoff" role="tabpanel" hidden>
          <div class="section-head">
            <h2>Handoff</h2>
            <span class="pill {'pass' if handoff["ready"] else 'warn'}">{_esc(handoff["detail"])}</span>
          </div>
          <div class="section-body stack">
            <div class="item" data-search="brain {_esc(status["brain_summary"])}">
              <strong>Brain</strong>
              <p>{_esc(status["brain_summary"])}</p>
            </div>
            <div class="item">
              <strong>Next operator brief</strong>
              <p>Run the commands below before handing work to another agent.</p>
              {_command_list(handoff["commands"])}
            </div>
            <div class="item">
              <strong>Local API</strong>
              <p class="muted">Copy live payloads for another tool or agent.</p>
              {_api_copy_list(API_PATHS)}
            </div>
          </div>
        </section>
      </div>

      <aside id="inspector" aria-live="polite">
        <div class="section-head">
          <h2>Inspector</h2>
          <span id="inspector-kind" class="pill">ready</span>
        </div>
        <div class="section-body inspector-body">
          <p id="inspector-title">Select a row, command, or API payload.</p>
          <p id="inspector-detail" class="muted">Details and raw JSON stay local in this browser.</p>
          <div id="action-drawer" class="action-drawer" aria-label="Selected object action details">
            <div>
              <span class="label">evidence</span>
              <p id="inspector-evidence" class="muted">Select an object to see local evidence.</p>
            </div>
            <div>
              <span class="label">health impact</span>
              <p id="inspector-health-impact" class="muted">No object selected.</p>
            </div>
            <div>
              <span class="label">next action</span>
              <p id="inspector-next-action" class="muted">Select an object to see the next step.</p>
            </div>
            <div>
              <span class="label">related commands</span>
              <div id="inspector-related-commands" class="stack"></div>
            </div>
          </div>
          <button id="copy-inspector" class="copy-btn" type="button">Copy JSON</button>
          <pre id="inspector-json" class="raw-json">{_esc(json.dumps(payloads["/api/status"], indent=2, sort_keys=True))}</pre>
        </div>
      </aside>
    </main>

    <section id="bottom-ops-console" class="bottom-ops-console" aria-live="polite">
      <div class="section-head">
        <h2>Ops Console</h2>
        <span class="pill">persistent local log</span>
      </div>
      <div class="section-body">
        <div id="bottom-ops-log" class="ops-log" data-ops-log></div>
      </div>
    </section>

    <p class="footer">Served locally by <span class="mono">agentic-stack mission-control</span>. No cloud service is required.</p>
  </div>
  <script id="mission-data" type="application/json">{embedded}</script>
  <script>{client_script()}</script>
</body>
</html>
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _json_for_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=True).replace("</", "<\\/")


def _json_attr(value: object) -> str:
    return _esc(json.dumps(value, ensure_ascii=True, sort_keys=True))


def _tab_button(name: str, selected: bool = False) -> str:
    selected_attr = "true" if selected else "false"
    return (
        f'<button class="tab-button" type="button" role="tab" '
        f'aria-selected="{selected_attr}" data-tab="{_esc(name)}">{_esc(name)}</button>'
    )


def _domain_rail() -> str:
    buttons: list[str] = []
    for domain in DOMAINS:
        selected = "true" if domain == "Command Center" else "false"
        buttons.append(
            f'<button class="rail-button" type="button" role="tab" aria-selected="{selected}" '
            f'data-domain="{_esc(domain)}" data-tab="{_esc(domain)}">{_esc(domain)}</button>'
        )
    return "".join(buttons)


def _domain_panels(payloads: dict[str, dict[str, Any]]) -> str:
    primary_paths = [
        ("/api/command-center", "Command Center"),
        ("/api/command-recipes", "Command Recipes"),
        ("/api/brain", "Brain"),
        ("/api/harnesses", "Harnesses"),
        ("/api/trust", "Trust"),
        ("/api/runs", "Runs"),
        ("/api/skills", "Skills"),
        ("/api/protocols", "Protocols"),
        ("/api/handoff", "Handoff"),
        ("/api/data-flywheel", "Data Flywheel"),
        ("/api/ops/events", "Ops Console"),
        ("/api/settings", "Settings"),
    ]
    panels: list[str] = []
    for path, domain in primary_paths:
        payload = payloads[path]
        summary = payload.get("domain_summary", payload.get("summary", ""))
        panel_id = ' id="ops-console"' if domain == "Ops Console" else ""
        hidden = "" if domain == "Command Center" else " hidden"
        panels.append(
            f'<section{panel_id} class="mission-panel domain-panel" data-panel="{_esc(domain)}" '
            f'role="tabpanel"{hidden}>'
            '<div class="section-head">'
            f"<h2>{_esc(domain)}</h2>"
            f'<button class="copy-btn" type="button" data-copy-api="{_esc(path)}">Copy JSON</button>'
            "</div>"
            '<div class="section-body">'
            f'<p class="domain-summary">{_esc(summary)}</p>'
            f"{_domain_object_table(payload.get('objects', []))}"
            f"{'<div id=\"ops-log\" class=\"ops-log\" data-ops-log></div>' if domain == 'Ops Console' else ''}"
            "</div>"
            "</section>"
        )
    return "".join(panels)


def _domain_object_table(objects: list[dict[str, Any]]) -> str:
    if not objects:
        return '<p class="muted">No objects for this domain.</p>'
    rows = ['<table><thead><tr><th>Kind</th><th>Status</th><th>Summary</th><th>Action</th></tr></thead><tbody>']
    for item in objects:
        status = str(item.get("status", "warn"))
        kind = str(item.get("kind", "item"))
        label = str(item.get("label", "item"))
        summary = str(item.get("summary", ""))
        payload = item.get("payload", {})
        command = payload.get("command") if isinstance(payload, dict) else None
        action = (
            f'<button class="copy-btn" type="button" data-copy-kind="command" '
            f'data-copy-text="{_esc(command)}">Copy</button>'
            if command else ""
        )
        search = f"{kind} {label} {status} {summary}"
        rows.append(
            f'<tr class="click-row" tabindex="0" data-search="{_esc(search)}" '
            f'data-inspect-kind="{_esc(kind)}" data-inspect="{_json_attr(item)}">'
            f"<td><strong>{_esc(label)}</strong><br><span class=\"muted\">{_esc(kind)}</span></td>"
            f'<td><span class="pill {status}">{_esc(status)}</span></td>'
            f"<td>{_esc(summary)}</td>"
            f"<td>{action}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "".join(rows)


def _metric(label: str, value: object) -> str:
    return f'<div class="metric"><span class="label">{_esc(label)}</span><strong>{_esc(value)}</strong></div>'


def _status_class(failures: int, warnings: int) -> str:
    if failures:
        return "fail"
    if warnings:
        return "warn"
    return "pass"


def _candidate_detail(counts: dict[str, Any]) -> str:
    return (
        f"{_esc(counts.get('staged', 0))} staged, "
        f"{_esc(counts.get('graduated', 0))} graduated, "
        f"{_esc(counts.get('rejected', 0))} rejected"
    )


def _memory_table(memory: dict[str, Any]) -> str:
    rows: list[str] = [
        '<table><thead><tr><th>Kind</th><th>ID</th><th>Claim</th></tr></thead><tbody>'
    ]
    items = [
        ("accepted", item)
        for item in memory.get("accepted_items", [])
        if isinstance(item, dict)
    ] + [
        ("rejected", item)
        for item in memory.get("rejected_items", [])
        if isinstance(item, dict)
    ]
    if not items:
        return '<p class="muted">No memory items to inspect.</p>'
    for kind, item in items:
        claim = item.get("claim", "")
        identifier = item.get("id", "?")
        search = f"{kind} {identifier} {claim}"
        rows.append(
            f'<tr class="click-row" tabindex="0" data-search="{_esc(search)}" '
            f'data-inspect-kind="memory" data-inspect="{_json_attr(item)}">'
            f"<td>{_esc(kind)}</td><td>{_esc(identifier)}</td><td>{_esc(claim)}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "".join(rows)


def _adapter_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="muted">No adapters installed.</p>'
    out = ['<table><thead><tr><th>Name</th><th>Status</th><th>Detail</th></tr></thead><tbody>']
    for row in rows:
        status = str(row.get("status", "warn"))
        search = f"{row.get('name', '')} {status} {row.get('detail', '')}"
        out.append(
            f'<tr class="click-row" tabindex="0" data-search="{_esc(search)}" '
            f'data-inspect-kind="adapter" data-inspect="{_json_attr(row)}">'
            f"<td>{_esc(row.get('name', '?'))}</td>"
            f'<td><span class="pill {status}">{_esc(status)}</span></td>'
            f"<td>{_esc(row.get('detail', ''))}</td>"
            "</tr>"
        )
    out.append("</tbody></table>")
    return "".join(out)


def _check_table(rows: list[dict[str, Any]]) -> str:
    out = ['<table><thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead><tbody>']
    for row in rows:
        status = str(row.get("status", "warn"))
        search = f"{row.get('label', '')} {status} {row.get('detail', '')}"
        out.append(
            f'<tr class="click-row" tabindex="0" data-search="{_esc(search)}" '
            f'data-inspect-kind="check" data-inspect="{_json_attr(row)}">'
            f"<td>{_esc(row.get('label', '?'))}</td>"
            f'<td><span class="pill {status}">{_esc(status)}</span></td>'
            f"<td>{_esc(row.get('detail', ''))}</td>"
            "</tr>"
        )
    out.append("</tbody></table>")
    return "".join(out)


def _command_list(commands: list[str]) -> str:
    rows: list[str] = []
    for command in commands:
        rows.append(
            f'<div class="command" data-search="{_esc(command)}" '
            f'data-inspect-kind="command" data-inspect="{_json_attr({"command": command})}">'
            f"<code>{_esc(command)}</code>"
            f'<button class="copy-btn" type="button" data-copy-kind="command" '
            f'data-copy-text="{_esc(command)}">Copy</button>'
            "</div>"
        )
    return "".join(rows)


def _api_copy_list(paths: set[str]) -> str:
    buttons = []
    for path in sorted(paths):
        label = path.removeprefix("/api/") or path
        buttons.append(
            f'<button class="copy-btn" type="button" data-search="{_esc(path)}" '
            f'data-copy-api="{_esc(path)}">Copy {_esc(label)} JSON</button>'
        )
    return '<div class="api-copy">' + "".join(buttons) + "</div>"

