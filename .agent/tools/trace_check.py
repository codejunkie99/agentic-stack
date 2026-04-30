#!/usr/bin/env python3
"""Deterministic trace verifier — did the expected events fire?

Reads `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`, applies a set
of expected-event matchers per (skill, phase) combination, and
prints a checklist of ✓ / ✗ / ⋯ per expectation. Designed to answer:
"did the harness do what I told it to do?" without needing to read
raw JSON logs.

Lightweight by design — stdlib only, one file, no daemon. Run after
a session (or with --watch during) to see what fired.

Usage:

    # After session — show what fired in last hour
    python3 .agent/tools/trace_check.py \\
        --skill consulting-deck-builder --phase 2

    # Tighter window
    python3 .agent/tools/trace_check.py \\
        --skill consulting-deck-builder --phase 2 --since 15m

    # Phase 1 iteration check
    python3 .agent/tools/trace_check.py \\
        --skill consulting-deck-builder --phase 1-iteration

    # Watch mode (poll every 3s)
    python3 .agent/tools/trace_check.py \\
        --skill consulting-deck-builder --phase 2 --watch

The expectation set per (skill, phase) is currently embedded in this
file (CHECKS dict). Move to per-skill YAML when more skills add
expectations — for v1, keeping it inline keeps the tool stdlib-only
and self-contained.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
EPISODIC = AGENT_ROOT / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
INSTALL_ROOT = AGENT_ROOT.parent

# Status tokens
PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
PEND = "\033[33m⋯\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _no_color():
    """Disable color codes when not on a TTY."""
    global PASS, FAIL, PEND, BOLD, DIM, RESET
    PASS, FAIL, PEND = "✓", "✗", "⋯"
    BOLD = DIM = RESET = ""


# ---- Expectations ---------------------------------------------------

def _expectations(skill: str, phase: str) -> list[dict]:
    """Return the expectation set for a (skill, phase) pair.

    Each expectation has: id, label, severity (critical|warning|info),
    matcher (callable that takes (entries, install_root) and returns
    (bool_pass, evidence_str_or_none)).
    """
    if skill == "consulting-deck-builder" and phase == "1":
        return _exp_deck_builder_phase_1_cold()
    if skill == "consulting-deck-builder" and phase == "1-iteration":
        return _exp_deck_builder_phase_1_iteration()
    if skill == "consulting-deck-builder" and phase == "2":
        return _exp_deck_builder_phase_2()
    return []


def _exp_deck_builder_phase_1_cold() -> list[dict]:
    return [
        {
            "id": "skill_loaded",
            "label": "consulting-deck-builder skill loaded",
            "severity": "critical",
            "matcher": _match_read_of("skills/consulting-deck-builder/SKILL.md"),
        },
        {
            "id": "briefing_read",
            "label": "engagement briefing.md read",
            "severity": "critical",
            "matcher": _match_read_of("briefing.md"),
        },
        {
            "id": "index_read",
            "label": "engagement INDEX.md read",
            "severity": "critical",
            "matcher": _match_read_of("INDEX.md"),
        },
        {
            "id": "summaries_consulted",
            "label": "summaries/ files consulted (lazy-load discipline)",
            "severity": "warning",
            "matcher": _match_path_count("summaries/", min_count=1),
        },
        {
            "id": "no_raw_uploads",
            "label": "raw-uploads/ NOT bulk-read (lazy-load discipline)",
            "severity": "critical",
            "matcher": _match_path_count("raw-uploads/", max_count=0),
        },
        {
            "id": "storyboard_written",
            "label": "output/storyboard.md exists",
            "severity": "critical",
            "matcher": _match_file_exists("output/storyboard.md"),
        },
    ]


def _exp_deck_builder_phase_1_iteration() -> list[dict]:
    return [
        {
            "id": "skill_loaded",
            "label": "consulting-deck-builder skill loaded",
            "severity": "critical",
            "matcher": _match_read_of("skills/consulting-deck-builder/SKILL.md"),
        },
        {
            "id": "existing_storyboard_read",
            "label": "existing output/storyboard.md read (iteration mode)",
            "severity": "critical",
            "matcher": _match_read_of("output/storyboard.md"),
        },
        {
            "id": "workflow_loaded",
            "label": "matching workflow file looked up",
            "severity": "critical",
            "matcher": _match_read_of("workflows/", suffix=".md"),
        },
        {
            "id": "deck_builder_dispatched",
            "label": "deck-builder dispatched (action-voice + MECE audit)",
            "severity": "critical",
            "matcher": _match_agent_dispatch("deck-builder"),
        },
        {
            "id": "case_analysts_parallel",
            "label": "case-analyst (×N) dispatched in parallel",
            "severity": "warning",
            "matcher": _match_parallel_dispatch("case-analyst", min_count=2, window_s=120),
        },
        {
            "id": "delivery_lead_dispatched",
            "label": "delivery-lead dispatched (if workflow has MVP/TOM)",
            "severity": "info",
            "matcher": _match_agent_dispatch("delivery-lead"),
        },
        {
            "id": "audit_findings_surfaced",
            "label": "audit findings synthesised + surfaced to user",
            "severity": "warning",
            "matcher": _match_assistant_text(["audit findings", "audit results", "structural findings", "MECE check", "action-voice audit"]),
        },
    ]


def _exp_deck_builder_phase_2() -> list[dict]:
    return [
        {
            "id": "skill_loaded",
            "label": "consulting-deck-builder skill loaded",
            "severity": "critical",
            "matcher": _match_read_of("skills/consulting-deck-builder/SKILL.md"),
        },
        {
            "id": "workflow_loaded",
            "label": "matching workflow looked up",
            "severity": "critical",
            "matcher": _match_read_of("workflows/", suffix=".md"),
        },
        {
            "id": "dispatch_plan_presented",
            "label": "dispatch plan presented BEFORE first Agent dispatch",
            "severity": "critical",
            "matcher": _match_dispatch_plan_before_agents,
        },
        {
            "id": "framework_lead_dispatched",
            "label": "framework-lead orchestrator dispatched",
            "severity": "critical",
            "matcher": _match_agent_dispatch("framework-lead"),
        },
        {
            "id": "case_analysts_parallel",
            "label": "case-analyst (×N≥4) dispatched in parallel within 60s",
            "severity": "critical",
            "matcher": _match_parallel_dispatch("case-analyst", min_count=4, window_s=60),
        },
        {
            "id": "deck_builder_dispatched",
            "label": "deck-builder dispatched",
            "severity": "warning",
            "matcher": _match_agent_dispatch("deck-builder"),
        },
        {
            "id": "delivery_lead_dispatched",
            "label": "delivery-lead dispatched (proposal-deck workflows)",
            "severity": "warning",
            "matcher": _match_agent_dispatch("delivery-lead"),
        },
        {
            "id": "lead_did_not_draft",
            "label": "lead did NOT draft slide content in main session",
            "severity": "critical",
            "matcher": _match_no_main_session_drafts,
        },
        {
            "id": "reviewers_parallel",
            "label": "3 reviewers dispatched in parallel after workers",
            "severity": "warning",
            "matcher": _match_reviewer_panel_after_workers,
        },
        {
            "id": "content_draft_written",
            "label": "output/content-draft.md exists",
            "severity": "critical",
            "matcher": _match_file_exists("output/content-draft.md"),
        },
    ]


# ---- Matchers --------------------------------------------------------

def _match_read_of(path_substring: str, suffix: str | None = None):
    """Episodic schema: action='read: <full_path>'."""
    def fn(entries, install_root):
        for e in entries:
            action = e.get("action", "")
            if not action.startswith("read: "):
                continue
            fp = action[len("read: "):]
            if path_substring in fp and (suffix is None or fp.endswith(suffix)):
                return True, f"Read {Path(fp).name} at {e.get('timestamp', 'unknown')}"
        return False, None
    return fn


def _match_path_count(path_substring: str, min_count: int = 0, max_count: int | None = None):
    def fn(entries, install_root):
        count = 0
        examples = []
        for e in entries:
            action = e.get("action", "")
            if not action.startswith("read: "):
                continue
            fp = action[len("read: "):]
            if path_substring in fp:
                count += 1
                if len(examples) < 3:
                    examples.append(Path(fp).name)
        if max_count is not None and count > max_count:
            return False, f"{count} read(s) — exceeds max ({max_count}). Examples: {', '.join(examples)}"
        if count < min_count:
            return False, f"only {count} read(s) — below min ({min_count})"
        return True, f"{count} read(s){' — ' + ', '.join(examples) if examples else ''}"
    return fn


def _match_file_exists(rel_path: str):
    def fn(entries, install_root):
        p = install_root / rel_path
        if p.is_file():
            return True, f"file exists ({p.stat().st_size} bytes)"
        return False, f"file not found at {rel_path}"
    return fn


def _match_agent_dispatch(subagent_name: str):
    """Episodic schema: action='agent: <subagent_name> — <description>'."""
    prefix = f"agent: {subagent_name}"
    def fn(entries, install_root):
        for e in entries:
            action = e.get("action", "")
            if action.startswith(prefix):
                return True, f"dispatched at {e.get('timestamp', 'unknown')}"
        return False, f"{subagent_name} never dispatched via Agent tool"
    return fn


def _match_parallel_dispatch(subagent_name: str, min_count: int = 2, window_s: int = 60):
    prefix = f"agent: {subagent_name}"
    def fn(entries, install_root):
        timestamps = []
        for e in entries:
            action = e.get("action", "")
            if not action.startswith(prefix):
                continue
            ts = e.get("timestamp")
            if ts:
                try:
                    timestamps.append(dt.datetime.fromisoformat(ts.rstrip("Z")).replace(tzinfo=None))
                except ValueError:
                    pass
        if len(timestamps) < min_count:
            return False, f"only {len(timestamps)} dispatch(es) — below min ({min_count})"
        timestamps.sort()
        for i in range(len(timestamps) - min_count + 1):
            if (timestamps[i + min_count - 1] - timestamps[i]).total_seconds() <= window_s:
                return True, f"{min_count}+ {subagent_name}(s) within {window_s}s window"
        spread = (timestamps[-1] - timestamps[0]).total_seconds()
        return False, f"{len(timestamps)} dispatches but spread over {spread:.0f}s (window: {window_s}s)"
    return fn


def _match_assistant_text(keywords: list[str]):
    """Search across action / detail / reflection fields for any keyword."""
    def fn(entries, install_root):
        for e in entries:
            text = " ".join(str(e.get(f, "")) for f in ("action", "detail", "reflection"))
            text_lower = text.lower()
            for kw in keywords:
                if kw.lower() in text_lower:
                    return True, f"matched '{kw}'"
        return False, f"no entry contained any of: {keywords}"
    return fn


def _match_dispatch_plan_before_agents(entries, install_root):
    """Dispatch plan must appear in some signal BEFORE first Agent call.
    Episodic schema: action='agent: <name> — <desc>'."""
    first_agent_ts = None
    for e in entries:
        action = e.get("action", "")
        if action.startswith("agent: ") or action.startswith("task: "):
            t = _parse_ts(e.get("timestamp"))
            if t is not None:
                first_agent_ts = t
                break
    if first_agent_ts is None:
        return False, "no Agent dispatch yet — cannot evaluate ordering"
    keywords = ["dispatch plan", "i'll dispatch", "i will dispatch", "plan for dispatch", "dispatch the team"]
    for e in entries:
        t = _parse_ts(e.get("timestamp"))
        if t is None:
            continue
        if t >= first_agent_ts:
            break
        text = " ".join(str(e.get(f, "")) for f in ("action", "detail", "reflection")).lower()
        for kw in keywords:
            if kw in text:
                return True, f"plan signaled before first dispatch (matched '{kw}')"
    return False, "no 'dispatch plan' signal in entries before first Agent call"


def _match_no_main_session_drafts(entries, install_root):
    """Lead should NOT have written slide content directly.
    Episodic schema: action='write: <path>' or 'edit: <path>'."""
    direct_writes = 0
    for e in entries:
        action = e.get("action", "")
        for prefix in ("write: ", "edit: "):
            if action.startswith(prefix):
                fp = action[len(prefix):]
                if "content-draft" in fp and "act-" not in fp:
                    direct_writes += 1
                break
    if direct_writes == 0:
        return True, "no main-session writes to content-draft.md (good)"
    return True, f"{direct_writes} write(s) to content-draft.md — verify these came from deck-builder, not lead"


def _match_reviewer_panel_after_workers(entries, install_root):
    """3 reviewer dispatches should fire AFTER case-analyst dispatches.
    Episodic schema: action='agent: <name> — <desc>'."""
    reviewer_types = {"partner-strategy", "partner-analytics", "principal-delivery"}
    reviewers_seen = set()
    last_worker_ts = None
    first_reviewer_ts = None
    for e in entries:
        action = e.get("action", "")
        if not action.startswith("agent: "):
            continue
        # Parse "agent: <subagent_name> — <description>"
        rest = action[len("agent: "):]
        stype = rest.split(" — ", 1)[0].split(" ", 1)[0]
        t = _parse_ts(e.get("timestamp"))
        if t is None:
            continue
        if stype == "case-analyst":
            last_worker_ts = max(t, last_worker_ts) if last_worker_ts else t
        elif stype in reviewer_types:
            reviewers_seen.add(stype)
            first_reviewer_ts = min(t, first_reviewer_ts) if first_reviewer_ts else t
    if len(reviewers_seen) < 3:
        return False, f"only {len(reviewers_seen)} of 3 reviewers dispatched ({sorted(reviewers_seen)})"
    if last_worker_ts and first_reviewer_ts and first_reviewer_ts < last_worker_ts:
        return False, "reviewers fired BEFORE last case-analyst — wrong sequencing"
    return True, f"3 reviewers dispatched after workers: {sorted(reviewers_seen)}"


# ---- Episodic loading ------------------------------------------------

def _parse_ts(ts: str | None) -> dt.datetime | None:
    """Parse ISO timestamp; strip timezone for naive comparison."""
    if not ts:
        return None
    try:
        t = dt.datetime.fromisoformat(ts.rstrip("Z")).replace(tzinfo=None)
        if t.tzinfo is not None:
            t = t.replace(tzinfo=None)
        return t
    except ValueError:
        return None


def _load_episodic(since_minutes: int | None = None) -> list[dict]:
    if not EPISODIC.is_file():
        return []
    out = []
    cutoff = None
    if since_minutes is not None:
        # Episodic timestamps are written in UTC; compare in UTC to avoid
        # timezone drift (a Singapore-local cutoff against UTC stamps would
        # exclude entries written within the last 8 hours by local clock).
        cutoff = dt.datetime.utcnow() - dt.timedelta(minutes=since_minutes)
    for line in EPISODIC.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if cutoff is not None:
            t = _parse_ts(entry.get("timestamp"))
            if t is not None and t < cutoff:
                continue
        out.append(entry)
    return out


def _parse_since(s: str) -> int:
    """Parse '15m' / '2h' / '90' (minutes) into integer minutes."""
    s = s.strip()
    if s.endswith("h"):
        return int(s[:-1]) * 60
    if s.endswith("m"):
        return int(s[:-1])
    return int(s)


# ---- Output ----------------------------------------------------------

def _print_checklist(skill: str, phase: str, expectations: list[dict], install_root: Path, entries: list[dict]):
    n_pass = n_fail = n_pending = 0
    print(f"\n{BOLD}trace_check{RESET}  ·  {skill}  ·  phase={phase}  ·  {dt.datetime.now().strftime('%H:%M:%S')}")
    print(DIM + ("─" * 72) + RESET)
    for exp in expectations:
        ok, evidence = exp["matcher"](entries, install_root)
        is_critical = exp["severity"] == "critical"
        if ok:
            mark, n_pass = PASS, n_pass + 1
        elif is_critical:
            mark, n_fail = FAIL, n_fail + 1
        else:
            mark, n_pending = PEND, n_pending + 1
        sev_tag = {"critical": "CRITICAL", "warning": "warning", "info": "info"}[exp["severity"]]
        sev_color = {"critical": "\033[31m", "warning": "\033[33m", "info": "\033[2m"}[exp["severity"]] if BOLD else ""
        sev_close = RESET if BOLD else ""
        print(f"  {mark}  {exp['label']:<58} {sev_color}[{sev_tag}]{sev_close}")
        if evidence:
            print(f"     {DIM}{evidence}{RESET}")
    print(DIM + ("─" * 72) + RESET)
    total = len(expectations)
    print(f"  {n_pass}/{total} passing  ·  {n_fail} critical fail  ·  {n_pending} pending/info")
    if n_fail:
        print(f"  {FAIL} CRITICAL gaps — wiring may not be working as designed")
        return 1
    if n_pending:
        print(f"  {PEND} non-critical gaps — review and decide whether to enforce")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--skill", required=True, help="Skill name, e.g. consulting-deck-builder")
    parser.add_argument("--phase", required=True, help="Phase identifier, e.g. 1, 1-iteration, 2")
    parser.add_argument("--since", default="1h", help="Episodic window (e.g., 15m, 2h, 90)")
    parser.add_argument("--watch", action="store_true", help="Re-render every 3s")
    parser.add_argument("--no-color", action="store_true", help="Disable color")
    parser.add_argument("--install-root", default=str(INSTALL_ROOT), help="Override install root")
    args = parser.parse_args(argv)

    if args.no_color or not sys.stdout.isatty():
        _no_color()

    install_root = Path(args.install_root).resolve()
    expectations = _expectations(args.skill, args.phase)
    if not expectations:
        print(f"error: no expectations defined for ({args.skill}, phase={args.phase})", file=sys.stderr)
        print("       supported: consulting-deck-builder phase=1, phase=1-iteration, phase=2", file=sys.stderr)
        return 2

    since_min = _parse_since(args.since)
    if not args.watch:
        entries = _load_episodic(since_minutes=since_min)
        return _print_checklist(args.skill, args.phase, expectations, install_root, entries)
    try:
        while True:
            entries = _load_episodic(since_minutes=since_min)
            print("\033[2J\033[H", end="")  # clear screen
            _print_checklist(args.skill, args.phase, expectations, install_root, entries)
            time.sleep(3)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
