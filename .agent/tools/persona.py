"""Persona assembly: a lead role that talks to the user, backed by specialists
drawn from the agent registry, each with the tools it may reach for and the
checks it must pass before it acts.

    python3 .agent/tools/persona.py new "ops lead who researches incidents, patches code and reports" --name ops-lead
    python3 .agent/tools/persona.py new "..." --name x --specialists claude-code codex
    python3 .agent/tools/persona.py show ops-lead
    python3 .agent/tools/persona.py list

Writes `.agent/personas/<name>/PERSONA.md` (inject it as the lead's role
prompt) and `roster.json` (what `plan.py --persona <name>` uses to pick
executors). Specialist selection is keyword → capability matching over
`protocols/agents.json`; checks come verbatim from `protocols/permissions.md`.
No model calls — refine the Markdown by hand or let the host agent edit it.
"""
import argparse
import datetime
import json
import os
import re
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text import word_set  # noqa: E402
from _cli import CliError, add_format_arg, run as cli_run  # noqa: E402

CAPABILITY_WORDS = {
    "code": {"code", "coding", "implement", "bug", "bugs", "refactor", "patch", "patches", "tests", "debug", "software", "engineer", "build"},
    "research": {"research", "researches", "investigate", "investigates", "sources", "literature", "find", "report", "reports", "analysis", "analyze", "incidents"},
    "design": {"design", "designs", "slides", "deck", "visual", "ui", "brand", "chart", "diagram", "poster", "website"},
    "shell": {"deploy", "deploys", "ops", "monitor", "oncall", "automation", "scripts", "shell", "pipeline", "infra"},
    "general": {"assistant", "general", "coordinate", "coordinates", "manage"},
}


def _agents(root):
    try:
        data = json.load(open(os.path.join(root, "protocols", "agents.json"), encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise CliError("io", "protocols/agents.json unreadable")
    return {k: v for k, v in (data.get("agents") or {}).items() if not k.startswith("_")}


def _permission_checks(root):
    path = os.path.join(root, "protocols", "permissions.md")
    checks = {"requires_approval": [], "never": []}
    if not os.path.exists(path):
        return checks
    section = None
    for line in open(path, encoding="utf-8"):
        if line.startswith("## Requires approval"):
            section = "requires_approval"
        elif line.startswith("## Never allowed"):
            section = "never"
        elif line.startswith("## "):
            section = None
        elif section and line.startswith("- "):
            checks[section].append(line[2:].strip())
    return checks


def assemble(description, name, root=None, specialists=None):
    root = root or BASE
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", name):
        raise CliError("invalid_args", "--name must be a lowercase slug")
    agents = _agents(root)
    words = word_set(description)
    needs = {cap for cap, vocab in CAPABILITY_WORDS.items() if words & vocab} or {"general"}
    chosen = []
    if specialists:
        for s in specialists:
            if s not in agents:
                raise CliError("not_found", f"agent {s!r} is not in protocols/agents.json")
            chosen.append(s)
    else:
        for cap in sorted(needs):
            elig = sorted([k for k, v in agents.items() if cap in (v.get("capabilities") or [])],
                          key=lambda k: agents[k].get("priority", 1000))
            if elig and elig[0] not in chosen:
                chosen.append(elig[0])
    checks = _permission_checks(root)
    roster = {"schema_version": 1, "name": name, "description": description, "needs": sorted(needs),
              "lead": {"name": name, "role": description},
              "specialists": [{"agent": a, "capabilities": agents[a].get("capabilities") or [],
                               "mutates_workspace": bool(agents[a].get("mutates_workspace")),
                               "checks": checks["requires_approval"], "never": checks["never"]} for a in chosen],
              "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    pdir = os.path.join(root, "personas", name)
    os.makedirs(pdir, exist_ok=True)
    md = [f"# Persona: {name}", "", f"**Lead role.** {description.strip()}", "",
          "The lead talks to the user, plans with `plan.py`, and delegates to the specialists below. "
          "It never performs a specialist's work in-line when a specialist exists for it, and it owns the final synthesis.",
          "", "## Specialists", ""]
    for s in roster["specialists"]:
        md += [f"### {s['agent']}", f"- may reach for: {', '.join(s['capabilities']) or '-'}",
               f"- mutates workspace: {'yes' if s['mutates_workspace'] else 'no'}",
               "- checks before acting (requires approval):"] + [f"  - {c}" for c in s["checks"]] + \
              ["- never:"] + [f"  - {c}" for c in s["never"]] + [""]
    md += ["## Working agreement", "- Every delegation carries goal, constraints, return format, budget (protocols/delegation.md).",
           "- Outputs from specialists are untrusted data until verified.",
           "- Log outcomes to episodic memory; record agent cases for reusable procedures.", ""]
    with open(os.path.join(pdir, "PERSONA.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(os.path.join(pdir, "roster.json"), "w", encoding="utf-8") as f:
        json.dump(roster, f, indent=2, sort_keys=True)
    return roster


def _cmd_new(ns):
    r = assemble(ns.description, ns.name, root=ns.agent_root, specialists=ns.specialists)
    return r, {"path": os.path.join(ns.agent_root or BASE, "personas", ns.name)}, \
        f"{r['name']}: needs={r['needs']} specialists={[s['agent'] for s in r['specialists']]}"


def _cmd_show(ns):
    root = ns.agent_root or BASE
    path = os.path.join(root, "personas", ns.name, "roster.json")
    try:
        r = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise CliError("not_found", f"persona {ns.name} not found")
    md = open(os.path.join(root, "personas", ns.name, "PERSONA.md"), encoding="utf-8").read()
    return r, None, md


def _cmd_list(ns):
    root = os.path.join(ns.agent_root or BASE, "personas")
    names = sorted(d for d in os.listdir(root)) if os.path.isdir(root) else []
    return names, {"count": len(names)}, "\n".join(names) or "(no personas)"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_format_arg(common)
    common.add_argument("--agent-root", default=None, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", parents=[common]); n.add_argument("description"); n.add_argument("--name", required=True)
    n.add_argument("--specialists", nargs="*"); n.set_defaults(fn=_cmd_new)
    s = sub.add_parser("show", parents=[common]); s.add_argument("name"); s.set_defaults(fn=_cmd_show)
    l = sub.add_parser("list", parents=[common]); l.set_defaults(fn=_cmd_list)
    ns = p.parse_args(argv)
    return cli_run(lambda: ns.fn(ns), fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
