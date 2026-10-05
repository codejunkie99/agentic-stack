#!/usr/bin/env python3
"""Agent-facing model recommendation tool.

Use this when an agent is deciding how to delegate a subtask. It is read-only:
it never changes the active session, runner, permissions, or user settings.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _core_router():
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from harness_manager.workspaces.model_router import recommend
        return recommend
    except ImportError:
        return None


def _live_catalog():
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from harness_manager.workspaces.agent_profiles import AgentProfiles
        return AgentProfiles(None, None, None).models().get("models", [])
    except (ImportError, OSError, ValueError, TypeError, AttributeError):
        return []


def _fallback(runner, task, policy, choices, attachments):
    deep = bool(re.search(r"\b(?:architect|audit|debug|investigate|migrat|refactor|research|security|multi[- ]step|production|entire app)\b", task, re.I)) or len(task) > 900
    fast = not deep and bool(re.search(r"\b(?:quick|brief|short|rename|format|typo|find|locate|list)\b", task, re.I))
    if policy == "auto:cost":
        target = "fast"
    elif policy == "auto:intelligence":
        target = "deep"
    else:
        target = "deep" if deep else "fast" if fast else "balanced"
    if not choices:
        defaults = ([('gpt-5.6-luna', 'fast'), ('gpt-5.6-terra', 'balanced'), ('gpt-5.6-sol', 'deep'), ('gpt-6-astra', 'deep')]
                    if runner == 'codex' else [('haiku', 'fast'), ('sonnet', 'balanced'), ('opus', 'deep'), ('fable', 'deep')])
        choices = [{'id': model, 'runner': runner, 'tier': tier, 'efforts': []} for model, tier in defaults]
    choices = [row for row in choices if isinstance(row, dict) and row.get('runner', runner) == runner]
    chosen = next((row for row in choices if row.get('tier') == target), choices[0] if choices else {})
    return {'policy': policy, 'model': chosen.get('id', ''), 'effort': '', 'complexity': target,
            'reason': 'Portable fallback matched the requested optimization mode.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recommend a model for an agent subtask without changing the current session.")
    parser.add_argument("task", help="The bounded subtask to classify")
    parser.add_argument("--runner", choices=["codex", "claude-code"], default="codex")
    parser.add_argument("--policy", choices=["auto:cost", "auto:balanced", "auto:intelligence"], default="auto:balanced")
    parser.add_argument("--catalog", type=Path, help="Optional JSON file containing a models array")
    parser.add_argument("--attachment-kind", action="append", default=[], choices=["image", "pdf", "audio", "video", "text", "file"])
    args = parser.parse_args(argv)
    choices = []
    if args.catalog:
        if args.catalog.stat().st_size > 8_000_000:
            parser.error("catalog is too large")
        value = json.loads(args.catalog.read_text())
        choices = value.get("models", []) if isinstance(value, dict) else value
        if not isinstance(choices, list):
            parser.error("catalog must contain a models array")
    else:
        choices = _live_catalog()
    attachments = [{"kind": value} for value in args.attachment_kind]
    router = _core_router()
    result = (router(args.runner, args.task, args.policy, choices, attachments)
              if router else _fallback(args.runner, args.task, args.policy, choices, attachments))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
