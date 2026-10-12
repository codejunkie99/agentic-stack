"""Proactivity: campaigns, wake-ups, a model-free monitor, and a report gate.

A campaign is a persistent record of a target, how to measure it, what the
agent may do, and a budget. The agent submits a round, registers a wake-up,
and waits without model calls; `tick` (cron it every minute) measures,
wakes due campaigns, runs the configured `on_wake` command within budget,
and wakes early when a measurement matches `done_regex` / `diverge_regex`.
Every decision must cite a recent measurement; a campaign closes only with a
report that has a baseline and makes no claim the recorded state contradicts.

    python3 .agent/tools/proactive.py new --target "val_bpb < 1.04" \
        --measure "python3 scripts/measure.py" --on-wake "agentic-stack loop run train 'next round' . --yes" \
        --max-rounds 7 --max-runtime-seconds 7200 --allowed resubmit,wait
    python3 .agent/tools/proactive.py wake <id> --in 1800
    python3 .agent/tools/proactive.py tick            # * * * * * in crontab
    python3 .agent/tools/proactive.py measure <id>
    python3 .agent/tools/proactive.py decide <id> resubmit --cite <measurement_id>
    python3 .agent/tools/proactive.py close <id> --report report.md
    python3 .agent/tools/proactive.py status [<id>] | list

State is an append-only event log (`.agent/proactive/campaigns.jsonl`) folded
on read, so nothing here can lose history.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cli import CliError, add_format_arg, run as cli_run, redact  # noqa: E402
from dag import run_bounded, expand  # noqa: E402

MEASUREMENT_TTL_SECONDS = 3600
MONITOR_EVERY_SECONDS = 60
OUTPUT_HEAD = 2000


def _now(now=None):
    if now is None:
        return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(now, str):
        now = datetime.datetime.fromisoformat(now)
    return now if now.tzinfo else now.replace(tzinfo=datetime.timezone.utc)


def _iso(dt):
    return dt.isoformat()


class Proactive:
    def __init__(self, agent_root=None):
        self.root = os.path.abspath(agent_root or BASE)
        self.log = os.path.join(self.root, "proactive", "campaigns.jsonl")
        self.project = os.path.dirname(self.root)

    def _append(self, row):
        os.makedirs(os.path.dirname(self.log), exist_ok=True)
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def _events(self):
        rows = []
        if os.path.exists(self.log):
            for line in open(self.log, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows

    def campaigns(self):
        state = {}
        for e in self._events():
            cid = e.get("campaign_id")
            if e["type"] == "campaign":
                state[cid] = dict(e, status="open", wakes=[], measurements=[], rounds=[], decisions=[],
                                  runtime_seconds=0.0, closed_report=None)
                continue
            c = state.get(cid)
            if not c:
                continue
            if e["type"] == "wake":
                c["wakes"].append(e)
            elif e["type"] == "measurement":
                c["measurements"].append(e)
            elif e["type"] == "round":
                c["rounds"].append(e)
                c["runtime_seconds"] += float(e.get("duration_seconds") or 0.0)
                c["wakes"] = [w for w in c["wakes"] if w["id"] != e.get("wake_id")]
            elif e["type"] == "decision":
                c["decisions"].append(e)
            elif e["type"] == "close":
                c["status"] = "closed"
                c["closed_report"] = e.get("report")
        return state

    def get(self, cid):
        c = self.campaigns().get(cid)
        if not c:
            raise CliError("not_found", f"campaign {cid} not found")
        return c

    # --- lifecycle -----------------------------------------------------------------
    def new(self, target, measure, on_wake=None, allowed=None, max_rounds=5, max_runtime_seconds=3600,
            done_regex=None, diverge_regex=None, monitor_every_seconds=MONITOR_EVERY_SECONDS, now=None):
        if not target or not measure:
            raise CliError("invalid_args", "--target and --measure are required")
        now = _now(now)
        cid = "cmp_" + hashlib.sha1(f"{target}|{_iso(now)}".encode()).hexdigest()[:8]
        return self._append({"type": "campaign", "campaign_id": cid, "target": target,
                             "measure": shlex.split(measure) if isinstance(measure, str) else list(measure),
                             "on_wake": (shlex.split(on_wake) if isinstance(on_wake, str) else list(on_wake)) if on_wake else None,
                             "allowed_actions": sorted(set(allowed or ["wait", "resubmit", "terminate"])),
                             "budget": {"max_rounds": int(max_rounds), "max_runtime_seconds": int(max_runtime_seconds)},
                             "done_regex": done_regex, "diverge_regex": diverge_regex,
                             "monitor_every_seconds": int(monitor_every_seconds), "created_at": _iso(now)})

    def wake(self, cid, at=None, in_seconds=None, reason="scheduled", now=None):
        c = self.get(cid)
        if c["status"] != "open":
            raise CliError("conflict", f"campaign {cid} is closed")
        now = _now(now)
        when = _now(at) if at else now + datetime.timedelta(seconds=int(in_seconds or 0))
        wid = "wk_" + hashlib.sha1(f"{cid}|{_iso(when)}|{len(c['wakes'])}".encode()).hexdigest()[:8]
        return self._append({"type": "wake", "campaign_id": cid, "id": wid, "at": _iso(when), "reason": reason,
                             "created_at": _iso(now)})

    def measure(self, cid, now=None):
        c = self.get(cid)
        now = _now(now)
        r = run_bounded(list(c["measure"]), "", self.project, 300, 20000,
                        env={"CAMPAIGN_ID": cid, "CAMPAIGN_TARGET": c["target"]})
        mid = "ms_" + hashlib.sha1(f"{cid}|{_iso(now)}|{len(c['measurements'])}".encode()).hexdigest()[:8]
        return self._append({"type": "measurement", "campaign_id": cid, "id": mid, "at": _iso(now),
                             "exit_code": r["exit_code"], "output": redact((r["stdout"] or "")[:OUTPUT_HEAD]),
                             "stderr_tail": redact((r["stderr"] or "")[-300:]), "timed_out": r["timed_out"]})

    def _remaining(self, c):
        return {"rounds": max(0, c["budget"]["max_rounds"] - len(c["rounds"])),
                "seconds": max(0.0, c["budget"]["max_runtime_seconds"] - c["runtime_seconds"])}

    def _run_round(self, c, wake_id, measurement, now):
        rem = self._remaining(c)
        if rem["rounds"] <= 0 or rem["seconds"] <= 0:
            return self._append({"type": "round", "campaign_id": c["campaign_id"], "wake_id": wake_id,
                                 "skipped": "budget_exhausted", "at": _iso(now), "duration_seconds": 0.0})
        if not c.get("on_wake"):
            return self._append({"type": "round", "campaign_id": c["campaign_id"], "wake_id": wake_id,
                                 "skipped": "no_on_wake", "at": _iso(now), "duration_seconds": 0.0})
        cmd = expand(list(c["on_wake"]), {"campaign_id": c["campaign_id"], "measurement_id": measurement["id"] if measurement else ""})
        r = run_bounded(cmd, "", self.project, int(min(rem["seconds"], 86400)), 200000,
                        env={"CAMPAIGN_ID": c["campaign_id"], "CAMPAIGN_REMAINING_ROUNDS": str(rem["rounds"]),
                             "CAMPAIGN_REMAINING_SECONDS": str(int(rem["seconds"])),
                             "CAMPAIGN_MEASUREMENT_ID": measurement["id"] if measurement else ""})
        return self._append({"type": "round", "campaign_id": c["campaign_id"], "wake_id": wake_id, "at": _iso(now),
                             "exit_code": r["exit_code"], "duration_seconds": r["duration_seconds"],
                             "timed_out": r["timed_out"], "output": redact((r["stdout"] or "")[:OUTPUT_HEAD])})

    def tick(self, now=None):
        now = _now(now)
        fired = []
        for cid, c in self.campaigns().items():
            if c["status"] != "open":
                continue
            last = c["measurements"][-1] if c["measurements"] else None
            due = [w for w in c["wakes"] if _now(w["at"]) <= now]
            stale = not last or (now - _now(last["at"])).total_seconds() >= c.get("monitor_every_seconds", MONITOR_EVERY_SECONDS)
            measurement = last
            early = None
            if stale or due:
                measurement = self.measure(cid, now=now)
                out = measurement.get("output") or ""
                if c.get("done_regex") and re.search(c["done_regex"], out):
                    early = "done"
                elif c.get("diverge_regex") and re.search(c["diverge_regex"], out):
                    early = "diverged"
            if early and not due:
                w = self.wake(cid, at=_iso(now), reason=early, now=now)
                due = [w]
            for w in due:
                rnd = self._run_round(c, w["id"], measurement, now)
                c = self.get(cid)
                fired.append({"campaign_id": cid, "wake_id": w["id"], "reason": w.get("reason"),
                              "measurement_id": measurement["id"] if measurement else None,
                              "round": {k: rnd.get(k) for k in ("exit_code", "skipped", "duration_seconds")}})
        return fired

    def decide(self, cid, action, cite, now=None):
        c = self.get(cid)
        now = _now(now)
        if c["status"] != "open":
            raise CliError("conflict", f"campaign {cid} is closed")
        if action not in c["allowed_actions"]:
            raise CliError("permission", f"action {action!r} not in allowed_actions {c['allowed_actions']}")
        m = next((m for m in c["measurements"] if m["id"] == cite), None)
        if not m:
            raise CliError("invalid_args", f"--cite must name a measurement of this campaign (got {cite!r})",
                           hint="run `proactive.py measure <id>` and cite its id")
        if (now - _now(m["at"])).total_seconds() > MEASUREMENT_TTL_SECONDS:
            raise CliError("invalid_args", f"measurement {cite} is older than {MEASUREMENT_TTL_SECONDS}s; measure again")
        row = {"type": "decision", "campaign_id": cid, "action": action, "cites": cite, "at": _iso(now)}
        if action == "resubmit":
            rem = self._remaining(c)
            if rem["rounds"] <= 0 or rem["seconds"] <= 0:
                raise CliError("permission", "budget exhausted; terminate or close the campaign")
            row["clamped_to"] = rem
            self._append(row)
            return self.wake(cid, at=_iso(now), reason="resubmit", now=now)
        return self._append(row)

    def close(self, cid, report_path, now=None):
        c = self.get(cid)
        now = _now(now)
        if c["status"] != "open":
            raise CliError("conflict", f"campaign {cid} already closed")
        try:
            report = open(report_path, encoding="utf-8").read()
        except OSError as e:
            raise CliError("io", f"cannot read report: {e}")
        low = report.lower()
        if not re.search(r"(?m)^(#+\s*baseline\b|baseline\s*:)", low):
            raise CliError("invalid_args", "report must include a baseline ('## Baseline' heading or 'Baseline:' line)")
        if not c["measurements"]:
            raise CliError("invalid_args", "no measurement recorded; a report cannot make claims without one")
        last = c["measurements"][-1]
        claims_success = bool(re.search(r"(?m)^(status|result):\s*(success|achieved|met)\b", low))
        if claims_success and last.get("exit_code") != 0:
            raise CliError("conflict", f"report claims success but the latest measurement ({last['id']}) exited "
                                       f"{last.get('exit_code')}", hint="fix the claim or measure again")
        if c.get("done_regex") and claims_success and not re.search(c["done_regex"], last.get("output") or ""):
            raise CliError("conflict", "report claims success but the latest measurement does not match done_regex")
        return self._append({"type": "close", "campaign_id": cid, "report": os.path.abspath(report_path),
                             "last_measurement": last["id"], "at": _iso(now)})


# --- CLI ------------------------------------------------------------------------------

def _p(ns):
    return Proactive(ns.agent_root)


def _brief(c):
    rem = {"rounds": max(0, c["budget"]["max_rounds"] - len(c["rounds"])),
           "seconds": max(0.0, c["budget"]["max_runtime_seconds"] - c["runtime_seconds"])}
    return {"campaign_id": c["campaign_id"], "status": c["status"], "target": c["target"],
            "pending_wakes": [{"id": w["id"], "at": w["at"], "reason": w.get("reason")} for w in c["wakes"]],
            "measurements": len(c["measurements"]), "last_measurement": c["measurements"][-1] if c["measurements"] else None,
            "rounds": len(c["rounds"]), "remaining": rem, "decisions": c["decisions"][-3:]}


def cmd_new(ns):
    r = _p(ns).new(ns.target, ns.measure, on_wake=ns.on_wake, allowed=(ns.allowed.split(",") if ns.allowed else None),
                   max_rounds=ns.max_rounds, max_runtime_seconds=ns.max_runtime_seconds,
                   done_regex=ns.done_regex, diverge_regex=ns.diverge_regex, monitor_every_seconds=ns.monitor_every)
    return r, None, f"{r['campaign_id']}  target: {r['target']}"


def cmd_wake(ns):
    r = _p(ns).wake(ns.campaign_id, at=ns.at, in_seconds=ns.in_seconds, reason=ns.reason)
    return r, None, f"{r['id']} at {r['at']}"


def cmd_tick(ns):
    fired = _p(ns).tick(now=ns.now)
    return fired, {"count": len(fired)}, "\n".join(f"{f['campaign_id']} woke ({f['reason']}) round={f['round']}" for f in fired) or "(nothing due)"


def cmd_measure(ns):
    m = _p(ns).measure(ns.campaign_id)
    return m, None, f"{m['id']} exit={m['exit_code']}\n{m['output'][:400]}"


def cmd_decide(ns):
    r = _p(ns).decide(ns.campaign_id, ns.action, ns.cite)
    return r, None, f"{ns.action} recorded (cites {ns.cite})" + (f"; wake {r['id']} at {r['at']}" if r.get("type") == "wake" else "")


def cmd_close(ns):
    r = _p(ns).close(ns.campaign_id, ns.report)
    return r, None, f"closed {ns.campaign_id} with {r['report']}"


def cmd_status(ns):
    p = _p(ns)
    if ns.campaign_id:
        b = _brief(p.get(ns.campaign_id))
        return b, None, json.dumps(b, indent=2)
    rows = [_brief(c) for c in p.campaigns().values()]
    return rows, {"count": len(rows)}, "\n".join(f"{r['campaign_id']}  {r['status']:<6} rounds={r['rounds']} wakes={len(r['pending_wakes'])}  {r['target']}" for r in rows) or "(no campaigns)"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_format_arg(common)
    common.add_argument("--agent-root", default=None, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", parents=[common]); n.add_argument("--target", required=True); n.add_argument("--measure", required=True)
    n.add_argument("--on-wake"); n.add_argument("--allowed"); n.add_argument("--max-rounds", type=int, default=5)
    n.add_argument("--max-runtime-seconds", type=int, default=3600); n.add_argument("--done-regex"); n.add_argument("--diverge-regex")
    n.add_argument("--monitor-every", type=int, default=MONITOR_EVERY_SECONDS); n.set_defaults(fn=cmd_new)
    w = sub.add_parser("wake", parents=[common]); w.add_argument("campaign_id"); w.add_argument("--at"); w.add_argument("--in", dest="in_seconds", type=int)
    w.add_argument("--reason", default="scheduled"); w.set_defaults(fn=cmd_wake)
    t = sub.add_parser("tick", parents=[common]); t.add_argument("--now", default=None, help=argparse.SUPPRESS); t.set_defaults(fn=cmd_tick)
    m = sub.add_parser("measure", parents=[common]); m.add_argument("campaign_id"); m.set_defaults(fn=cmd_measure)
    d = sub.add_parser("decide", parents=[common]); d.add_argument("campaign_id"); d.add_argument("action", choices=["wait", "resubmit", "terminate"])
    d.add_argument("--cite", required=True); d.set_defaults(fn=cmd_decide)
    c = sub.add_parser("close", parents=[common]); c.add_argument("campaign_id"); c.add_argument("--report", required=True); c.set_defaults(fn=cmd_close)
    s = sub.add_parser("status", parents=[common]); s.add_argument("campaign_id", nargs="?"); s.set_defaults(fn=cmd_status)
    l = sub.add_parser("list", parents=[common]); l.set_defaults(fn=cmd_status, campaign_id=None)
    ns = p.parse_args(argv)
    return cli_run(lambda: ns.fn(ns), fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
