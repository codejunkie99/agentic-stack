"""Evolver: diagnosis-driven, gated harness evolution. No model calls.

A harness candidate is a set of replacement files for `.agent/` plus a
descriptor: where it edits (`prompt | knowledge | runtime | config`), which
pathology it targets, the observed symptom, supporting trace events, the
expected behavior change, and an activation marker. Nothing reaches the
live `.agent/` before it beats its parent in a paired screen.

    python3 .agent/tools/evolve.py diagnose [--days 14]
    python3 .agent/tools/evolve.py scaffold <dx_id> --where prompt [--marker TEXT]
    python3 .agent/tools/evolve.py screen <cid> [<cid> ...] --n 4 [--attempts 1] [--seed 7]
    python3 .agent/tools/evolve.py round <cid> ... --n 4 --keep 2
    python3 .agent/tools/evolve.py install <cid>
    python3 .agent/tools/evolve.py genebank

Screening (paired, same task sample for every candidate in a round):
  validity gate    every attempt logged with an exit code (timeouts fail the gate)
  activation gate  the candidate's marker appears in at least one transcript
  paired gain      γ_i = score_candidate(i) − score_parent(i) per task,
                   t = mean(γ)/(sd(γ)/√n), zero variance → ±∞ or 0 by sign
  pass             mean(γ) > 0 and t ≥ 1.96 and both gates, n ≥ 2

Gene bank cells are (where, pathology); each holds one confirmed harness.
Competitors are the incumbent plus confirmed candidates; the higher
full-training utility wins, incumbent kept on ties. `install` applies a
confirmed candidate to the live `.agent/` with a backup. Lineage is the
parent chain. Utility is pass@1 over `evolve/evals/*.json` task cards run
through `evolve/runner.json` (defaults to the standalone conductor).
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
import tempfile

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text import word_set  # noqa: E402
from _cli import CliError, add_format_arg, run as cli_run  # noqa: E402
from dag import run_bounded, expand  # noqa: E402

LAMBDA_SCREEN = 1.96
WHERE = ("prompt", "knowledge", "runtime", "config")
DEFAULT_RUNNER = {"command": ["python3", "{agent_root}/harness/conductor.py", "{prompt}"], "timeout_seconds": 600}
IGNORE_COPY = shutil.ignore_patterns("runtime", ".index", "__pycache__", "evolve", "*.lock", "*.tmp")


class Evolver:
    def __init__(self, agent_root=None):
        self.root = os.path.abspath(agent_root or BASE)
        self.dir = os.path.join(self.root, "evolve")
        self.evals = os.path.join(self.dir, "evals")
        self.candidates = os.path.join(self.dir, "candidates")
        self.rounds = os.path.join(self.dir, "rounds")
        self.backups = os.path.join(self.dir, "backups")
        self.genebank = os.path.join(self.dir, "genebank.jsonl")
        self.diagnoses = os.path.join(self.dir, "diagnoses.jsonl")
        self.state_path = os.path.join(self.dir, "state.json")
        self.episodic = os.path.join(self.root, "memory", "episodic", "AGENT_LEARNINGS.jsonl")

    # --- helpers --------------------------------------------------------------
    @staticmethod
    def _now():
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def _jsonl(path):
        rows = []
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows

    @staticmethod
    def _append(path, row):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    @staticmethod
    def _write_json(path, obj):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
        os.replace(tmp, path)

    def state(self):
        try:
            return json.load(open(self.state_path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"round": 0, "stagnation": 0}

    def runner(self):
        try:
            r = json.load(open(os.path.join(self.dir, "runner.json"), encoding="utf-8"))
            return {"command": list(r["command"]), "timeout_seconds": int(r.get("timeout_seconds") or 600)}
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return dict(DEFAULT_RUNNER)

    def tasks(self):
        out = []
        if os.path.isdir(self.evals):
            for name in sorted(os.listdir(self.evals)):
                if name.endswith(".json"):
                    try:
                        t = json.load(open(os.path.join(self.evals, name), encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if t.get("id") and t.get("prompt") and isinstance(t.get("check"), dict):
                        out.append(t)
        return out

    def descriptor(self, cid):
        path = os.path.join(self.candidates, cid, "descriptor.json")
        try:
            return json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise CliError("not_found", f"candidate {cid} not found")

    # --- diagnose ----------------------------------------------------------------
    @staticmethod
    def _pathology(detail):
        words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", (detail or "").lower()) if w in word_set(w)][:5]
        return "-".join(words) or "unspecified"

    def diagnose(self, days=14, now=None):
        now = now or datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(days=days)
        groups = {}
        for e in self._jsonl(self.episodic):
            if e.get("result") != "failure":
                continue
            try:
                ts = datetime.datetime.fromisoformat(e["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
            except (KeyError, ValueError):
                continue
            if ts < cutoff:
                continue
            key = (e.get("skill") or "unknown", self._pathology(e.get("detail") or e.get("reflection")))
            g = groups.setdefault(key, {"count": 0, "events": [], "symptom": (e.get("detail") or e.get("reflection") or "")[:300]})
            g["count"] += 1
            if len(g["events"]) < 10:
                g["events"].append(e.get("timestamp"))
        existing = {d["id"]: d for d in self._jsonl(self.diagnoses)}
        out = []
        for (skill, pathology), g in sorted(groups.items(), key=lambda kv: -kv[1]["count"]):
            dx_id = "dx_" + hashlib.sha1(f"{skill}|{pathology}".encode()).hexdigest()[:8]
            skill_md = os.path.join("skills", skill, "SKILL.md")
            loc = skill_md if os.path.exists(os.path.join(self.root, skill_md)) else "harness/PLANNING.md"
            d = {"id": dx_id, "skill": skill, "pathology": pathology, "symptom": g["symptom"],
                 "trace_event_ids": g["events"], "count": g["count"], "edit_location": loc,
                 "expected_change": f"fewer '{pathology}' failures in {skill}", "diagnosed_at": self._now()}
            if dx_id not in existing or existing[dx_id].get("count") != g["count"]:
                self._append(self.diagnoses, d)
            out.append(d)
        return out

    # --- scaffold ------------------------------------------------------------------
    def scaffold(self, dx_id, where, marker=None, files=None):
        if where not in WHERE:
            raise CliError("invalid_args", f"--where must be one of {WHERE}")
        dx = next((d for d in reversed(self._jsonl(self.diagnoses)) if d["id"] == dx_id), None)
        if not dx:
            raise CliError("not_found", f"diagnosis {dx_id} not found", hint="run `evolve.py diagnose` first")
        cid = "h_" + hashlib.sha1(f"{dx_id}|{where}|{self._now()}".encode()).hexdigest()[:8]
        cdir = os.path.join(self.candidates, cid)
        default_loc = {"prompt": dx["edit_location"], "knowledge": "memory/semantic/DOMAIN_KNOWLEDGE.md",
                       "runtime": "harness/seats.json", "config": "loops/budget.json"}[where]
        rels = files or [default_loc]
        for rel in rels:
            src = os.path.join(self.root, rel)
            dst = os.path.join(cdir, "files", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            else:
                open(dst, "w", encoding="utf-8").write("{}\n" if rel.endswith(".json") else "")
        cell = self.cells().get(f"{where}|{dx['pathology']}")
        desc = {"id": cid, "where": where, "pathology": dx["pathology"], "diagnosis_id": dx_id,
                "symptom": dx["symptom"], "trace_event_ids": dx["trace_event_ids"], "edit_location": rels,
                "expected_change": dx["expected_change"], "activation": {"marker": marker},
                "parent": (cell or {}).get("harness_id", "h0"), "created_at": self._now()}
        self._write_json(os.path.join(cdir, "descriptor.json"), desc)
        return desc

    # --- evaluation ----------------------------------------------------------------
    def _overlay(self, cid=None):
        tmp = tempfile.mkdtemp(prefix="evolve-")
        dst = os.path.join(tmp, ".agent")
        shutil.copytree(self.root, dst, ignore=IGNORE_COPY, symlinks=True)
        if cid:
            fdir = os.path.join(self.candidates, cid, "files")
            for dirpath, _, files in os.walk(fdir):
                for f in files:
                    src = os.path.join(dirpath, f)
                    rel = os.path.relpath(src, fdir)
                    target = os.path.join(dst, rel)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.copy2(src, target)
        return tmp, dst

    @staticmethod
    def _check(task, out, agent_root):
        c = task["check"]
        kind = c.get("type")
        if kind == "contains":
            return 1.0 if str(c.get("value", "")) in out else 0.0
        if kind == "regex":
            return 1.0 if re.search(str(c.get("value", "")), out, re.MULTILINE) else 0.0
        if kind == "command":
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
                f.write(out)
            r = run_bounded(expand(list(c.get("command") or []), {"agent_root": agent_root, "output": f.name}),
                            out, os.path.dirname(agent_root), int(c.get("timeout_seconds") or 120), 20000,
                            env={"TASK_OUTPUT": f.name})
            return 1.0 if r["exit_code"] == 0 else 0.0
        return 0.0

    def _run_tasks(self, agent_root, tasks, attempts):
        runner = self.runner()
        scores, valid, transcripts = [], True, []
        for t in tasks:
            s = 0.0
            for _ in range(attempts):
                cmd = expand(runner["command"], {"agent_root": agent_root, "prompt": t["prompt"], "task_id": t["id"]})
                r = run_bounded(cmd, t["prompt"], os.path.dirname(agent_root), runner["timeout_seconds"], 200000,
                                env={"AGENT_ROOT": agent_root, "AGENT_PROJECT_DIR": os.path.dirname(agent_root)})
                if r["exit_code"] is None or r["error"]:
                    valid = False
                transcripts.append((r["stdout"] or "") + "\n" + (r["stderr"] or ""))
                s += self._check(t, r["stdout"] or "", agent_root)
            scores.append(s / attempts)
        return scores, valid, transcripts

    @staticmethod
    def paired_stat(gains):
        n = len(gains)
        mean = sum(gains) / n
        var = sum((g - mean) ** 2 for g in gains) / (n - 1) if n > 1 else 0.0
        if var <= 1e-12:
            t = math.inf if mean > 0 else (-math.inf if mean < 0 else 0.0)
        else:
            t = mean / (math.sqrt(var) / math.sqrt(n))
        return mean, var, t

    def screen(self, cids, n=4, attempts=1, seed=None, activation_gate=True, tasks=None):
        tasks = tasks if tasks is not None else self.tasks()
        if n < 2:
            raise CliError("invalid_args", "screening needs n ≥ 2 tasks")
        if len(tasks) < n:
            raise CliError("invalid_args", f"only {len(tasks)} eval task cards; need ≥ {n}",
                           hint=f"add task cards under {self.evals}")
        rng = random.Random(seed)
        sample = rng.sample(tasks, n)
        round_id = "scr_" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        results = {"round_id": round_id, "kind": "screen", "n": n, "attempts": attempts, "seed": seed,
                   "sample": [t["id"] for t in sample], "candidates": {}, "created_at": self._now()}
        parents = {}
        for cid in cids:
            desc = self.descriptor(cid)
            parent = desc.get("parent", "h0")
            if parent not in parents:
                ptmp, proot = self._overlay(None if parent == "h0" else parent)
                try:
                    parents[parent] = self._run_tasks(proot, sample, attempts)
                finally:
                    shutil.rmtree(ptmp, ignore_errors=True)
            p_scores, p_valid, _ = parents[parent]
            ctmp, croot = self._overlay(cid)
            try:
                c_scores, c_valid, transcripts = self._run_tasks(croot, sample, attempts)
            finally:
                shutil.rmtree(ctmp, ignore_errors=True)
            marker = (desc.get("activation") or {}).get("marker")
            if marker:
                activated = any(marker in t for t in transcripts)
                activation_unverified = False
            else:
                activated = not activation_gate
                activation_unverified = True
            gains = [c - p for c, p in zip(c_scores, p_scores)]
            mean, var, t = self.paired_stat(gains)
            passed = bool(p_valid and c_valid and activated and mean > 0 and t >= LAMBDA_SCREEN)
            results["candidates"][cid] = {
                "parent": parent, "parent_scores": p_scores, "candidate_scores": c_scores, "gains": gains,
                "mean_gain": round(mean, 4), "variance": round(var, 6),
                "t_pair": ("inf" if t == math.inf else "-inf" if t == -math.inf else round(t, 4)),
                "validity_gate": bool(p_valid and c_valid), "activation_gate": bool(activated),
                "activation_unverified": activation_unverified, "pass": passed,
                "candidate_utility": round(sum(c_scores) / n, 4), "parent_utility": round(sum(p_scores) / n, 4),
            }
        self._write_json(os.path.join(self.rounds, f"{round_id}.json"), results)
        return results

    def _latest_pass(self, cid):
        best = None
        if os.path.isdir(self.rounds):
            for name in sorted(os.listdir(self.rounds)):
                r = json.load(open(os.path.join(self.rounds, name), encoding="utf-8"))
                c = (r.get("candidates") or {}).get(cid)
                if c and c.get("pass"):
                    best = dict(c, round_id=r["round_id"], full_utility=c.get("full_utility"))
        return best

    # --- gene bank ---------------------------------------------------------------------
    def cells(self):
        cells = {}
        for row in self._jsonl(self.genebank):
            cells[f"{row['where']}|{row['pathology']}"] = row
        return cells

    def archive_update(self, cid, utility, round_id, forced=False):
        desc = self.descriptor(cid)
        key = f"{desc['where']}|{desc['pathology']}"
        incumbent = self.cells().get(key)
        if incumbent and not forced and utility <= float(incumbent.get("utility", -1)):
            return {"cell": key, "winner": incumbent["harness_id"], "kept_incumbent": True,
                    "candidate_utility": utility, "incumbent_utility": incumbent.get("utility")}
        lineage = list((incumbent or {}).get("lineage") or [])
        if desc.get("parent") and desc["parent"] != "h0" and desc["parent"] not in lineage:
            lineage.append(desc["parent"])
        lineage.append(cid)
        row = {"where": desc["where"], "pathology": desc["pathology"], "harness_id": cid, "utility": utility,
               "lineage": lineage, "round_id": round_id, "forced": forced, "confirmed_at": self._now()}
        self._append(self.genebank, row)
        return {"cell": key, "winner": cid, "kept_incumbent": False, "candidate_utility": utility,
                "incumbent_utility": (incumbent or {}).get("utility")}

    def round(self, cids, n=4, keep=2, attempts=1, seed=None, patience=3, max_rounds=10, activation_gate=True):
        st = self.state()
        if st.get("round", 0) >= max_rounds:
            return {"stopped": "max_rounds", "state": st}
        if st.get("stagnation", 0) >= patience:
            return {"stopped": "stagnation", "state": st}
        screen = self.screen(cids, n=n, attempts=attempts, seed=seed, activation_gate=activation_gate)
        survivors = [c for c in cids if screen["candidates"][c]["pass"]][:keep]
        tasks = self.tasks()
        archive = []
        for cid in survivors:
            ctmp, croot = self._overlay(cid)
            try:
                scores, valid, _ = self._run_tasks(croot, tasks, attempts)
            finally:
                shutil.rmtree(ctmp, ignore_errors=True)
            if not valid:
                continue
            utility = round(sum(scores) / len(scores), 4)
            screen["candidates"][cid]["full_utility"] = utility
            archive.append(self.archive_update(cid, utility, screen["round_id"]))
        self._write_json(os.path.join(self.rounds, f"{screen['round_id']}.json"), screen)
        confirmed = [a for a in archive if not a["kept_incumbent"]]
        st["round"] = st.get("round", 0) + 1
        st["stagnation"] = 0 if confirmed else st.get("stagnation", 0) + 1
        st["last_round_id"] = screen["round_id"]
        self._write_json(self.state_path, st)
        return {"round_id": screen["round_id"], "survivors": survivors, "archive": archive, "state": st,
                "stopped": ("stagnation" if st["stagnation"] >= patience else
                            "max_rounds" if st["round"] >= max_rounds else None)}

    # --- install ------------------------------------------------------------------------
    def install(self, cid, force=False):
        desc = self.descriptor(cid)
        confirmed = any(r["harness_id"] == cid for r in self._jsonl(self.genebank))
        passed = self._latest_pass(cid)
        if not (confirmed or passed) and not force:
            raise CliError("permission", f"candidate {cid} has not passed screening",
                           hint="run `evolve.py screen` or `round` first; --force bypasses the gate and is logged")
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        bdir = os.path.join(self.backups, f"{stamp}-{cid}")
        fdir = os.path.join(self.candidates, cid, "files")
        applied = []
        for dirpath, _, files in os.walk(fdir):
            for f in files:
                src = os.path.join(dirpath, f)
                rel = os.path.relpath(src, fdir)
                dst = os.path.join(self.root, rel)
                if os.path.exists(dst):
                    os.makedirs(os.path.dirname(os.path.join(bdir, rel)), exist_ok=True)
                    shutil.copy2(dst, os.path.join(bdir, rel))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                applied.append(rel)
        if not confirmed:
            self.archive_update(cid, float((passed or {}).get("candidate_utility") or 0.0),
                                (passed or {}).get("round_id") or "forced", forced=not passed)
        return {"candidate": cid, "applied": applied, "backup": bdir if applied else None, "forced": force and not passed}


# --- CLI ----------------------------------------------------------------------------------

def _ev(ns):
    return Evolver(ns.agent_root)


def cmd_diagnose(ns):
    rows = _ev(ns).diagnose(days=ns.days)
    text = "\n".join(f"{d['id']}  x{d['count']:<3} {d['skill']:<20} {d['pathology']:<30} -> {d['edit_location']}" for d in rows) or "(no failures in window)"
    return rows, {"count": len(rows)}, text


def cmd_scaffold(ns):
    d = _ev(ns).scaffold(ns.dx_id, ns.where, marker=ns.marker, files=ns.file)
    return d, None, f"{d['id']}  edit files under evolve/candidates/{d['id']}/files/ ({', '.join(d['edit_location'])})"


def cmd_screen(ns):
    r = _ev(ns).screen(ns.cids, n=ns.n, attempts=ns.attempts, seed=ns.seed, activation_gate=not ns.no_activation_gate)
    text = "\n".join(f"{cid}: pass={c['pass']} mean_gain={c['mean_gain']} t={c['t_pair']} "
                     f"validity={c['validity_gate']} activation={c['activation_gate']}"
                     f"{' (unverified)' if c['activation_unverified'] else ''}" for cid, c in r["candidates"].items())
    return r, {"round_id": r["round_id"]}, f"{r['round_id']} sample={r['sample']}\n{text}"


def cmd_round(ns):
    r = _ev(ns).round(ns.cids, n=ns.n, keep=ns.keep, attempts=ns.attempts, seed=ns.seed,
                      patience=ns.patience, max_rounds=ns.max_rounds, activation_gate=not ns.no_activation_gate)
    if r.get("stopped") and "round_id" not in r:
        return r, None, f"stopped: {r['stopped']} (state={r['state']})"
    text = f"{r['round_id']} survivors={r['survivors']} archive={r['archive']} state={r['state']}"
    if r.get("stopped"):
        text += f"\nstop condition reached: {r['stopped']}"
    return r, None, text


def cmd_install(ns):
    r = _ev(ns).install(ns.cid, force=ns.force)
    return r, None, f"installed {r['candidate']}: {', '.join(r['applied']) or '(no files)'}; backup={r['backup']}"


def cmd_genebank(ns):
    cells = _ev(ns).cells()
    rows = list(cells.values())
    return rows, {"count": len(rows)}, "\n".join(f"{r['where']:<10} {r['pathology']:<30} {r['harness_id']}  u={r['utility']}  lineage={'>'.join(r['lineage'])}" for r in rows) or "(empty gene bank)"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_format_arg(common)
    common.add_argument("--agent-root", default=None, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diagnose", parents=[common]); d.add_argument("--days", type=int, default=14); d.set_defaults(fn=cmd_diagnose)
    s = sub.add_parser("scaffold", parents=[common]); s.add_argument("dx_id"); s.add_argument("--where", required=True, choices=WHERE)
    s.add_argument("--marker"); s.add_argument("--file", nargs="*"); s.set_defaults(fn=cmd_scaffold)
    for name, fn in (("screen", cmd_screen), ("round", cmd_round)):
        x = sub.add_parser(name, parents=[common]); x.add_argument("cids", nargs="+"); x.add_argument("--n", type=int, default=4)
        x.add_argument("--attempts", type=int, default=1); x.add_argument("--seed", type=int, default=None)
        x.add_argument("--no-activation-gate", action="store_true")
        if name == "round":
            x.add_argument("--keep", type=int, default=2); x.add_argument("--patience", type=int, default=3)
            x.add_argument("--max-rounds", type=int, default=10)
        x.set_defaults(fn=fn)
    i = sub.add_parser("install", parents=[common]); i.add_argument("cid"); i.add_argument("--force", action="store_true"); i.set_defaults(fn=cmd_install)
    g = sub.add_parser("genebank", parents=[common]); g.set_defaults(fn=cmd_genebank)
    ns = p.parse_args(argv)
    return cli_run(lambda: ns.fn(ns), fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
