#!/usr/bin/env python3
"""Process Pi Coding Agent tool_result events into episodic memory entries.

Pi exposes a project-local extension system. The adapter installs
`.pi/extensions/memory-hook.ts`, which forwards every `tool_result` event to
this script via stdin. We normalize Pi's event shape into the same
tool_input/tool_response structure used by the Claude Code hook so the
importance scoring, reflection generation, and success classification stay
consistent across harnesses.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

sys.path.insert(0, os.path.join(AGENT_ROOT, "harness"))
sys.path.insert(0, os.path.join(AGENT_ROOT, "tools"))

from hooks.post_execution import log_execution  # noqa: E402
from hooks.on_failure import on_failure        # noqa: E402
import hooks.claude_code_post_tool as cc       # noqa: E402


_PI_TO_CANONICAL = {
    "bash": "Bash",
    "edit": "Edit",
    "write": "Write",
    "read": "Read",
    "grep": "Grep",
    "find": "Find",
    "ls": "LS",
    "task": "Task",
    "todowrite": "TodoWrite",
    "webfetch": "WebFetch",
}


def _tool_name(name: str) -> str:
    if not isinstance(name, str):
        return "Unknown"
    lowered = name.strip().lower()
    return _PI_TO_CANONICAL.get(lowered, name[:1].upper() + name[1:])


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content[:500]
    if not isinstance(content, list):
        return ""
    texts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str) and text:
                texts.append(text)
    return " ".join(texts)[:500]


def _normalize_response(event: dict) -> dict:
    """Map Pi tool_result shape to the Claude hook's response schema."""
    resp: dict = {"is_error": bool(event.get("isError", False))}
    details = event.get("details")
    content = event.get("content")

    if isinstance(details, dict):
        if isinstance(details.get("output"), str):
            resp["output"] = details["output"][:500]
        if isinstance(details.get("stdout"), str):
            resp["stdout"] = details["stdout"][:500]
        if isinstance(details.get("stderr"), str):
            resp["stderr"] = details["stderr"][:300]
        if isinstance(details.get("error"), str):
            resp["error"] = details["error"][:300]
        if isinstance(details.get("text"), str):
            resp["text"] = details["text"][:500]
        if "exitCode" in details:
            resp["exit_code"] = details.get("exitCode")
        if "cancelled" in details:
            resp["interrupted"] = bool(details.get("cancelled"))
        if "truncated" in details:
            resp["truncated"] = bool(details.get("truncated"))
        resp["details"] = details

    text = _extract_text(content)
    if text:
        resp.setdefault("output", text)
        resp["content"] = [{"type": "text", "text": text}]

    if not any(k in resp for k in ("output", "stdout", "text", "content")):
        if isinstance(details, str):
            resp["output"] = details[:500]
        elif details is not None:
            resp["output"] = json.dumps(details, default=str)[:500]

    return resp


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        payload = {}

    tool_name = _tool_name(payload.get("tool_name") or "Unknown")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {"raw": str(tool_input)}
    tool_response = _normalize_response(payload)

    success = cc._is_success(tool_name, tool_input, tool_response)
    importance = cc._importance(tool_name, json.dumps(tool_input))
    action = cc._action_label(tool_name, tool_input)
    reflection = cc._reflection(tool_name, tool_input, tool_response, success)
    detail = cc._detail(tool_name, tool_input, tool_response, success)

    pscore = cc._pain_score(importance, success)
    if success:
        log_execution(
            skill_name="pi",
            action=action,
            result=detail,
            success=True,
            reflection=reflection,
            importance=importance,
            confidence=0.7,
            pain_score=pscore,
        )
    else:
        on_failure(
            skill_name="pi",
            action=action,
            error=reflection,
            context=detail,
            confidence=0.7,
            importance=importance,
            pain_score=pscore,
        )


if __name__ == "__main__":
    main()
