#!/usr/bin/env python3
"""PostToolUse hook for GitHub Copilot CLI.

Copilot CLI calls this script after every postToolUse hook event, passing a
JSON payload via stdin:

    {
      "timestamp": 1704614700000,
      "cwd": "/path/to/project",
      "toolName": "bash",
      "toolArgs": "{\"command\":\"npm test\"}",
      "toolResult": {
        "resultType": "success",
        "textResultForLlm": "All tests passed (15/15)"
      }
    }

This normalizes Copilot CLI's camelCase format to the canonical
tool_name/tool_input/tool_response shape used by the rest of the harness,
then delegates to the shared importance scoring and episodic logging.

Configured via .github/hooks/agentic-stack.json (installed by the
copilot-cli adapter).
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


_COPILOT_TO_CANONICAL = {
    "bash": "Bash",
    "edit": "Edit",
    "view": "Read",
    "create": "Write",
    "write": "Write",
    "multiedit": "MultiEdit",
    "multi_edit": "MultiEdit",
    "grep": "Grep",
    "find": "Find",
    "ls": "LS",
    "task": "Task",
    "todowrite": "TodoWrite",
    "todo_write": "TodoWrite",
    "webfetch": "WebFetch",
    "web_fetch": "WebFetch",
    "search": "Grep",
}


def _tool_name(name: str) -> str:
    if not isinstance(name, str):
        return "Unknown"
    lowered = name.strip().lower()
    return _COPILOT_TO_CANONICAL.get(
        lowered,
        name[:1].upper() + name[1:] if name else "Unknown",
    )


def _parse_tool_args(args_raw) -> dict:
    """toolArgs is a JSON string in Copilot CLI's format."""
    if isinstance(args_raw, dict):
        return args_raw
    if not isinstance(args_raw, str) or not args_raw.strip():
        return {}
    try:
        parsed = json.loads(args_raw)
        return parsed if isinstance(parsed, dict) else {"raw": str(parsed)}
    except json.JSONDecodeError:
        return {"command": args_raw}


def _build_response(payload: dict) -> dict:
    """Map toolResult to the canonical response shape cc.* helpers expect."""
    result = payload.get("toolResult") or {}
    if not isinstance(result, dict):
        return {}
    result_type = result.get("resultType", "success")
    text = result.get("textResultForLlm", "")
    is_error = result_type in ("failure", "denied")
    resp: dict = {
        "is_error": is_error,
        "output": str(text)[:500] if text else "",
    }
    if is_error:
        resp["error"] = str(text)[:300]
    if result_type == "denied":
        resp["stderr"] = "tool use denied by hook"
    return resp


def _emit_malformed(reason: str, raw_excerpt: str) -> None:
    excerpt = raw_excerpt[:200] if isinstance(raw_excerpt, str) else ""
    on_failure(
        skill_name="copilot-cli",
        action="hook:malformed_payload",
        error=f"copilot-cli postToolUse payload malformed: {reason}",
        context=excerpt,
        confidence=0.95,
        importance=5,
        pain_score=2,
    )


def main() -> None:
    raw = ""
    try:
        raw = sys.stdin.read()
    except OSError as e:
        _emit_malformed(f"stdin read failed: {e}", "")
        return

    if not raw or not raw.strip():
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        _emit_malformed(f"json decode error: {e.msg}", raw)
        return

    if not isinstance(payload, dict):
        _emit_malformed(f"payload is {type(payload).__name__}, expected object", raw)
        return

    raw_tool_name = payload.get("toolName")
    if not raw_tool_name:
        return

    tool_name = _tool_name(raw_tool_name)
    tool_input = _parse_tool_args(payload.get("toolArgs"))
    tool_response = _build_response(payload)

    success = cc._is_success(tool_name, tool_input, tool_response)
    importance = cc._importance(tool_name, json.dumps(tool_input))
    action = cc._action_label(tool_name, tool_input)
    reflection = cc._reflection(tool_name, tool_input, tool_response, success)
    detail = cc._detail(tool_name, tool_input, tool_response, success)
    pscore = cc._pain_score(importance, success)

    if success:
        log_execution(
            skill_name="copilot-cli",
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
            skill_name="copilot-cli",
            action=action,
            error=reflection,
            context=detail,
            confidence=0.7,
            importance=importance,
            pain_score=pscore,
        )


if __name__ == "__main__":
    main()
