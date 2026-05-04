#!/usr/bin/env python3
"""Claude Code PreToolUse adapter for the ztk permission checker."""
import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from ztk_policy import claude_output, evaluate_event  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(json.dumps(claude_output({
            "decision": "deny",
            "reason": f"BLOCKED: malformed hook JSON: {exc}",
        })))
        return 0

    if payload.get("hook_event_name") not in (None, "PreToolUse"):
        return 0

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        print(json.dumps(claude_output({
            "decision": "deny",
            "reason": "BLOCKED: tool_input must be an object",
        })))
        return 0

    print(json.dumps(claude_output(evaluate_event(payload))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
