"""Runs before every tool call. Enforces permissions and tool schemas."""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _schema(tool_name):
    p = os.path.join(ROOT, "protocols/tool_schemas", f"{tool_name}.schema.json")
    if not os.path.exists(p):
        return {}
    return json.load(open(p))


def _perms_text():
    p = os.path.join(ROOT, "protocols/permissions.md")
    return open(p).read() if os.path.exists(p) else ""


def _match_any(patterns, text):
    """Returns the first pattern that matches text via re.search, or None.
    Skips (with warning to stderr) any regex that fails to compile so a single
    bad schema entry doesn't take down the hook."""
    for pat in patterns or []:
        try:
            if re.search(pat, text):
                return pat
        except re.error as e:
            print(f"pre_tool_call: skipping invalid regex {pat!r}: {e}", file=sys.stderr)
            continue
    return None


def check_tool_call(tool_name, operation, args):
    """Returns (allowed, reason). allowed may be True, False, or 'approval_needed'."""
    schema = _schema(tool_name)
    op = schema.get("operations", {}).get(operation, {})

    blocked = op.get("blocked_targets", [])
    target = args.get("branch") or args.get("target") or args.get("env") or ""
    if target and target in blocked:
        return False, f"BLOCKED: {operation} to '{target}' is forbidden"

    command = args.get("command") or ""
    if isinstance(command, str) and command:
        hit = _match_any(op.get("blocked_patterns", []), command)
        if hit:
            return False, f"BLOCKED: command matches forbidden pattern '{hit}'"
        hit = _match_any(op.get("requires_approval_patterns", []), command)
        if hit:
            return "approval_needed", f"command matches pattern '{hit}'; requires human approval"

    if op.get("requires_approval", False):
        return "approval_needed", f"{operation} requires human approval"

    perms = _perms_text()
    if "## Never allowed" in perms:
        never = perms.split("## Never allowed")[1].split("##")[0]
        desc = f"{tool_name} {operation} {json.dumps(args)}".lower()
        for line in never.strip().splitlines():
            if not line.startswith("- "):
                continue
            rule = line[2:].lower()
            keywords = [w for w in rule.split() if len(w) > 3]
            if keywords and sum(1 for k in keywords if k in desc) >= 2:
                return False, f"BLOCKED by permission rule: {line[2:]}"

    return True, "allowed"
