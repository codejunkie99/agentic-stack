"""Runs before every tool call. Enforces permissions and tool schemas."""
import json, os, re
from urllib.parse import urlparse

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _schema(tool_name):
    p = os.path.join(ROOT, "protocols/tool_schemas", f"{tool_name}.schema.json")
    if not os.path.exists(p):
        return {}
    return json.load(open(p))


def _perms_text():
    p = os.path.join(ROOT, "protocols/permissions.md")
    return open(p).read() if os.path.exists(p) else ""


def _arg_text(args):
    return json.dumps(args, sort_keys=True)


def _pattern_to_regex(pattern):
    escaped = re.escape(pattern)
    return escaped.replace(r"\.\*", ".*").replace(r"\*", ".*")


def _matches_pattern(pattern, text):
    if not pattern or not text:
        return False
    return re.search(_pattern_to_regex(pattern), text, re.IGNORECASE) is not None


def _host_allowed(url, allowlist):
    host = urlparse(url).hostname
    if not host:
        return True
    host = host.lower()
    allowed = [d.lower() for d in allowlist]
    return any(host == d or host.endswith("." + d) for d in allowed)


def check_tool_call(tool_name, operation, args):
    """Returns (allowed, reason). allowed may be True, False, or 'approval_needed'."""
    schema = _schema(tool_name)
    op = schema.get("operations", {}).get(operation, {})
    desc = f"{tool_name} {operation} {_arg_text(args)}"

    allowlist = op.get("domain_allowlist", [])
    url = args.get("url") or args.get("uri") or ""
    if allowlist and url and not _host_allowed(url, allowlist):
        return False, f"BLOCKED: {url} is outside the approved domains list"

    for pattern in op.get("blocked_patterns", []):
        if _matches_pattern(pattern, desc):
            return False, f"BLOCKED: pattern '{pattern}' matched {desc}"

    blocked = op.get("blocked_targets", [])
    target = args.get("branch") or args.get("target") or args.get("env") or ""
    if target and target in blocked:
        return False, f"BLOCKED: {operation} to '{target}' is forbidden"

    perms = _perms_text()
    if "## Never allowed" in perms:
        never = perms.split("## Never allowed")[1].split("##")[0]
        lowered = desc.lower()
        for line in never.strip().splitlines():
            if not line.startswith("- "):
                continue
            rule = line[2:].lower()
            keywords = [w for w in rule.split() if len(w) > 3]
            if keywords and sum(1 for k in keywords if k in lowered) >= 2:
                return False, f"BLOCKED by permission rule: {line[2:]}"

    for pattern in op.get("requires_approval_patterns", []):
        if _matches_pattern(pattern, desc):
            return "approval_needed", f"{operation} requires human approval: pattern '{pattern}' matched"

    if op.get("requires_approval", False):
        return "approval_needed", f"{operation} requires human approval"

    return True, "allowed"
