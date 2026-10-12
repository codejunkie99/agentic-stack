"""Mission Control collectors for the v0.20 runtime: DAG plan runs, proactive
campaigns, the gated evolver, and Markdown memory tracks.

Everything is read from files under `<target>/.agent/`; nothing is executed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ENTRY = re.compile(r"^<!-- entry:(\S+) -->", re.M)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


_RUN_STATUS = {
    "completed": "pass",
    "running": "pass",
    "planned": "pass",
    "awaiting_approval": "warn",
    "suspended": "warn",
    "abandoned": "fail",
    "failed": "fail",
}


def plan_run_objects(target: Path, control_object, source) -> list[dict[str, Any]]:
    plans = target / ".agent" / "runtime" / "plans"
    objects: list[dict[str, Any]] = []
    if not plans.is_dir():
        return objects
    for run_dir in sorted(plans.iterdir(), reverse=True):
        run = _json(run_dir / "run.json")
        if not run:
            continue
        nodes = run.get("nodes") or {}
        counts: dict[str, int] = {}
        for state in nodes.values():
            key = str((state or {}).get("status", "pending"))
            counts[key] = counts.get(key, 0) + 1
        status = str(run.get("status", "planned"))
        summary = f"{status}; " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) if counts else status
        objects.append(
            control_object(
                f"plan-{run_dir.name}",
                "plan_run",
                str(run.get("run_id", run_dir.name)),
                _RUN_STATUS.get(status, "warn"),
                summary,
                source(api="/api/runs", path=run_dir / "run.json"),
                {
                    "run_id": run.get("run_id"),
                    "name": run.get("name"),
                    "run_status": status,
                    "node_counts": counts,
                    "updated_at": run.get("updated_at"),
                    "command": f"python3 .agent/tools/plan.py status {run.get('run_id', run_dir.name)}",
                },
            )
        )
        if len(objects) >= 12:
            break
    return objects


def campaign_objects(target: Path, control_object, source) -> list[dict[str, Any]]:
    log = target / ".agent" / "proactive" / "campaigns.jsonl"
    state: dict[str, dict[str, Any]] = {}
    for e in _jsonl(log):
        cid = e.get("campaign_id")
        kind = e.get("type")
        if kind == "campaign":
            state[cid] = {"target": e.get("target"), "status": "open", "wakes": 0, "rounds": 0,
                          "measurements": 0, "decisions": 0, "last_measurement": None}
            continue
        c = state.get(cid)
        if not c:
            continue
        if kind == "wake":
            c["wakes"] += 1
        elif kind == "round":
            c["rounds"] += 1
            c["wakes"] = max(0, c["wakes"] - 1)
        elif kind == "measurement":
            c["measurements"] += 1
            c["last_measurement"] = e.get("output")
        elif kind == "decision":
            c["decisions"] += 1
        elif kind == "close":
            c["status"] = "closed"
    objects: list[dict[str, Any]] = []
    for cid, c in list(state.items())[-12:]:
        objects.append(
            control_object(
                f"campaign-{cid}",
                "campaign",
                str(cid),
                "pass" if c["status"] == "closed" else "warn",
                f"{c['status']}; rounds={c['rounds']} pending wakes={c['wakes']} target={c['target']}",
                source(api="/api/runs", path=log),
                {**c, "campaign_id": cid, "command": f"python3 .agent/tools/proactive.py status {cid}"},
            )
        )
    return objects


def evolution_objects(target: Path, control_object, source) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evolve = target / ".agent" / "evolve"
    diagnoses = _jsonl(evolve / "diagnoses.jsonl")
    genebank = _jsonl(evolve / "genebank.jsonl")
    state = _json(evolve / "state.json") or {}
    candidates: list[dict[str, Any]] = []
    cand_dir = evolve / "candidates"
    if cand_dir.is_dir():
        for d in sorted(cand_dir.iterdir()):
            desc = _json(d / "descriptor.json")
            if desc:
                candidates.append(desc)
    confirmed = {str(r.get("harness_id")) for r in genebank}
    rounds_dir = evolve / "rounds"
    rounds = sorted(rounds_dir.glob("*.json")) if rounds_dir.is_dir() else []
    stats = {
        "diagnoses": len(diagnoses),
        "candidates": len(candidates),
        "confirmed": len([c for c in candidates if c.get("id") in confirmed]),
        "cells": len({f"{r.get('where')}|{r.get('pathology')}" for r in genebank}),
        "rounds": len(rounds),
        "round": state.get("round", 0),
        "stagnation": state.get("stagnation", 0),
    }
    objects = [
        control_object(
            "evolution-state",
            "evolution_summary",
            "Evolver state",
            "pass" if not candidates or stats["confirmed"] else "warn",
            f"round {stats['round']}, stagnation {stats['stagnation']}; "
            f"{stats['diagnoses']} diagnoses, {stats['candidates']} candidates, {stats['confirmed']} confirmed, {stats['cells']} gene-bank cells",
            source(api="/api/evolution", path=evolve / "state.json"),
            {**stats, "command": "python3 .agent/tools/evolve.py genebank"},
        )
    ]
    for c in candidates[-12:]:
        cid = str(c.get("id"))
        objects.append(
            control_object(
                f"candidate-{cid}",
                "evolution_candidate",
                cid,
                "pass" if cid in confirmed else "warn",
                f"{c.get('where')}/{c.get('pathology')}: {c.get('symptom', '')}"[:200],
                source(api="/api/evolution", path=cand_dir / cid / "descriptor.json"),
                {**c, "confirmed": cid in confirmed,
                 "command": f"python3 .agent/tools/evolve.py install {cid}" if cid in confirmed
                 else f"python3 .agent/tools/evolve.py screen {cid}"},
            )
        )
    by_cell: dict[str, dict[str, Any]] = {}
    for r in genebank:
        by_cell[f"{r.get('where')}|{r.get('pathology')}"] = r
    for key, r in list(by_cell.items())[:12]:
        objects.append(
            control_object(
                f"cell-{key}",
                "gene_bank_cell",
                key,
                "pass",
                f"incumbent {r.get('harness_id')} utility={r.get('utility')} (round {r.get('round_id')})",
                source(api="/api/evolution", path=evolve / "genebank.jsonl"),
                dict(r),
            )
        )
    return objects, stats


_TRACKS = (("episodes", "episode"), ("foresights", "foresight"), ("cases", "agent case"))


def track_objects(target: Path, control_object, source) -> list[dict[str, Any]]:
    memory = target / ".agent" / "memory"
    objects: list[dict[str, Any]] = []
    for folder, label in _TRACKS:
        d = memory / folder
        if not d.is_dir():
            continue
        files = sorted(d.glob("*.md"))
        entries = 0
        latest: str | None = None
        for f in files:
            ids = _ENTRY.findall(f.read_text(encoding="utf-8", errors="replace"))
            entries += len(ids)
            if ids:
                latest = ids[-1]
        objects.append(
            control_object(
                f"track-{folder}",
                "memory_track",
                f"{label} track",
                "pass" if entries else "warn",
                f"{entries} entries across {len(files)} daily files" + (f"; latest {latest}" if latest else ""),
                source(api="/api/brain", path=d),
                {"track": folder, "entries": entries, "files": len(files), "latest": latest,
                 "command": f"python3 .agent/tools/track.py list {folder[:-1] if folder != 'cases' else 'case'}"},
            )
        )
    return objects
