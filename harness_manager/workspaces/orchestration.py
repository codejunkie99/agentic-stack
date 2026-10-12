"""Desktop snapshot of the v0.20 runtime: DAG plan runs, proactive campaigns,
the gated evolver, and Markdown memory tracks. Reads project files only."""
from __future__ import annotations

from pathlib import Path

from .. import mission_control_orchestration as orch


def _item(identifier, kind, label, status, summary, source, payload):
    command = payload.get("command", "") if isinstance(payload, dict) else ""
    return {"id": identifier, "kind": kind, "label": label, "status": status,
            "summary": summary, "command": command or "",
            "path": str(source.get("path", ""))}


def _source(*, api=None, path=None, command=None):
    return {"path": path or ""}


def snapshot(root):
    root = Path(root)
    if not (root / ".agent").is_dir():
        return {"plans": [], "campaigns": [], "evolution": [], "tracks": [],
                "evolutionStats": {}, "projectAccessError": "This project has no .agent folder yet. Initialize the stack first."}
    evolution, stats = orch.evolution_objects(root, _item, _source)
    return {
        "plans": orch.plan_run_objects(root, _item, _source),
        "campaigns": orch.campaign_objects(root, _item, _source),
        "evolution": evolution,
        "evolutionStats": {k: int(v) for k, v in stats.items()},
        "tracks": orch.track_objects(root, _item, _source),
        "projectAccessError": "",
    }
