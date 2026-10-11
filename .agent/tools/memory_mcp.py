#!/usr/bin/env python3
"""Stdio MCP server exposing the portable brain to any MCP host. Stdlib only.

Stable tool names (see docs/contracts.md):

    mem_context   {query}                      → markdown, splice into context as-is
    mem_search    {query, topK?}               → markdown list of hits
    mem_save_turn {messages[] | role+content, sessionKey?, flush?} → JSON save status
    mem_save_fact {fact | messages[]}          → JSON save status

Read-only resources for hosts that expose `resources/read` but not tools:

    mem://profile                              → same text as mem_context
    mem://search?q={query}&topK={topK}         → same text as mem_search

stdout carries protocol frames only; logs go to stderr. Tool failures come
back as MCP tool errors (`isError: true`); resource failures are JSON-RPC
errors so hosts can tell them from markdown content.

Register once per host, e.g.:

    claude mcp add agentic-memory -- python3 /path/.agent/tools/memory_mcp.py
    # cursor ~/.cursor/mcp.json / codex ~/.codex/config.toml: same command
"""
import json
import os
import re
import sys
import urllib.parse

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracks  # noqa: E402
from _cli import redact  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
PROFILE_MD = os.path.join(BASE, "memory", "personal", "PROFILE.md")
PREFERENCES_MD = os.path.join(BASE, "memory", "personal", "PREFERENCES.md")
TOP_K_DEFAULT = 5
TOP_K_MAX = 50


def _log(msg):
    sys.stderr.write(f"[memory_mcp] {msg}\n")
    sys.stderr.flush()


def _recall_lessons(query, k):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("recall", os.path.join(BASE, "tools", "recall.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.recall(query, top_k=k)
        rows = result[0] if isinstance(result, tuple) else result
        return [r for r in (rows or []) if isinstance(r, dict)]
    except Exception as e:  # recall is optional context; never fail the tool
        _log(f"recall unavailable: {e}")
        return []


def _top_k(value):
    try:
        k = int(value)
    except (TypeError, ValueError):
        return TOP_K_DEFAULT
    if k <= 0:
        return TOP_K_DEFAULT
    return min(k, TOP_K_MAX)


def mem_search(query, top_k=TOP_K_DEFAULT, root=None):
    if not query or not str(query).strip():
        raise ValueError("query must be a non-empty string")
    k = _top_k(top_k)
    lines = []
    eps = tracks.search("episode", query, k=k, root=root)
    cases = tracks.search("case", query, k=k, root=root)
    lessons = _recall_lessons(query, k) if root is None else []
    if lessons:
        lines.append("## Lessons")
        for r in lessons:
            lines.append(f"- {r.get('claim') or r.get('text') or json.dumps(r)[:200]}")
    if eps:
        lines.append("## Episodes")
        for e in eps:
            lines.append(f"- ({e['score']:.2f}) [{e['id']}] {e['body'].splitlines()[0][:200]}")
    if cases:
        lines.append("## Agent cases")
        for e in cases:
            lines.append(f"- ({e['score']:.2f}) [{e['id']}] {e['body'].replace(chr(10), ' / ')[:200]}")
    return redact("\n".join(lines) if lines else "_no memory matched_")


def _read(path, limit=4000):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()[:limit]
    except OSError:
        return ""


def mem_context(query, root=None):
    parts = []
    profile = _read(PROFILE_MD if root is None else os.path.join(root, "personal", "PROFILE.md"))
    prefs = _read(PREFERENCES_MD if root is None else os.path.join(root, "personal", "PREFERENCES.md"), 2000)
    if prefs:
        parts.append("## Preferences\n" + prefs.strip())
    if profile:
        parts.append("## Profile\n" + profile.strip())
    fs = tracks.active_foresights(root=root)
    if fs:
        parts.append("## Foresight (currently valid)\n" + "\n".join(f"- {e['body'].splitlines()[0][:200]}" for e in fs[-5:]))
    if query and str(query).strip():
        parts.append(mem_search(query, TOP_K_DEFAULT, root=root))
    return redact("\n\n".join(parts) if parts else "_no profile yet_")


def _texts(messages):
    out = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content") or m.get("text") or ""
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        if role in ("user", "assistant") and str(content).strip():
            out.append((role, str(content).strip()))
    return out


def mem_save_turn(args, root=None):
    messages = args.get("messages")
    if not messages:
        if not args.get("role"):
            raise ValueError("messages[] or role+content required")
        messages = [{"role": args["role"], "content": args.get("content") or args.get("text") or ""}]
    turns = _texts(messages)
    if not turns:
        raise ValueError("no user/assistant text in messages")
    tool_calls = sum(len(m.get("toolCalls") or []) for m in messages if isinstance(m, dict))
    body = "\n".join(f"**{r.capitalize()}:** {redact(t)[:2000]}" for r, t in turns)
    e = tracks.append_entry("episode", body, {
        "session_id": args.get("sessionKey") or "default",
        "source": "mcp",
        "tool_calls": tool_calls,
        "flushed": bool(args.get("flush", True)),
    }, root=root)
    return {"saved": True, "id": e["id"], "kind": "episode", "turns": len(turns)}


def mem_save_fact(args, root=None):
    fact = args.get("fact")
    if not fact:
        msgs = args.get("messages") or []
        if any(isinstance(m, dict) and m.get("role") not in ("user", "assistant") for m in msgs):
            raise ValueError("mem_save_fact accepts only user/assistant roles")
        fact = " ".join(t for _, t in _texts(msgs))
    fact = redact(str(fact).strip())
    if not fact:
        raise ValueError("fact must be a non-empty string")
    path = PROFILE_MD if root is None else os.path.join(root, "personal", "PROFILE.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = _read(path, limit=10**7)
    if not existing:
        existing = "# Profile\n\nDurable facts about the user, saved by agents. Edit freely.\n\n## Facts\n"
    if "## Facts" not in existing:
        existing = existing.rstrip("\n") + "\n\n## Facts\n"
    line = f"- {fact}"
    if line in existing.splitlines():
        return {"saved": False, "duplicate": True, "path": path}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(existing.rstrip("\n") + "\n" + line + "\n")
    os.replace(tmp, path)
    return {"saved": True, "extracted": False, "path": path}


TOOLS = [
    {"name": "mem_context", "description": "User profile, preferences, valid foresight and memory relevant to a query. Returns markdown.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "mem_search", "description": "Search episodes, agent cases and lessons. Returns markdown.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "topK": {"type": "integer"}}, "required": ["query"]}},
    {"name": "mem_save_turn", "description": "Record a conversation turn (user/assistant messages, tool round trips preserved by count) as an episode.",
     "inputSchema": {"type": "object", "properties": {"messages": {"type": "array"}, "role": {"type": "string"},
                                                     "content": {"type": "string"}, "text": {"type": "string"},
                                                     "sessionKey": {"type": "string"}, "flush": {"type": "boolean"}}}},
    {"name": "mem_save_fact", "description": "Record a durable user fact (preference, habit, decision) to the profile. Not for trajectories.",
     "inputSchema": {"type": "object", "properties": {"fact": {"type": "string"}, "messages": {"type": "array"}}}},
]

RESOURCES = [
    {"uri": "mem://profile", "name": "User profile and context", "mimeType": "text/markdown"},
]
RESOURCE_TEMPLATES = [
    {"uriTemplate": "mem://search?q={query}&topK={topK}", "name": "Semantic-ish memory search", "mimeType": "text/markdown"},
]


def call_tool(name, args, root=None):
    args = args or {}
    if name == "mem_context":
        return mem_context(args.get("query", ""), root=root)
    if name == "mem_search":
        return mem_search(args.get("query", ""), args.get("topK", TOP_K_DEFAULT), root=root)
    if name == "mem_save_turn":
        return json.dumps(mem_save_turn(args, root=root))
    if name == "mem_save_fact":
        return json.dumps(mem_save_fact(args, root=root))
    raise KeyError(f"unknown tool: {name}")


def read_resource(uri, root=None):
    if uri == "mem://profile":
        return mem_context("", root=root)
    m = re.match(r"^mem://search\?(.*)$", uri)
    if m:
        qs = urllib.parse.parse_qs(m.group(1))
        q = (qs.get("q") or qs.get("query") or [""])[0]
        k = (qs.get("topK") or qs.get("top_k") or [TOP_K_DEFAULT])[0]
        if not q.strip():
            raise ValueError("empty query")
        return mem_search(q, k, root=root)
    raise KeyError(f"unknown resource: {uri}")


def handle(req, root=None):
    """Return a JSON-RPC response dict, or None for notifications."""
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}
    if rid is None:
        return None  # notification (e.g. notifications/initialized)

    def ok(result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                   "capabilities": {"tools": {}, "resources": {}},
                   "serverInfo": {"name": "agentic-stack-memory", "version": "1.0.0"}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        try:
            text = call_tool(params.get("name"), params.get("arguments"), root=root)
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:
            return ok({"content": [{"type": "text", "text": redact(str(e))}], "isError": True})
    if method == "resources/list":
        return ok({"resources": RESOURCES})
    if method == "resources/templates/list":
        return ok({"resourceTemplates": RESOURCE_TEMPLATES})
    if method == "resources/read":
        uri = params.get("uri", "")
        try:
            text = read_resource(uri, root=root)
        except KeyError as e:
            return err(-32002, str(e.args[0] if e.args else e))
        except Exception as e:
            return err(-32603, redact(str(e)))
        return ok({"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]})
    return err(-32601, f"method not found: {method}")


def serve(stdin=None, stdout=None, root=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                     "error": {"code": -32700, "message": "parse error"}}) + "\n")
            stdout.flush()
            continue
        resp = handle(req, root=root)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()


if __name__ == "__main__":
    try:
        serve()
    except Exception as e:  # boot failure → stderr, exit 1
        _log(f"fatal: {e}")
        sys.exit(1)
