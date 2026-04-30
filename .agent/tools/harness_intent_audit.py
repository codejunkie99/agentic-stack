#!/usr/bin/env python3
"""Phase O: Behavioral intent audit for installed targets.

Codifies the 18-checkpoint audit from .agent/protocols/canonical-sources.md
as a runnable tool. Categories: install_state (5), engagement_behavior (8),
drift_detection (4), plus an anchor checkpoint (write the audit report).

Output: structured JSON + human-readable markdown to
<target>/.agent/memory/working/intent-audit-<YYYY-MM-DD>.{json,md}.

Exit codes: 0 all PASS; 1 any FAIL; 2 any WARN with no FAIL.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


def _check(category: str, name: str, status: str, detail: str = "", rationale: str = "") -> dict:
    return {
        "id": None,
        "category": category,
        "name": name,
        "status": status,
        "detail": detail,
        "rationale": rationale,
    }


# ============================================================================
# INSTALL STATE (5 checks)
# ============================================================================

def check_files_present(target: Path) -> dict:
    expected = [target / ".agent", target / ".claude/settings.json"]
    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        return _check("install_state", "files_present", "FAIL",
                      detail=f"missing: {missing}",
                      rationale="adapter declared files not at expected paths")
    return _check("install_state", "files_present", "PASS",
                  detail="declared adapter files present")


def check_install_json_present(target: Path) -> dict:
    path = target / ".agent/install.json"
    if path.exists():
        return _check("install_state", "install_json_present", "PASS",
                      detail=str(path.relative_to(target)))
    return _check("install_state", "install_json_present", "FAIL",
                  detail="missing: .agent/install.json",
                  rationale="install.json absent — install corrupted or pre-v0.9")


def check_skill_linter_passes(target: Path) -> dict:
    linter = target / ".agent/tools/skill_linter.py"
    if not linter.exists():
        return _check("install_state", "skill_linter", "SKIP",
                      rationale="skill_linter.py not present in target")
    import subprocess
    result = subprocess.run([sys.executable, str(linter)],
                            cwd=target, capture_output=True, text=True)
    if result.returncode == 0:
        last_line = result.stdout.strip().splitlines()[-1] if result.stdout else ""
        return _check("install_state", "skill_linter", "PASS", detail=last_line)
    return _check("install_state", "skill_linter", "FAIL",
                  detail=(result.stdout + result.stderr)[:200],
                  rationale="skill_linter.py exit nonzero")


def check_conformance_audit(target: Path) -> dict:
    audit = target / ".agent/tools/harness_conformance_audit.py"
    if not audit.exists():
        return _check("install_state", "conformance_audit", "SKIP",
                      rationale="harness_conformance_audit.py not in target")
    import subprocess
    result = subprocess.run([sys.executable, str(audit)],
                            cwd=target, capture_output=True, text=True)
    if result.returncode == 0:
        return _check("install_state", "conformance_audit", "PASS")
    return _check("install_state", "conformance_audit", "FAIL",
                  detail=(result.stdout + result.stderr)[:200],
                  rationale="conformance audit exit nonzero")


def check_smoke_install_succeeds(target: Path) -> dict:
    return _check("install_state", "smoke_install", "SKIP",
                  rationale="deferred — runs in CI, not on every audit invocation")


# ============================================================================
# ENGAGEMENT BEHAVIOR (8 checks)
# ============================================================================

def check_episodic_nonempty(target: Path) -> dict:
    p = target / ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"
    if not p.exists():
        return _check("engagement_behavior", "episodic_nonempty", "FAIL",
                      detail="missing AGENT_LEARNINGS.jsonl",
                      rationale="no episodic log at all")
    n = sum(1 for _ in p.open() if _.strip())
    if n > 0:
        return _check("engagement_behavior", "episodic_nonempty", "PASS",
                      detail=f"{n} entries")
    return _check("engagement_behavior", "episodic_nonempty", "WARN",
                  detail="empty AGENT_LEARNINGS.jsonl",
                  rationale="install present but no engagement events captured")


def check_workspace_recent(target: Path) -> dict:
    p = target / ".agent/memory/working/WORKSPACE.md"
    if not p.exists():
        return _check("engagement_behavior", "workspace_recent", "WARN",
                      detail="WORKSPACE.md missing")
    age_h = (dt.datetime.now() - dt.datetime.fromtimestamp(p.stat().st_mtime)).total_seconds() / 3600
    if age_h <= 168:
        return _check("engagement_behavior", "workspace_recent", "PASS",
                      detail=f"mtime {age_h:.1f}h ago")
    return _check("engagement_behavior", "workspace_recent", "WARN",
                  detail=f"mtime {age_h:.1f}h ago",
                  rationale="WORKSPACE.md not updated recently")


def check_per_agent_memory(target: Path) -> dict:
    am = target / ".claude/agent-memory"
    if not am.exists():
        return _check("engagement_behavior", "per_agent_memory", "SKIP",
                      rationale=".claude/agent-memory/ not present")
    populated = [d.name for d in am.iterdir() if d.is_dir() and any(d.iterdir())]
    if len(populated) >= 1:
        return _check("engagement_behavior", "per_agent_memory", "PASS",
                      detail=f"{len(populated)} agents have memory: {populated[:5]}")
    return _check("engagement_behavior", "per_agent_memory", "WARN",
                  detail="no per-agent memory written",
                  rationale="agents dispatched but no per-agent memory captured")


def check_phase_exit_reflections(target: Path) -> dict:
    p = target / ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"
    if not p.exists():
        return _check("engagement_behavior", "phase_exit_reflections", "SKIP")
    high_imp = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(e.get("importance") or 0) >= 8 and (e.get("reflection") or "").strip():
            high_imp += 1
    if high_imp >= 1:
        return _check("engagement_behavior", "phase_exit_reflections", "PASS",
                      detail=f"{high_imp} reflection events at importance >= 8")
    return _check("engagement_behavior", "phase_exit_reflections", "WARN",
                  detail="no high-importance reflections",
                  rationale="skills with phase exits should produce importance>=8 reflections")


def check_dream_cycle_ran(target: Path) -> dict:
    log = target / ".agent/memory/dream.log"
    if log.exists():
        return _check("engagement_behavior", "dream_cycle_ran", "PASS",
                      detail=f"dream.log size {log.stat().st_size}")
    cands = target / ".agent/memory/candidates"
    if cands.exists() and any(cands.iterdir()):
        return _check("engagement_behavior", "dream_cycle_ran", "PASS",
                      detail="candidates/ has staged entries")
    return _check("engagement_behavior", "dream_cycle_ran", "WARN",
                  rationale="no dream.log; no candidates/ contents")


def check_candidates_lesson_shaped(target: Path) -> dict:
    cands = target / ".agent/memory/candidates"
    if not cands.exists():
        return _check("engagement_behavior", "candidates_lesson_shaped", "SKIP")
    file_write_re = re.compile(r"^(Wrote|Edited|Created|Updated)\s+\S+\.\S+")
    bad = 0
    sampled = 0
    for f in sorted(cands.iterdir())[:5]:
        if not f.name.endswith(".json"):
            continue
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        sampled += 1
        if file_write_re.match(data.get("claim", "")):
            bad += 1
    if sampled == 0:
        return _check("engagement_behavior", "candidates_lesson_shaped", "SKIP",
                      rationale="no candidates to sample")
    if bad >= 3:
        return _check("engagement_behavior", "candidates_lesson_shaped", "FAIL",
                      detail=f"{bad}/{sampled} candidates are file-write-shaped",
                      rationale="dream cycle producing noise; check Gap 9 collapse filter")
    if bad >= 1:
        return _check("engagement_behavior", "candidates_lesson_shaped", "WARN",
                      detail=f"{bad}/{sampled} are file-write-shaped")
    return _check("engagement_behavior", "candidates_lesson_shaped", "PASS",
                  detail=f"{sampled} candidates sampled, all lesson-shaped")


def check_semantic_memory_grew(target: Path) -> dict:
    lessons = target / ".agent/memory/semantic/LESSONS.md"
    if not lessons.exists():
        return _check("engagement_behavior", "semantic_memory_grew", "WARN",
                      rationale="no LESSONS.md")
    if lessons.stat().st_size > 200:
        return _check("engagement_behavior", "semantic_memory_grew", "PASS",
                      detail=f"size {lessons.stat().st_size} bytes")
    return _check("engagement_behavior", "semantic_memory_grew", "WARN",
                  detail=f"LESSONS.md size {lessons.stat().st_size}",
                  rationale="LESSONS.md very small; no graduations yet")


def check_harness_feedback_nonempty_if_long(target: Path) -> dict:
    feedback = target / ".agent/memory/working/HARNESS_FEEDBACK.md"
    episodic = target / ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"
    if not episodic.exists():
        return _check("engagement_behavior", "harness_feedback_nonempty", "SKIP")
    tool_calls = sum(1 for _ in episodic.open() if _.strip())
    feedback_lines = sum(1 for _ in feedback.open()) if feedback.exists() else 0
    if tool_calls > 30 and feedback_lines <= 3:
        return _check("engagement_behavior", "harness_feedback_nonempty", "WARN",
                      detail=f"tool_calls={tool_calls}, feedback_lines={feedback_lines}",
                      rationale="long session with no captured friction (Gap 11 territory)")
    return _check("engagement_behavior", "harness_feedback_nonempty", "PASS",
                  detail=f"tool_calls={tool_calls}, feedback_lines={feedback_lines}")


# ============================================================================
# DRIFT DETECTION (4 checks — minimal v1; full trace_check integration deferred)
# ============================================================================

def check_workflow_contract_followed(target: Path) -> dict:
    tc = target / ".agent/tools/trace_check.py"
    if not tc.exists():
        return _check("drift_detection", "workflow_contract", "SKIP",
                      rationale="trace_check.py not in target")
    return _check("drift_detection", "workflow_contract", "SKIP",
                  rationale="full trace_check integration deferred to v2")


def check_skill_handoff_order(target: Path) -> dict:
    return _check("drift_detection", "skill_handoff_order", "SKIP",
                  rationale="v1: deferred to manual review")


def check_agent_output_paths_respected(target: Path) -> dict:
    return _check("drift_detection", "agent_output_paths", "SKIP",
                  rationale="v1: deferred to manual review")


def check_primitives_used_as_documented(target: Path) -> dict:
    settings = target / ".claude/settings.json"
    if not settings.exists():
        return _check("drift_detection", "primitives_used", "SKIP")
    try:
        cfg = json.loads(settings.read_text())
    except json.JSONDecodeError:
        return _check("drift_detection", "primitives_used", "FAIL",
                      detail="settings.json unparseable")
    return _check("drift_detection", "primitives_used", "PASS",
                  detail=f"settings.json valid JSON, {len(cfg)} top-level keys")


INSTALL_STATE_CHECKS = [
    check_files_present,
    check_install_json_present,
    check_skill_linter_passes,
    check_conformance_audit,
    check_smoke_install_succeeds,
]
ENGAGEMENT_BEHAVIOR_CHECKS = [
    check_episodic_nonempty,
    check_workspace_recent,
    check_per_agent_memory,
    check_phase_exit_reflections,
    check_dream_cycle_ran,
    check_candidates_lesson_shaped,
    check_semantic_memory_grew,
    check_harness_feedback_nonempty_if_long,
]
DRIFT_CHECKS = [
    check_workflow_contract_followed,
    check_skill_handoff_order,
    check_agent_output_paths_respected,
    check_primitives_used_as_documented,
]


def run_audit(target: Path, strict: bool = False) -> dict:
    checkpoints = []
    cid = 1
    for fn_group in (INSTALL_STATE_CHECKS, ENGAGEMENT_BEHAVIOR_CHECKS, DRIFT_CHECKS):
        for fn in fn_group:
            c = fn(target)
            c["id"] = cid
            if strict and c["status"] == "WARN":
                c["status"] = "FAIL"
                c["rationale"] = (c.get("rationale") or "") + " (strict: WARN→FAIL)"
            checkpoints.append(c)
            cid += 1

    summary = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for c in checkpoints:
        summary[c["status"].lower()] = summary.get(c["status"].lower(), 0) + 1

    return {
        "target": str(target),
        "audit_date": dt.date.today().isoformat(),
        "checkpoints": checkpoints,
        "summary": summary,
    }


def render_md(report: dict) -> str:
    lines = [
        f"# Intent Audit — {report['target']}",
        f"**Date:** {report['audit_date']}",
        f"**Summary:** PASS={report['summary'].get('pass',0)} "
        f"FAIL={report['summary'].get('fail',0)} "
        f"WARN={report['summary'].get('warn',0)} "
        f"SKIP={report['summary'].get('skip',0)}",
        "",
    ]
    last_category = None
    for c in report["checkpoints"]:
        if c["category"] != last_category:
            lines.append(f"\n## {c['category']}")
            last_category = c["category"]
        status_icon = {"PASS":"✓","FAIL":"✗","WARN":"⚠","SKIP":"–"}.get(c["status"], "?")
        line = f"- {status_icon} **{c['name']}** ({c['status']})"
        if c.get("detail"):
            line += f" — {c['detail']}"
        if c.get("rationale") and c["status"] != "PASS":
            line += f"\n  - rationale: {c['rationale']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Behavioral intent audit for an installed target.")
    p.add_argument("target_path")
    p.add_argument("--json", action="store_true")
    p.add_argument("--md", action="store_true")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    target = Path(args.target_path).resolve()
    if not target.exists():
        print(f"error: target not found: {target}", file=sys.stderr)
        return 2

    report = run_audit(target, strict=args.strict)

    out_dir = target / ".agent/memory/working"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"intent-audit-{report['audit_date']}.json"
    md_path = out_dir / f"intent-audit-{report['audit_date']}.md"

    if args.json or (not args.json and not args.md):
        print(json.dumps(report, indent=2))
    if args.md:
        print(render_md(report))

    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(render_md(report))

    # Anchor checkpoint #18 — audit report written
    report["checkpoints"].append({
        "id": len(report["checkpoints"]) + 1,
        "category": "anchor",
        "name": "audit_report_written",
        "status": "PASS",
        "detail": f"wrote {json_path.name} and {md_path.name}",
        "rationale": "",
    })
    report["summary"]["pass"] = report["summary"].get("pass", 0) + 1
    json_path.write_text(json.dumps(report, indent=2))

    if report["summary"].get("fail", 0) > 0:
        return 1
    if report["summary"].get("warn", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
