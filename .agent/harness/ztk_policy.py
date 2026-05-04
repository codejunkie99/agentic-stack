"""Host-neutral policy evaluation for ztk tool events."""
import json

from hooks.pre_tool_call import check_tool_call


WRITE_TOOLS = {
    "Edit",
    "Write",
    "MultiEdit",
    "NotebookEdit",
    "apply_patch",
    "edit",
    "write",
    "patch",
    "multiedit",
}


def _decision(value, reason):
    return {"decision": value, "reason": reason}


def _first_path(tool_input):
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if value:
            return str(value)
    return ""


def _mentions_permissions_file(tool_input):
    path = _first_path(tool_input).replace("\\", "/")
    if path == ".agent/protocols/permissions.md" or path.endswith(
        "/.agent/protocols/permissions.md"
    ):
        return True
    command = str(tool_input.get("command", "")).replace("\\", "/")
    return ".agent/protocols/permissions.md" in command


def _normalize_tool_event(event):
    """Return (tool, operation, input) from generic or host-native hook JSON."""
    tool_input = event.get("input")
    if isinstance(tool_input, dict):
        return (
            str(event.get("tool", "")),
            str(event.get("operation", "")),
            tool_input,
        )

    tool_name = str(event.get("tool_name") or event.get("tool") or "")
    raw_input = event.get("tool_input") or {}
    if not isinstance(raw_input, dict):
        raw_input = {"value": raw_input}

    if tool_name in ("Bash", "bash", "shell"):
        return "shell", "run", {"command": str(raw_input.get("command", ""))}

    if tool_name in ("WebFetch", "webfetch"):
        return "api", "http_get", {"url": str(raw_input.get("url", ""))}

    if tool_name in WRITE_TOOLS:
        return "file", "write", raw_input

    return tool_name, str(event.get("operation", "")), raw_input


def evaluate_event(event):
    """Evaluate a pre-tool event and return a normalized ztk decision dict."""
    if event.get("tool") == "invalid" and event.get("operation") == "parse":
        error = event.get("input", {}).get("error", "invalid event")
        return _decision("deny", f"BLOCKED: malformed ztk event: {error}")

    tool, operation, tool_input = _normalize_tool_event(event)

    if tool == "file" and operation == "write":
        if _mentions_permissions_file(tool_input):
            return _decision(
                "deny",
                "BLOCKED: .agent/protocols/permissions.md is human-owned",
            )
        return _decision("allow", "allowed")

    allowed, reason = check_tool_call(tool, operation, tool_input)
    if allowed is True:
        return _decision("allow", reason)
    if allowed == "approval_needed":
        return _decision("ask", reason)
    return _decision("deny", reason)


def claude_output(decision):
    """Convert a normalized ztk decision into Claude Code hook output."""
    if decision["decision"] == "allow":
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision["decision"],
            "permissionDecisionReason": decision["reason"],
        }
    }


def codex_output(decision, event=None):
    """Convert a normalized ztk decision into Codex hook output."""
    event = event or {"hook_event_name": "PreToolUse"}
    hook_event = event.get("hook_event_name", "PreToolUse")
    if decision["decision"] == "allow":
        return {}

    if hook_event == "PermissionRequest":
        if decision["decision"] == "deny":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {
                        "behavior": "deny",
                        "message": decision["reason"],
                    },
                }
            }
        return {
            "systemMessage": decision["reason"],
        }

    reason = decision["reason"]
    if decision["decision"] == "ask":
        reason = f"{reason}; Codex PreToolUse cannot ask safely, so ztk denied it"

    if decision["decision"] == "deny":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def load_event(stream):
    try:
        payload = json.load(stream)
    except json.JSONDecodeError as exc:
        return {"tool": "invalid", "operation": "parse", "input": {"error": str(exc)}}
    if isinstance(payload, dict):
        return payload
    return {"tool": "invalid", "operation": "parse", "input": {"error": "event must be an object"}}
