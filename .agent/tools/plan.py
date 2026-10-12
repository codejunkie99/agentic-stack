"""Host-agent CLI for DAG plans (see harness/dag.py for the model).

    python3 .agent/tools/plan.py validate --file plan.json
    python3 .agent/tools/plan.py new --file plan.json [--persona ops-lead]
    python3 .agent/tools/plan.py new --playbook release --goal "ship v1.2"
    python3 .agent/tools/plan.py run <run_id> [--yes]
    python3 .agent/tools/plan.py status <run_id> | list
    python3 .agent/tools/plan.py resolve <run_id> <node> continue --message "..."
    python3 .agent/tools/plan.py resolve <run_id> <node> abandon
    python3 .agent/tools/plan.py resolve <run_id> <node> replan --file successor.json
    python3 .agent/tools/plan.py report <run_id>
    python3 .agent/tools/plan.py playbook save <run_id> --name release
    python3 .agent/tools/plan.py playbook list

`run` without `--yes` stops at `awaiting_approval` when any node's agent
mutates the workspace; that is the approval gate, not an error.
"""
import argparse
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cli import CliError, add_format_arg, run as cli_run  # noqa: E402
import dag  # noqa: E402


def _planner(ns):
    return dag.Planner(ns.agent_root or BASE)


def _load_plan(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise CliError("invalid_args", f"cannot read plan file: {e}")


def _roster(ns):
    if not getattr(ns, "persona", None):
        return None
    path = os.path.join(ns.agent_root or BASE, "personas", ns.persona, "roster.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise CliError("not_found", f"persona {ns.persona} not found", hint="persona.py new '<description>' --name ...")
    return [s["agent"] for s in data.get("specialists") or []]


def _wrap(fn):
    def inner(ns):
        try:
            return fn(ns)
        except dag.PlanError as e:
            raise CliError("invalid_args", str(e))
    return inner


@_wrap
def cmd_validate(ns):
    p = _planner(ns)
    plan = p.validate(_load_plan(ns.file), roster=_roster(ns))
    data = {"valid": True, "name": plan["name"], "order": plan["_order"],
            "assignments": {n["id"]: n["agent"] for n in plan["nodes"]},
            "needs_approval": p.needs_approval(plan)}
    return data, None, "valid: " + " -> ".join(f"{n}({data['assignments'][n]})" for n in plan["_order"])


@_wrap
def cmd_new(ns):
    p = _planner(ns)
    if ns.playbook:
        if not ns.goal:
            raise CliError("invalid_args", "--playbook needs --goal")
        plan = p.instantiate(ns.playbook, ns.goal)
    elif ns.file:
        plan = _load_plan(ns.file)
    else:
        raise CliError("invalid_args", "pass --file plan.json or --playbook NAME --goal ...")
    run = p.new_run(plan, roster=_roster(ns))
    return ({"run_id": run["run_id"], "status": run["status"], "nodes": list(run["nodes"])},
            {"run_dir": p.run_dir(run["run_id"])}, f"{run['run_id']}  {run['status']}")


@_wrap
def cmd_run(ns):
    p = _planner(ns)
    run = p.run(ns.run_id, approved=ns.yes)
    data = {"run_id": run["run_id"], "status": run["status"],
            "nodes": {n: s["status"] for n, s in run["nodes"].items()}}
    text = f"{run['run_id']}  {run['status']}\n" + "\n".join(f"  {n:<24} {s}" for n, s in data["nodes"].items())
    if run["status"] == "awaiting_approval":
        text += "\n  (a node mutates the workspace; re-run with --yes to approve)"
    if run["status"] == "suspended":
        text += "\n  open exception reports: " + ", ".join(e["node"] for e in p.exceptions(run["run_id"]))
    return data, None, text


@_wrap
def cmd_status(ns):
    p = _planner(ns)
    run, plan = p.load(ns.run_id)
    data = {"run_id": run["run_id"], "status": run["status"], "supersedes": run.get("supersedes"),
            "superseded_by": run.get("superseded_by"),
            "nodes": {n: {"status": s["status"], "attempts": s["attempts"], "error": s.get("error")} for n, s in run["nodes"].items()},
            "exceptions": p.exceptions(ns.run_id)}
    text = f"{run['run_id']}  {run['status']}\n" + "\n".join(
        f"  {n:<24} {s['status']:<12} attempts={s['attempts']} {s.get('error') or ''}" for n, s in run["nodes"].items())
    return data, None, text


@_wrap
def cmd_list(ns):
    p = _planner(ns)
    rows = []
    if os.path.isdir(p.plans_dir):
        for d in sorted(os.listdir(p.plans_dir)):
            r = dag._read_json(os.path.join(p.plans_dir, d, "run.json"))
            if r:
                rows.append({"run_id": r["run_id"], "name": r["name"], "status": r["status"], "created_at": r["created_at"]})
    return rows, {"count": len(rows)}, "\n".join(f"{r['run_id']}  {r['status']:<14} {r['name']}" for r in rows) or "(no runs)"


@_wrap
def cmd_resolve(ns):
    p = _planner(ns)
    new_plan = _load_plan(ns.file) if ns.file else None
    result = p.resolve(ns.run_id, ns.node, ns.action, message=ns.message, new_plan=new_plan, roster=_roster(ns))
    if ns.action == "replan":
        return ({"successor": result["run_id"], "supersedes": ns.run_id}, None,
                f"replanned: {ns.run_id} -> {result['run_id']} (run it with `plan.py run {result['run_id']} --yes`)")
    return ({"run_id": ns.run_id, "node": ns.node, "status": result["nodes"][ns.node]["status"], "run_status": result["status"]},
            None, f"{ns.node} -> {result['nodes'][ns.node]['status']}; run {result['status']}")


@_wrap
def cmd_report(ns):
    data, md = _planner(ns).report(ns.run_id)
    return data, None, md


@_wrap
def cmd_playbook(ns):
    p = _planner(ns)
    if ns.pb_cmd == "save":
        path = p.save_playbook(ns.run_id, ns.name)
        return {"name": ns.name, "path": path}, None, f"saved playbook {ns.name} -> {path}"
    names = p.playbooks()
    return names, {"count": len(names)}, "\n".join(names) or "(no playbooks)"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_format_arg(common)
    common.add_argument("--agent-root", default=None, help=argparse.SUPPRESS)
    common.add_argument("--persona", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", parents=[common]); v.add_argument("--file", required=True); v.set_defaults(fn=cmd_validate)
    n = sub.add_parser("new", parents=[common]); n.add_argument("--file"); n.add_argument("--playbook"); n.add_argument("--goal")
    n.set_defaults(fn=cmd_new)
    r = sub.add_parser("run", parents=[common]); r.add_argument("run_id"); r.add_argument("--yes", action="store_true"); r.set_defaults(fn=cmd_run)
    s = sub.add_parser("status", parents=[common]); s.add_argument("run_id"); s.set_defaults(fn=cmd_status)
    l = sub.add_parser("list", parents=[common]); l.set_defaults(fn=cmd_list)
    rs = sub.add_parser("resolve", parents=[common]); rs.add_argument("run_id"); rs.add_argument("node")
    rs.add_argument("action", choices=["continue", "abandon", "replan"]); rs.add_argument("--message"); rs.add_argument("--file")
    rs.set_defaults(fn=cmd_resolve)
    rp = sub.add_parser("report", parents=[common]); rp.add_argument("run_id"); rp.set_defaults(fn=cmd_report)
    pb = sub.add_parser("playbook"); pbs = pb.add_subparsers(dest="pb_cmd", required=True)
    pbsave = pbs.add_parser("save", parents=[common]); pbsave.add_argument("run_id"); pbsave.add_argument("--name", required=True)
    pbsave.set_defaults(fn=cmd_playbook)
    pbl = pbs.add_parser("list", parents=[common]); pbl.set_defaults(fn=cmd_playbook)
    ns = p.parse_args(argv)
    return cli_run(lambda: ns.fn(ns), fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
