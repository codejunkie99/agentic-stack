"""Host-agent CLI over the Markdown memory tracks (episodes / cases / foresights).

    python3 .agent/tools/track.py add episode "Shipped the billing fix" --session s1
    python3 .agent/tools/track.py add case --intent "fix flaky auth test" \
        --outcome "pinned the clock in conftest" --quality 0.9
    python3 .agent/tools/track.py add foresight "cert expires" --until 2026-12-01
    python3 .agent/tools/track.py list case --limit 5
    python3 .agent/tools/track.py search episode "supabase migration"
    python3 .agent/tools/track.py deprecate episode ep_20261011_00000001 --by ep_20261011_00000004

Speaks the shared CLI contract (`_cli.py`): JSON envelope when piped, prose
on a TTY, stable exit codes, credential redaction on the way out.
"""
import argparse
import datetime
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracks  # noqa: E402
from _cli import CliError, add_format_arg, run  # noqa: E402


def _kv(pairs):
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise CliError("invalid_args", f"--meta expects key=value, got {p!r}")
        k, v = p.split("=", 1)
        out[k] = v
    return out


def _until(value):
    if not value:
        return None
    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError:
        raise CliError("invalid_args", f"--until must be ISO-8601, got {value!r}",
                       hint="example: 2026-12-01 or 2026-12-01T09:00:00+00:00")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()


def _rel(path):
    rel = os.path.relpath(path, BASE)
    return path if rel.startswith("..") else rel


def _brief(e):
    return {"id": e["id"], "date": e["date"], "body": e["body"][:400],
            "meta": e["meta"], "deprecated_by": e.get("deprecated_by"),
            **({"score": e["score"]} if "score" in e else {})}


def cmd_add(ns):
    meta = _kv(ns.meta)
    if ns.session:
        meta["session_id"] = ns.session
    if ns.kind == "case":
        if not (ns.intent and ns.outcome):
            raise CliError("invalid_args", "case needs --intent and --outcome")
        body = f"intent: {ns.intent}\noutcome: {ns.outcome}"
        if ns.quality is not None:
            if not 0.0 <= ns.quality <= 1.0:
                raise CliError("invalid_args", "--quality must be in [0, 1]")
            meta["quality"] = ns.quality
        if ns.skill:
            meta["skill"] = ns.skill
    else:
        if not ns.body:
            raise CliError("invalid_args", f"{ns.kind} needs a body")
        body = ns.body
        if ns.kind == "foresight":
            meta["valid_from"] = _until(ns.frm) or datetime.datetime.now(datetime.timezone.utc).isoformat()
            if ns.until:
                meta["valid_until"] = _until(ns.until)
    e = tracks.append_entry(ns.kind, body, meta, root=ns.root)
    return _brief(e), {"path": _rel(e["path"])}, f"{e['id']}  {_rel(e['path'])}"


def cmd_list(ns):
    rows = tracks.recent(ns.kind, k=ns.limit, root=ns.root, agent_id=ns.agent)
    if ns.kind == "foresight" and ns.active:
        rows = tracks.active_foresights(root=ns.root)[-ns.limit:]
    data = [_brief(e) for e in rows]
    text = "\n".join(f"{e['id']}  {e['body'].splitlines()[0][:100] if e['body'] else ''}" for e in data) or "(empty)"
    return data, {"count": len(data)}, text


def cmd_search(ns):
    rows = tracks.search(ns.kind, ns.query, k=ns.limit, root=ns.root, agent_id=ns.agent)
    data = [_brief(e) for e in rows]
    text = "\n".join(f"{e['score']:.2f}  {e['id']}  {e['body'].splitlines()[0][:90]}" for e in data) or "(no hits)"
    return data, {"count": len(data)}, text


def cmd_deprecate(ns):
    if not tracks.deprecate(ns.kind, ns.entry_id, ns.by, root=ns.root):
        raise CliError("not_found", f"{ns.kind} entry {ns.entry_id} not found")
    return {"id": ns.entry_id, "deprecated_by": ns.by}, None, f"{ns.entry_id} -> {ns.by}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_format_arg(common)
    common.add_argument("--root", default=None, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", parents=[common])
    a.add_argument("kind", choices=sorted(tracks.KINDS))
    a.add_argument("body", nargs="?")
    a.add_argument("--session")
    a.add_argument("--meta", nargs="*", help="extra key=value pairs")
    a.add_argument("--intent")
    a.add_argument("--outcome")
    a.add_argument("--quality", type=float)
    a.add_argument("--skill")
    a.add_argument("--from", dest="frm")
    a.add_argument("--until")
    a.set_defaults(fn=cmd_add)

    l = sub.add_parser("list", parents=[common])
    l.add_argument("kind", choices=sorted(tracks.KINDS))
    l.add_argument("--limit", type=int, default=10)
    l.add_argument("--agent")
    l.add_argument("--active", action="store_true", help="foresight: only currently valid items")
    l.set_defaults(fn=cmd_list)

    s = sub.add_parser("search", parents=[common])
    s.add_argument("kind", choices=sorted(tracks.KINDS))
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--agent")
    s.set_defaults(fn=cmd_search)

    d = sub.add_parser("deprecate", parents=[common])
    d.add_argument("kind", choices=sorted(tracks.KINDS))
    d.add_argument("entry_id")
    d.add_argument("--by", required=True)
    d.set_defaults(fn=cmd_deprecate)

    ns = p.parse_args(argv)
    return run(lambda: ns.fn(ns), fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
