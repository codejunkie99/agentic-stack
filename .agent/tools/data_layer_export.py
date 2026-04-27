#!/usr/bin/env python3
"""Local data layer export for the portable agentic-stack brain.

Reads shared `.agent/` memory plus optional local data-layer inputs and writes
dashboard-ready JSONL, JSON, CSV, a dependency-free HTML dashboard, and a
terminal dashboard.

No network calls, no external dependencies, no telemetry.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

VALID_WINDOWS = {"7d", "30d", "90d", "all"}
VALID_BUCKETS = {"hour", "day", "week", "month"}


def _e(*codes: int) -> str:
    return f"\x1b[{';'.join(map(str, codes))}m"


def _hex(value: str) -> str:
    value = value.lstrip("#")
    r, g, b = int(value[:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return f"\x1b[38;2;{r};{g};{b}m"


RESET = _e(0)
BOLD = _e(1)
DIM = _e(2)
PURPLE = _hex("#BF5AF2")
BLUE = _hex("#0A84FF")
GREEN = _hex("#30D158")
ORANGE = _hex("#FF9F0A")
MUTED = _hex("#636366")
WHITE = _hex("#F5F5F7")


def paint(text: Any, color: str, enabled: bool) -> str:
    return f"{color}{text}{RESET}" if enabled else str(text)


def colored_stdout_enabled() -> bool:
    return not os.environ.get("NO_COLOR")


def rail(color: bool = False) -> str:
    return paint("│", MUTED, color)


def sha256(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def hash_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return f"sha256:{sha256(value)}"


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso(value: Any) -> str | None:
    parsed = parse_time(value)
    if not parsed:
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def safe_num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:
        return None
    return n


def safe_int(value: Any) -> int | None:
    n = safe_num(value)
    return None if n is None else int(round(n))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quality = {"missing": False, "malformed_lines": 0}
    if not path.exists():
        quality["missing"] = True
        return [], quality

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                quality["malformed_lines"] += 1
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
            else:
                quality["malformed_lines"] += 1
    return records, quality


def read_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    quality = {"missing": False, "malformed": False}
    if not path.exists():
        quality["missing"] = True
        return {}, quality
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        quality["malformed"] = True
        return {}, quality
    return parsed if isinstance(parsed, dict) else {}, quality


def cutoff_for(window: str) -> dt.datetime | None:
    if window == "all":
        return None
    days = int(window[:-1])
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)


def nearest_window(days: int) -> str:
    if days <= 7:
        return "7d"
    if days <= 30:
        return "30d"
    if days <= 90:
        return "90d"
    return "all"


def parse_natural_language_request(text: str) -> dict[str, str]:
    request = " ".join(text.split())
    if not request:
        return {}

    key = request.lower()
    parsed: dict[str, str] = {}

    bucket_patterns = [
        ("hour", (r"\bby hour\b", r"\bper hour\b", r"\bhourly\b", r"\beach hour\b")),
        ("day", (r"\bby day\b", r"\bper day\b", r"\bdaily\b", r"\beach day\b")),
        ("week", (r"\bby week\b", r"\bper week\b", r"\bweekly\b", r"\beach week\b")),
        ("month", (r"\bby month\b", r"\bper month\b", r"\bmonthly\b", r"\beach month\b")),
    ]
    for bucket, patterns in bucket_patterns:
        if any(re.search(pattern, key) for pattern in patterns):
            parsed["bucket"] = bucket
            break

    if re.search(r"\b(all time|everything|all history|entire history)\b", key):
        parsed["window"] = "all"
    elif re.search(r"\b(today|last 24 hours|past 24 hours)\b", key):
        parsed.setdefault("bucket", "hour")
        parsed["window"] = "7d"
    elif re.search(r"\b(this week|past week|last week|weekly view)\b", key):
        parsed["window"] = "7d"
    elif re.search(r"\b(this month|past month|last month|monthly view)\b", key):
        parsed["window"] = "30d"
    elif re.search(r"\b(this quarter|past quarter|last quarter|quarterly view)\b", key):
        parsed["window"] = "90d"

    match = re.search(
        r"\b(?:last|past|previous|prior|over|for)?\s*(\d+)\s*(hours?|hrs?|h|days?|d|weeks?|w|months?|mos?|mo)\b",
        key,
    )
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit.startswith(("hour", "hr", "h")):
            days = max(1, (amount + 23) // 24)
            parsed.setdefault("bucket", "hour")
        elif unit.startswith(("week", "w")):
            days = amount * 7
        elif unit.startswith(("month", "mo")):
            days = amount * 30
        else:
            days = amount
        parsed["window"] = nearest_window(days)

    return parsed


def flag_was_provided(argv: list[str], flag: str) -> bool:
    return any(token == flag or token.startswith(f"{flag}=") for token in argv)


def apply_natural_language_request(args: argparse.Namespace, argv: list[str]) -> None:
    request_text = " ".join(args.request).strip()
    args.request_text = " ".join(request_text.split())
    parsed = parse_natural_language_request(args.request_text)
    if parsed.get("window") and not flag_was_provided(argv, "--window"):
        args.window = parsed["window"]
    if parsed.get("bucket") and not flag_was_provided(argv, "--bucket"):
        args.bucket = parsed["bucket"]


def inside_window(record: dict[str, Any], cutoff: dt.datetime | None) -> bool:
    if cutoff is None:
        return True
    ts = parse_time(record.get("timestamp") or record.get("created_at") or record.get("started_at"))
    return ts is not None and ts >= cutoff


def slug(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    out = []
    last_sep = False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            last_sep = False
        elif not last_sep:
            out.append("_")
            last_sep = True
    cleaned = "".join(out).strip("_")
    return cleaned[:80] or fallback


def normalize_harness(value: Any) -> str:
    key = slug(value)
    if "claude" in key:
        return "claude-code"
    if "openclaw" in key:
        return "openclaw"
    if "hermes" in key:
        return "hermes"
    if "codex" in key:
        return "codex"
    if "cursor" in key:
        return "cursor"
    if "opencode" in key:
        return "opencode"
    if "windsurf" in key:
        return "windsurf"
    if key in {"pi", "pi_coding_agent"}:
        return "pi"
    if "antigravity" in key:
        return "antigravity"
    return key or "unknown"


def infer_phase(action: str, skill: str) -> str:
    key = f"{action} {skill}".lower()
    if any(term in key for term in ("plan", "design", "spec")):
        return "plan"
    if any(term in key for term in ("review", "audit", "security")):
        return "review"
    if any(term in key for term in ("test", "qa", "verify", "benchmark")):
        return "qa"
    if any(term in key for term in ("ship", "deploy", "release")):
        return "ship"
    if any(term in key for term in ("debug", "investigate", "failure")):
        return "debug"
    if any(term in key for term in ("reflect", "memory", "learn", "dream")):
        return "memory"
    return "analysis"


def infer_workflow(action: str, skill: str) -> str:
    phase = infer_phase(action, skill)
    if phase in {"plan", "review", "qa", "ship", "debug", "memory"}:
        return phase
    return slug(skill or action, "analysis")


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_category_rules(config: dict[str, Any]) -> dict[str, Any]:
    rules = []
    for raw in as_list(config.get("rules")):
        if not isinstance(raw, dict) or not raw.get("category"):
            continue
        rules.append(
            {
                "category": slug(raw.get("category"), "uncategorized"),
                "skills": [slug(x) for x in as_list(raw.get("skills"))],
                "actions": [slug(x) for x in as_list(raw.get("actions"))],
                "workflows": [slug(x) for x in as_list(raw.get("workflows"))],
                "phases": [slug(x) for x in as_list(raw.get("phases"))],
                "harnesses": [normalize_harness(x) for x in as_list(raw.get("harnesses"))],
                "profiles": [slug(x) for x in as_list(raw.get("profiles"))],
                "run_types": [slug(x) for x in as_list(raw.get("run_types"))],
                "results": [slug(x) for x in as_list(raw.get("results"))],
            }
        )
    return {
        "default_category": slug(config.get("default_category"), "uncategorized"),
        "rules": rules,
    }


def resolve_category(record: dict[str, Any], rules: dict[str, Any]) -> str:
    explicit = slug(record.get("category"), "")
    if explicit:
        return explicit
    tests = {
        "skills": slug(record.get("skill"), ""),
        "actions": slug(record.get("action"), ""),
        "workflows": slug(record.get("workflow"), ""),
        "phases": slug(record.get("phase"), ""),
        "harnesses": normalize_harness(record.get("harness")),
        "profiles": slug(record.get("profile"), ""),
        "run_types": slug(record.get("run_type"), ""),
        "results": slug(record.get("result") or record.get("status"), ""),
    }
    for rule in rules["rules"]:
        for key, value in tests.items():
            if value and value in rule.get(key, []):
                return rule["category"]
    return rules["default_category"]


def normalize_agent_event(entry: dict[str, Any], idx: int, args: argparse.Namespace, rules: dict[str, Any]) -> dict[str, Any]:
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    started = iso(entry.get("timestamp")) or now_iso()
    skill = str(entry.get("skill") or source.get("skill") or "unknown")
    action = str(entry.get("action") or "")
    harness = normalize_harness(entry.get("harness") or source.get("harness") or source.get("skill") or skill)
    profile_hash = hash_id(source.get("profile"))
    run_id_hash = hash_id(source.get("run_id"))
    duration_ms = safe_int(entry.get("duration_ms"))
    tokens_in = safe_num(entry.get("tokens_in_estimate"))
    tokens_out = safe_num(entry.get("tokens_out_estimate"))
    id_seed = f"{started}|{skill}|{action}|{source.get('run_id')}|{idx}"
    base = {
        "id": f"evt_{sha256(id_seed)[:16]}",
        "created_at": started,
        "started_at": started,
        "finished_at": iso(entry.get("finished_at")),
        "project": args.project,
        "harness": harness,
        "skill": skill,
        "action": action,
        "workflow": str(entry.get("workflow") or infer_workflow(action, skill)),
        "phase": str(entry.get("phase") or infer_phase(action, skill)),
        "run_type": str(entry.get("run_type") or "agent"),
        "result": str(entry.get("result") or "unknown"),
        "status": "success" if entry.get("result") == "success" else "error" if entry.get("result") == "failure" else str(entry.get("result") or "unknown"),
        "duration_ms": duration_ms,
        "importance": safe_int(entry.get("importance")),
        "pain_score": safe_int(entry.get("pain_score")),
        "confidence": safe_num(entry.get("confidence")),
        "tokens_in_estimate": tokens_in,
        "tokens_out_estimate": tokens_out,
        "tokens_total_estimate": (tokens_in or 0) + (tokens_out or 0) or None,
        "cost_estimate_usd": safe_num(entry.get("cost_estimate_usd")),
        "agent_id_hash": hash_id(source.get("run_id") or f"{harness}:{source.get('profile', '')}"),
        "profile_hash": profile_hash,
        "run_id_hash": run_id_hash,
        "privacy_level": str(entry.get("privacy_level") or "local_only"),
        "pii_level": str(entry.get("pii_level") or "unknown"),
    }
    base["category"] = resolve_category(base, rules)
    return base


def normalize_cron_run(entry: dict[str, Any], idx: int, args: argparse.Namespace, rules: dict[str, Any]) -> dict[str, Any]:
    started = iso(entry.get("started_at") or entry.get("timestamp") or entry.get("created_at")) or now_iso()
    finished = iso(entry.get("finished_at") or entry.get("ended_at"))
    start_dt = parse_time(started)
    finish_dt = parse_time(finished)
    duration_ms = safe_int(entry.get("duration_ms"))
    if duration_ms is None and start_dt and finish_dt:
        duration_ms = max(0, int((finish_dt - start_dt).total_seconds() * 1000))
    tokens_in = safe_num(entry.get("tokens_in_estimate"))
    tokens_out = safe_num(entry.get("tokens_out_estimate"))
    harness = normalize_harness(entry.get("harness") or entry.get("source") or "cron")
    id_seed = f"{started}|{entry.get('name')}|{idx}"
    base = {
        "id": str(entry.get("id") or f"cron_{sha256(id_seed)[:16]}"),
        "created_at": iso(entry.get("created_at") or started) or started,
        "started_at": started,
        "finished_at": finished,
        "project": str(entry.get("project") or args.project),
        "harness": harness,
        "schedule": entry.get("schedule"),
        "name": str(entry.get("name") or entry.get("workflow") or "cron_run"),
        "workflow": str(entry.get("workflow") or "scheduled_workflow"),
        "phase": str(entry.get("phase") or "automation"),
        "run_type": "cron",
        "status": str(entry.get("status") or entry.get("result") or "unknown"),
        "duration_ms": duration_ms,
        "tokens_in_estimate": tokens_in,
        "tokens_out_estimate": tokens_out,
        "tokens_total_estimate": (tokens_in or 0) + (tokens_out or 0) or None,
        "cost_estimate_usd": safe_num(entry.get("cost_estimate_usd")),
        "agent_id_hash": entry.get("agent_id_hash") or hash_id(entry.get("agent_id") or entry.get("run_id") or entry.get("profile")),
        "privacy_level": str(entry.get("privacy_level") or "local_only"),
        "pii_level": str(entry.get("pii_level") or "unknown"),
    }
    base["category"] = resolve_category(base, rules)
    return base


def bucket_start(value: str, bucket: str) -> str:
    parsed = parse_time(value)
    if not parsed:
        return "unknown"
    if bucket == "hour":
        parsed = parsed.replace(minute=0, second=0, microsecond=0)
    elif bucket == "day":
        parsed = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
    elif bucket == "week":
        parsed = (parsed - dt.timedelta(days=parsed.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif bucket == "month":
        parsed = parsed.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return parsed.isoformat().replace("+00:00", "Z")


def build_activity_series(agent_events: list[dict[str, Any]], cron_runs: list[dict[str, Any]], bucket: str) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    active: dict[str, set[str]] = {}

    def row_for(ts: str) -> dict[str, Any]:
        key = bucket_start(ts, bucket)
        rows.setdefault(
            key,
            {
                "bucket_start": key,
                "agent_events": 0,
                "cron_runs": 0,
                "tokens_in_estimate": 0,
                "tokens_out_estimate": 0,
                "tokens_total_estimate": 0,
                "cost_estimate_usd": 0,
                "active_agents": 0,
            },
        )
        return rows[key]

    for event in agent_events:
        row = row_for(event["started_at"])
        row["agent_events"] += 1
        row["tokens_in_estimate"] += event.get("tokens_in_estimate") or 0
        row["tokens_out_estimate"] += event.get("tokens_out_estimate") or 0
        row["tokens_total_estimate"] += event.get("tokens_total_estimate") or 0
        row["cost_estimate_usd"] += event.get("cost_estimate_usd") or 0
        if event.get("agent_id_hash"):
            active.setdefault(row["bucket_start"], set()).add(event["agent_id_hash"])

    for run in cron_runs:
        row = row_for(run["started_at"])
        row["cron_runs"] += 1
        row["tokens_in_estimate"] += run.get("tokens_in_estimate") or 0
        row["tokens_out_estimate"] += run.get("tokens_out_estimate") or 0
        row["tokens_total_estimate"] += run.get("tokens_total_estimate") or 0
        row["cost_estimate_usd"] += run.get("cost_estimate_usd") or 0
        if run.get("agent_id_hash"):
            active.setdefault(row["bucket_start"], set()).add(run["agent_id_hash"])

    for key, agents in active.items():
        rows[key]["active_agents"] = len(agents)

    return sorted(rows.values(), key=lambda row: row["bucket_start"])


def count_by(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = str(record.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def sum_field(records: list[dict[str, Any]], field: str) -> float:
    return sum((safe_num(record.get(field)) or 0) for record in records)


def median(values: list[float]) -> float | None:
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2


def observed_days(records: list[dict[str, Any]]) -> int:
    days = set()
    for record in records:
        parsed = parse_time(record.get("started_at") or record.get("created_at"))
        if parsed:
            days.add(parsed.date().isoformat())
    return max(1, len(days))


def category_summary(agent_events: list[dict[str, Any]], cron_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for record in agent_events + cron_runs:
        category = str(record.get("category") or "uncategorized")
        rows.setdefault(
            category,
            {
                "category": category,
                "agent_events": 0,
                "cron_runs": 0,
                "duration_ms": 0,
                "tokens_total_estimate": 0,
                "cost_estimate_usd": 0,
            },
        )
        row = rows[category]
        if record.get("run_type") == "cron":
            row["cron_runs"] += 1
        else:
            row["agent_events"] += 1
        row["duration_ms"] += record.get("duration_ms") or 0
        row["tokens_total_estimate"] += record.get("tokens_total_estimate") or 0
        row["cost_estimate_usd"] += record.get("cost_estimate_usd") or 0
    for row in rows.values():
        row["hours"] = round(row["duration_ms"] / 3600000, 2)
        row["cost_estimate_usd"] = round(row["cost_estimate_usd"], 4)
    return sorted(rows.values(), key=lambda row: (-(row["agent_events"] + row["cron_runs"]), row["category"]))


def harness_summary(agent_events: list[dict[str, Any]], cron_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for record in agent_events + cron_runs:
        harness = str(record.get("harness") or "unknown")
        rows.setdefault(
            harness,
            {
                "harness": harness,
                "agent_events": 0,
                "cron_runs": 0,
                "successes": 0,
                "errors": 0,
                "tokens_total_estimate": 0,
                "cost_estimate_usd": 0,
                "active_agents": set(),
            },
        )
        row = rows[harness]
        if record.get("run_type") == "cron":
            row["cron_runs"] += 1
        else:
            row["agent_events"] += 1
        if record.get("status") == "success" or record.get("result") == "success":
            row["successes"] += 1
        elif record.get("status") == "error" or record.get("result") == "failure":
            row["errors"] += 1
        row["tokens_total_estimate"] += record.get("tokens_total_estimate") or 0
        row["cost_estimate_usd"] += record.get("cost_estimate_usd") or 0
        if record.get("agent_id_hash"):
            row["active_agents"].add(record["agent_id_hash"])
    out = []
    for row in rows.values():
        converted = dict(row)
        converted["active_agents"] = len(row["active_agents"])
        converted["cost_estimate_usd"] = round(row["cost_estimate_usd"], 4)
        out.append(converted)
    return sorted(out, key=lambda row: (-(row["agent_events"] + row["cron_runs"]), row["harness"]))


def workflow_summary(agent_events: list[dict[str, Any]], cron_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for record in agent_events + cron_runs:
        workflow = str(record.get("workflow") or "unknown")
        rows.setdefault(
            workflow,
            {
                "workflow": workflow,
                "agent_events": 0,
                "cron_runs": 0,
                "successes": 0,
                "errors": 0,
                "tokens_total_estimate": 0,
                "cost_estimate_usd": 0,
            },
        )
        row = rows[workflow]
        if record.get("run_type") == "cron":
            row["cron_runs"] += 1
        else:
            row["agent_events"] += 1
        if record.get("status") == "success" or record.get("result") == "success":
            row["successes"] += 1
        elif record.get("status") == "error" or record.get("result") == "failure":
            row["errors"] += 1
        row["tokens_total_estimate"] += record.get("tokens_total_estimate") or 0
        row["cost_estimate_usd"] += record.get("cost_estimate_usd") or 0
    for row in rows.values():
        total = row["agent_events"] + row["cron_runs"]
        row["success_rate"] = round(row["successes"] / total, 3) if total else None
        row["cost_estimate_usd"] = round(row["cost_estimate_usd"], 4)
    return sorted(rows.values(), key=lambda row: (-(row["agent_events"] + row["cron_runs"]), row["workflow"]))


def build_cron_timeline(cron_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed_runs = []
    for idx, run in enumerate(cron_runs):
        start = parse_time(run.get("started_at"))
        finish = parse_time(run.get("finished_at")) or start
        if not start:
            continue
        if finish and finish < start:
            finish = start
        parsed_runs.append((idx, run, start, finish or start))

    if not parsed_runs:
        return []

    timeline_start = min(start for _, _, start, _ in parsed_runs)
    timeline_end = max(finish for _, _, _, finish in parsed_runs)
    span_ms = max(1, int((timeline_end - timeline_start).total_seconds() * 1000))
    rows: list[dict[str, Any]] = []
    for lane, (idx, run, start, finish) in enumerate(sorted(parsed_runs, key=lambda item: (item[2], item[1].get("name") or ""))):
        duration_ms = run.get("duration_ms")
        if duration_ms is None:
            duration_ms = max(0, int((finish - start).total_seconds() * 1000))
        offset_ms = max(0, int((start - timeline_start).total_seconds() * 1000))
        width_ms = max(1, int((finish - start).total_seconds() * 1000))
        rows.append(
            {
                "id": run.get("id"),
                "lane": lane,
                "name": run.get("name"),
                "harness": run.get("harness"),
                "workflow": run.get("workflow"),
                "category": run.get("category"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "duration_ms": duration_ms,
                "status": run.get("status"),
                "timeline_start": timeline_start.isoformat().replace("+00:00", "Z"),
                "timeline_end": timeline_end.isoformat().replace("+00:00", "Z"),
                "start_offset_pct": round(offset_ms / span_ms * 100, 3),
                "width_pct": round(max(width_ms / span_ms * 100, 0.8), 3),
            }
        )
    return rows


def build_kpi_summary(agent_events: list[dict[str, Any]], cron_runs: list[dict[str, Any]], categories: list[dict[str, Any]], harnesses: list[dict[str, Any]], workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    all_records = agent_events + cron_runs
    total_runs = len(all_records)
    successes = sum(1 for record in all_records if record.get("status") == "success" or record.get("result") == "success")
    errors = sum(1 for record in all_records if record.get("status") == "error" or record.get("result") == "failure")
    duration_values = [float(record["duration_ms"]) for record in all_records if record.get("duration_ms") is not None]
    days = observed_days(all_records)
    active_agents = len({record.get("agent_id_hash") for record in all_records if record.get("agent_id_hash")})
    total_tokens = sum_field(agent_events, "tokens_total_estimate") + sum_field(cron_runs, "tokens_total_estimate")
    total_cost = sum_field(agent_events, "cost_estimate_usd") + sum_field(cron_runs, "cost_estimate_usd")

    rows = [
        ("agent_events", len(agent_events), "events", "Non-cron agent actions observed across harnesses."),
        ("cron_runs", len(cron_runs), "runs", "Scheduled or cron-triggered agent runs."),
        ("cron_runs_per_day", round(len(cron_runs) / days, 3), "runs/day", "Observed scheduled-agent cadence."),
        ("events_per_day", round(len(agent_events) / days, 3), "events/day", "Observed non-cron agent activity cadence."),
        ("active_agents", active_agents, "agents", "Distinct hashed agent/run identities observed."),
        ("harnesses", len(harnesses), "harnesses", "Distinct harnesses such as Claude Code, Hermes, OpenClaw, Codex, or Cursor."),
        ("workflows", len(workflows), "workflows", "Distinct workflow names observed."),
        ("categories", len(categories), "categories", "User-defined resource categories observed."),
        ("successes", successes, "runs", "Runs marked success."),
        ("errors", errors, "runs", "Runs marked error or failure."),
        ("success_rate", round(successes / total_runs, 3) if total_runs else None, "ratio", "Successful runs divided by all observed runs."),
        ("error_rate", round(errors / total_runs, 3) if total_runs else None, "ratio", "Errored runs divided by all observed runs."),
        ("median_duration_ms", median(duration_values), "ms", "Median duration across runs with duration data."),
        ("tokens_total_estimate", total_tokens, "tokens", "Estimated input plus output tokens."),
        ("tokens_per_run_estimate", round(total_tokens / total_runs, 3) if total_runs else None, "tokens/run", "Estimated tokens divided by observed runs."),
        ("cost_estimate_usd", round(total_cost, 4), "USD", "Estimated total model/tool cost when supplied by harnesses."),
        ("cost_per_run_estimate_usd", round(total_cost / total_runs, 4) if total_runs else None, "USD/run", "Estimated cost divided by observed runs."),
    ]
    return [{"kpi": kpi, "value": value, "unit": unit, "description": description} for kpi, value, unit, description in rows]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def bar_rows(rows: list[dict[str, Any]], label: str, value: str, color: str = "#2563eb") -> str:
    max_value = max([safe_num(row.get(value)) or 0 for row in rows] + [1])
    out = []
    for row in rows:
        n = safe_num(row.get(value)) or 0
        width = max(2, int(n / max_value * 100))
        out.append(
            "<div class='bar-row'>"
            f"<span>{html.escape(str(row.get(label, '')))}</span>"
            f"<div class='track'><div class='bar' style='width:{width}%;background:{color}'></div></div>"
            f"<strong>{n:g}</strong></div>"
        )
    return "\n".join(out) or "<p>No data yet.</p>"


def table_html(headers: list[str], rows: list[dict[str, Any]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows[:50]:
        cells = "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def timeline_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No cron timeline data yet.</p>"
    out = []
    for row in rows[:80]:
        label = f"{row.get('name', '')} - {row.get('harness', '')}"
        width = max(0.8, safe_num(row.get("width_pct")) or 0.8)
        left = min(99, max(0, safe_num(row.get("start_offset_pct")) or 0))
        out.append(
            "<div class='timeline-row'>"
            f"<span>{html.escape(label)}</span>"
            "<div class='timeline-track'>"
            f"<div class='timeline-bar' style='left:{left}%;width:{width}%' title='{html.escape(str(row.get('started_at')))} to {html.escape(str(row.get('finished_at')))}'></div>"
            "</div>"
            f"<strong>{html.escape(str(row.get('status', '')))}</strong>"
            "</div>"
        )
    return "\n".join(out)


def write_dashboard(path: Path, summary: dict[str, Any], activity: list[dict[str, Any]], categories: list[dict[str, Any]], harnesses: list[dict[str, Any]], workflows: list[dict[str, Any]], cron_runs: list[dict[str, Any]], cron_timeline: list[dict[str, Any]], kpis: list[dict[str, Any]]) -> None:
    css = """
body{margin:0;background:#f7f9fb;color:#172033;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{background:#fff;border-bottom:1px solid #d9e0e8;padding:28px 32px}
h1{margin:0 0 8px;font-size:28px} h2{font-size:18px;margin:0 0 14px}
p{color:#657286} main{padding:24px 32px 40px;display:grid;gap:18px}
section{background:#fff;border:1px solid #d9e0e8;border-radius:8px;padding:18px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.metric{border:1px solid #d9e0e8;border-radius:8px;padding:14px;background:#fbfcfe}
.metric b{display:block;font-size:28px}.metric span{color:#657286;font-size:13px}
.bar-row{display:grid;grid-template-columns:160px 1fr 72px;gap:10px;align-items:center;min-height:28px;font-size:13px}
.track{height:16px;background:#edf2f7;border-radius:4px;overflow:hidden}.bar{height:100%;border-radius:4px}
.timeline-row{display:grid;grid-template-columns:220px minmax(320px,1fr) 88px;gap:10px;align-items:center;min-height:30px;font-size:13px}
.timeline-track{height:20px;background:#edf2f7;border-radius:4px;position:relative;overflow:hidden}
.timeline-bar{position:absolute;top:0;height:100%;background:#0f766e;border-radius:4px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;border-bottom:1px solid #d9e0e8;padding:8px 6px;vertical-align:top}
th{color:#657286}.scroll{overflow-x:auto}.footer{font-size:12px;color:#657286}
"""
    metric_cards = [
        ("Agent events", summary["counts"]["agent_events"]),
        ("Cron runs", summary["counts"]["cron_runs"]),
        ("Harnesses", summary["counts"]["harnesses"]),
        ("Active agents", summary["counts"]["active_agents"]),
        ("Tokens est.", int(summary["resources"]["tokens_total_estimate"])),
        ("Cost est.", f"${summary['resources']['cost_estimate_usd']:.2f}"),
    ]
    cards = "".join(f"<div class='metric'><b>{html.escape(str(v))}</b><span>{html.escape(k)}</span></div>" for k, v in metric_cards)
    cron_table = table_html(
        ["Name", "Harness", "Workflow", "Category", "Start", "Finish", "Duration ms", "Status"],
        cron_runs,
        ["name", "harness", "workflow", "category", "started_at", "finished_at", "duration_ms", "status"],
    )
    path.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>agentic-stack Data Layer Dashboard</title><style>{css}</style></head>
<body><header><h1>agentic-stack Data Layer Dashboard</h1>
<p>{html.escape(summary['project'])} - {html.escape(summary['window'])} - bucket: {html.escape(summary['bucket'])} - generated {html.escape(summary['generated_at'])}</p></header>
<main>
<section><h2>Resource Overview</h2><div class="grid">{cards}</div></section>
<section><h2>KPI Summary</h2><div class="scroll">{table_html(['KPI','Value','Unit','Description'], kpis, ['kpi','value','unit','description'])}</div></section>
<section><h2>Activity By {html.escape(summary['bucket'].title())}</h2>{bar_rows(activity, 'bucket_start', 'agent_events', '#0f766e')}</section>
<section><h2>Tokens By {html.escape(summary['bucket'].title())}</h2>{bar_rows(activity, 'bucket_start', 'tokens_total_estimate', '#2563eb')}</section>
<section><h2>Cron Runs</h2>{bar_rows(activity, 'bucket_start', 'cron_runs', '#b45309')}</section>
<section><h2>Task Categories</h2>{bar_rows(categories, 'category', 'agent_events', '#7c3aed')}</section>
<section><h2>Harness Mix</h2>{bar_rows(harnesses, 'harness', 'agent_events', '#0369a1')}</section>
<section><h2>Workflow Outcomes</h2><div class="scroll">{table_html(['Workflow','Agent events','Cron runs','Successes','Errors','Success rate','Tokens','Cost'], workflows, ['workflow','agent_events','cron_runs','successes','errors','success_rate','tokens_total_estimate','cost_estimate_usd'])}</div></section>
<section><h2>Cron Gantt</h2><div class="scroll">{timeline_html(cron_timeline)}</div></section>
<section><h2>Cron Timeline</h2><div class="scroll">{cron_table}</div></section>
<p class="footer">Local-only dashboard. Review privacy and PII status before sharing screenshots.</p>
</main></body></html>
""",
        encoding="utf-8",
    )


def build_summary(args: argparse.Namespace, quality: dict[str, Any], agent_events: list[dict[str, Any]], cron_runs: list[dict[str, Any]], categories: list[dict[str, Any]], harnesses: list[dict[str, Any]]) -> dict[str, Any]:
    active_agents = len({record.get("agent_id_hash") for record in agent_events + cron_runs if record.get("agent_id_hash")})
    return {
        "generated_at": now_iso(),
        "project": args.project,
        "window": args.window,
        "bucket": args.bucket,
        "request": getattr(args, "request_text", "") or None,
        "privacy_model": "local_only",
        "counts": {
            "agent_events": len(agent_events),
            "cron_runs": len(cron_runs),
            "harnesses": len(harnesses),
            "categories": len(categories),
            "active_agents": active_agents,
        },
        "resources": {
            "tokens_in_estimate": sum_field(agent_events, "tokens_in_estimate") + sum_field(cron_runs, "tokens_in_estimate"),
            "tokens_out_estimate": sum_field(agent_events, "tokens_out_estimate") + sum_field(cron_runs, "tokens_out_estimate"),
            "tokens_total_estimate": sum_field(agent_events, "tokens_total_estimate") + sum_field(cron_runs, "tokens_total_estimate"),
            "cost_estimate_usd": round(sum_field(agent_events, "cost_estimate_usd") + sum_field(cron_runs, "cost_estimate_usd"), 4),
        },
        "top_harnesses": count_by(agent_events + cron_runs, "harness"),
        "top_skills": count_by(agent_events, "skill"),
        "top_workflows": count_by(agent_events + cron_runs, "workflow"),
        "categories": count_by(agent_events + cron_runs, "category"),
        "data_quality": quality,
        "daily_report": {
            "screenshot_target": "dashboard.html",
            "recommended_sections": [
                "Resource Overview",
                "Activity By Bucket",
                "Tokens By Bucket",
                "Cron Runs",
                "Task Categories",
                "Harness Mix",
                "Workflow Outcomes",
                "KPI Summary",
                "Cron Gantt",
                "Cron Timeline",
            ],
            "delivery": "user-approved channel only",
        },
    }


def build_dashboard_report(args: argparse.Namespace, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"daily_agent_resource_report_{args.date}",
        "cadence": "daily",
        "timezone": args.timezone,
        "generated_at": summary["generated_at"],
        "dashboard_html": "dashboard.html",
        "terminal_dashboard": "dashboard.tui.txt",
        "daily_report_md": "daily-report.md",
        "screenshot_target": "dashboard.html",
        "charts": [
            "resource_overview",
            "activity",
            "tokens",
            "cron_runs",
            "task_categories",
            "harness_mix",
            "workflow_outcomes",
            "kpi_summary",
            "cron_gantt",
            "cron_timeline",
        ],
        "delivery": {
            "status": "not_configured",
            "requires_user_approval": True,
            "note": "Agents can attach screenshots or the daily report only after the user approves a destination.",
        },
        "privacy_level": "local_only",
        "pii_level": "unknown",
    }


def write_daily_report(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(
        f"""# Daily agentic-stack Resource Report

Generated: {summary['generated_at']}

## Key Numbers

- Agent events: {summary['counts']['agent_events']}
- Cron runs: {summary['counts']['cron_runs']}
- Harnesses observed: {summary['counts']['harnesses']}
- Active agents: {summary['counts']['active_agents']}
- Estimated tokens: {summary['resources']['tokens_total_estimate']}
- Estimated cost: ${summary['resources']['cost_estimate_usd']}

## Screenshot Target

Open `dashboard.html` and capture the Resource Overview, Activity, Tokens,
Cron Runs, Task Categories, Harness Mix, Workflow Outcomes, KPI Summary,
Cron Gantt, and Cron Timeline sections.

This report does not send data anywhere. A host agent may deliver screenshots
only through an explicitly user-approved channel.
""",
        encoding="utf-8",
    )


def compact_value(value: Any, prefix: str = "", suffix: str = "") -> str:
    n = safe_num(value)
    if n is None:
        return "n/a"
    if abs(n) >= 1000000:
        text = f"{n / 1000000:.1f}M"
    elif abs(n) >= 1000:
        text = f"{n / 1000:.1f}k"
    elif n == int(n):
        text = str(int(n))
    else:
        text = f"{n:.2f}".rstrip("0").rstrip(".")
    return f"{prefix}{text}{suffix}"


def plain_bar(value: Any, max_value: float, width: int = 18) -> str:
    n = safe_num(value) or 0
    filled = 0 if max_value <= 0 else int(round(n / max_value * width))
    filled = max(0, min(width, filled))
    return "#" * filled + "-" * (width - filled)


def top_table(rows: list[dict[str, Any]], label_field: str, value_field: str, secondary_value_field: str = "", limit: int = 5, color: bool = False) -> list[str]:
    if not rows:
        return [f"{rail(color)}  {paint('no data yet', MUTED, color)}"]
    top = rows[:limit]
    values = [
        (safe_num(row.get(value_field)) or 0) + (safe_num(row.get(secondary_value_field)) or 0)
        for row in top
    ]
    max_value = max(values + [1])
    lines = []
    for row, value in zip(top, values):
        label = str(row.get(label_field) or "unknown")[:22].ljust(22)
        bar = plain_bar(value, max_value)
        lines.append(
            f"{rail(color)}  {paint(label, WHITE, color)} "
            f"[{paint(bar, BLUE, color)}] {paint(compact_value(value), f'{BOLD}{WHITE}', color)}"
        )
    return lines


def metric_line(label: str, value: str, color: bool = False) -> str:
    return (
        f"{paint('◆', PURPLE, color)}  {paint(label.ljust(14), DIM, color)} "
        f"{paint('...', MUTED, color)} {paint(value, f'{BOLD}{WHITE}', color)}"
    )


def section_line(title: str, color: bool = False) -> str:
    return f"{rail(color)}  {paint(title, f'{BOLD}{ORANGE}', color)}"


def render_terminal_dashboard(out_dir: Path, color: bool = False) -> str:
    summary = json.loads((out_dir / "dashboard-summary.json").read_text(encoding="utf-8"))
    activity = json.loads((out_dir / "activity-series.json").read_text(encoding="utf-8"))
    categories = json.loads((out_dir / "category-summary.json").read_text(encoding="utf-8"))
    harnesses = json.loads((out_dir / "harness-summary.json").read_text(encoding="utf-8"))
    workflows = json.loads((out_dir / "workflow-summary.json").read_text(encoding="utf-8"))

    resources = summary["resources"]
    counts = summary["counts"]
    latest_activity = activity[-1] if activity else {}
    lines = [
        f"{paint('◇', PURPLE, color)}  {paint('agentic-stack Data Layer', f'{BOLD}{WHITE}', color)}  {paint('Terminal Dashboard', MUTED, color)}",
        rail(color),
        f"{rail(color)}  project={summary['project']} window={summary['window']} bucket={summary['bucket']}",
        f"{rail(color)}  generated={summary['generated_at']}",
    ]
    if summary.get("request"):
        lines.append(f"{rail(color)}  Request ... {paint(summary['request'], f'{BOLD}{WHITE}', color)}")
    lines.extend([
        rail(color),
        section_line("Resource Overview", color),
        metric_line("Agent events", compact_value(counts["agent_events"]), color),
        metric_line("Cron runs", compact_value(counts["cron_runs"]), color),
        metric_line("Harnesses", compact_value(counts["harnesses"]), color),
        metric_line("Active agents", compact_value(counts["active_agents"]), color),
        metric_line("Tokens est.", compact_value(resources["tokens_total_estimate"]), color),
        metric_line("Cost est.", compact_value(resources["cost_estimate_usd"], prefix="$"), color),
        rail(color),
        section_line("Latest Bucket", color),
        f"{rail(color)}  {latest_activity.get('bucket_start', 'no activity')}  "
        f"events={compact_value(latest_activity.get('agent_events'))} "
        f"cron={compact_value(latest_activity.get('cron_runs'))} "
        f"tokens={compact_value(latest_activity.get('tokens_total_estimate'))}",
        rail(color),
        section_line("Top Harnesses", color),
        *top_table(harnesses, "harness", "agent_events", "cron_runs", color=color),
        rail(color),
        section_line("Top Workflows", color),
        *top_table(workflows, "workflow", "agent_events", "cron_runs", color=color),
        rail(color),
        section_line("Top Categories", color),
        *top_table(categories, "category", "agent_events", "cron_runs", color=color),
        rail(color),
        f"{paint('└', MUTED, color)}  Open in browser: {out_dir / 'dashboard.html'}",
        f"{rail(color)}  Terminal copy : {out_dir / 'dashboard.tui.txt'}",
        f"{rail(color)}  Privacy       : local-only; screenshots require explicit user approval",
    ])
    return "\n".join(lines) + "\n"


def export(args: argparse.Namespace) -> Path:
    agent_root = Path(args.agent_root).resolve()
    data_dir = agent_root / "data-layer"
    episodic_path = Path(args.episodic) if args.episodic else agent_root / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
    extra_events_path = Path(args.events) if args.events else data_dir / "harness-events.jsonl"
    cron_path = Path(args.cron_runs) if args.cron_runs else data_dir / "cron-runs.jsonl"
    category_path = Path(args.category_rules) if args.category_rules else data_dir / "category-rules.json"
    out_dir = Path(args.out) if args.out else data_dir / "exports" / args.date

    cutoff = cutoff_for(args.window)
    category_config, category_quality = read_json(category_path)
    category_rules = load_category_rules(category_config)
    episodic, episodic_quality = read_jsonl(episodic_path)
    extras, extras_quality = read_jsonl(extra_events_path)
    cron_raw, cron_quality = read_jsonl(cron_path)

    raw_agent = [r for r in episodic + extras if inside_window(r, cutoff)]
    agent_events = [normalize_agent_event(r, i, args, category_rules) for i, r in enumerate(raw_agent)]
    cron_runs = [normalize_cron_run(r, i, args, category_rules) for i, r in enumerate(cron_raw) if inside_window(r, cutoff)]
    activity = build_activity_series(agent_events, cron_runs, args.bucket)
    categories = category_summary(agent_events, cron_runs)
    harnesses = harness_summary(agent_events, cron_runs)
    workflows = workflow_summary(agent_events, cron_runs)
    cron_timeline = build_cron_timeline(cron_runs)
    kpis = build_kpi_summary(agent_events, cron_runs, categories, harnesses, workflows)
    quality = {
        "episodic": episodic_quality,
        "extra_events": extras_quality,
        "cron_runs": cron_quality,
        "category_rules": category_quality,
        "note": "Local-only export. Review categories, token/cost estimates, and PII status before sharing.",
    }
    summary = build_summary(args, quality, agent_events, cron_runs, categories, harnesses)
    dashboard_report = build_dashboard_report(args, summary)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "agent-events.jsonl", agent_events)
    write_csv(out_dir / "agent-events.csv", agent_events, [
        "id", "created_at", "started_at", "finished_at", "project", "harness", "skill", "action",
        "workflow", "phase", "run_type", "category", "result", "status", "duration_ms",
        "tokens_in_estimate", "tokens_out_estimate", "tokens_total_estimate", "cost_estimate_usd",
        "agent_id_hash", "profile_hash", "run_id_hash", "privacy_level", "pii_level",
    ])
    write_jsonl(out_dir / "cron-runs.jsonl", cron_runs)
    write_csv(out_dir / "cron-runs.csv", cron_runs, [
        "id", "created_at", "started_at", "finished_at", "project", "harness", "schedule", "name",
        "workflow", "phase", "run_type", "category", "status", "duration_ms", "tokens_in_estimate",
        "tokens_out_estimate", "tokens_total_estimate", "cost_estimate_usd", "agent_id_hash",
        "privacy_level", "pii_level",
    ])
    write_json(out_dir / "cron-timeline.json", cron_timeline)
    write_csv(out_dir / "cron-timeline.csv", cron_timeline, [
        "id", "lane", "name", "harness", "workflow", "category", "started_at", "finished_at",
        "duration_ms", "status", "timeline_start", "timeline_end", "start_offset_pct", "width_pct",
    ])
    write_json(out_dir / "activity-series.json", activity)
    write_csv(out_dir / "activity-series.csv", activity, [
        "bucket_start", "agent_events", "cron_runs", "tokens_in_estimate", "tokens_out_estimate",
        "tokens_total_estimate", "cost_estimate_usd", "active_agents",
    ])
    write_json(out_dir / "category-summary.json", categories)
    write_csv(out_dir / "category-summary.csv", categories, [
        "category", "agent_events", "cron_runs", "duration_ms", "hours", "tokens_total_estimate", "cost_estimate_usd",
    ])
    write_json(out_dir / "harness-summary.json", harnesses)
    write_csv(out_dir / "harness-summary.csv", harnesses, [
        "harness", "agent_events", "cron_runs", "successes", "errors", "tokens_total_estimate",
        "cost_estimate_usd", "active_agents",
    ])
    write_json(out_dir / "workflow-summary.json", workflows)
    write_csv(out_dir / "workflow-summary.csv", workflows, [
        "workflow", "agent_events", "cron_runs", "successes", "errors", "success_rate",
        "tokens_total_estimate", "cost_estimate_usd",
    ])
    write_json(out_dir / "kpi-summary.json", kpis)
    write_csv(out_dir / "kpi-summary.csv", kpis, ["kpi", "value", "unit", "description"])
    write_json(out_dir / "dashboard-summary.json", summary)
    write_json(out_dir / "dashboard-report.json", dashboard_report)
    write_dashboard(out_dir / "dashboard.html", summary, activity, categories, harnesses, workflows, cron_runs, cron_timeline, kpis)
    write_daily_report(out_dir / "daily-report.md", summary)
    (out_dir / "dashboard.tui.txt").write_text(render_terminal_dashboard(out_dir, color=False), encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Export local agentic-stack activity into dashboard-ready data.")
    parser.add_argument("--agent-root", default=".agent")
    parser.add_argument("--episodic", default="")
    parser.add_argument("--events", default="", help="Optional extra cross-harness event JSONL.")
    parser.add_argument("--cron-runs", default="", help="Optional cron/scheduled-run JSONL.")
    parser.add_argument("--category-rules", default="", help="Optional category rules JSON.")
    parser.add_argument("--out", default="")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--project", default=Path.cwd().name)
    parser.add_argument("--timezone", default=os.environ.get("TZ", "UTC"))
    parser.add_argument("--window", choices=sorted(VALID_WINDOWS), default="30d")
    parser.add_argument("--bucket", choices=sorted(VALID_BUCKETS), default="day")
    parser.add_argument("request", nargs="*", help="Optional natural language request, for example: show me last 7 days by hour")
    args = parser.parse_args()
    apply_natural_language_request(args, sys.argv[1:])
    out_dir = export(args)
    print(f"agentic-stack data layer export: {out_dir}")
    print(f"dashboard_html={out_dir / 'dashboard.html'}")
    print()
    print(render_terminal_dashboard(out_dir, color=colored_stdout_enabled()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
