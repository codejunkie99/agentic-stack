"""Skill Forge: task-aware skill retrieval, quality admission, explicit updates,
task-intent clustering of agent cases, and lineage. Stdlib only, no model calls.

    python3 .agent/tools/skill_forge.py search "rotate the postgres credentials" --k 5
    python3 .agent/tools/skill_forge.py admit .agent/skills/git-proxy
    python3 .agent/tools/skill_forge.py update --ops ops.json [--skills a b]
    python3 .agent/tools/skill_forge.py cluster
    python3 .agent/tools/skill_forge.py propose
    python3 .agent/tools/skill_forge.py lineage <skill>

Retrieval fuses three sources by exact name with weighted reciprocal-rank
fusion (local 1.0, memory-derived 0.8, hub 0.6; k=60): each source returns up
to 2·k hits, the fused pool is capped at 2·k, blocked (non-admitted) skills
are dropped, and the top k survive. The host agent is the final gate: it
reads the pool and picks, where Raven uses an LLM gate.

Quality facets are integers 0–10 in SKILL.md frontmatter
(`quality: {"utility": 8, "robustness": 6, "safety": 9}`), divided by ten.
Issue flags cap facets; hard flags (prompt_injection, cmd_injection,
unsafe_exec, auth_bypass, csam_risk) refuse admission outright. A skill is
admitted when no hard flag fires and safety ≥ 0.3. Composite:

    atten(s)      = 0 below 0.3, 0.5 at 0.3 rising linearly to 1.0 at 0.7
    qual_content  = atten(s) · (0.50·u + 0.35·r + 0.15·s)
    qual_cur      = clip01(0.85·qual_content + 0.15·p_src + bonus)
    bonus         = +0.05 if scripts/ exists, +0.02 if references/ exists

Update operations are explicit and validated (add needs ≥ 5 non-empty lines
and ≥ 50 chars; one update per target per batch; confidence clipped to
[0, 1], malformed → 0.5 on add / prior on update; confidence < 0.1 keeps
the record retrievable). Lineage: Λ(s⁺) = Unique(Λ(s) ++ [case_id]).

Task-intent clustering groups agent cases (quality < θ_skip=0.2 skipped;
< 0.5 → failure mode; else success) by cosine over bag-of-words intents with
running-mean centroids; `propose` turns success clusters into candidate skill
drafts under memory/candidates/skills/ for host review.
"""
import argparse
import datetime
import json
import os
import re
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.join(BASE, "memory"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text import word_set  # noqa: E402
from _cli import CliError, add_format_arg, run  # noqa: E402
import tracks  # noqa: E402

SKILLS_DIR = os.path.join(BASE, "skills")
MANIFEST = os.path.join(SKILLS_DIR, "_manifest.jsonl")
LINEAGE = os.path.join(SKILLS_DIR, "_lineage.jsonl")
HUB = os.path.join(SKILLS_DIR, "_hub.jsonl")
DERIVED = os.path.join(BASE, "memory", "candidates", "skills")
CLUSTERS = os.path.join(BASE, "memory", ".skill_clusters.json")

RRF_K = 60
SOURCE_WEIGHT = {"local": 1.0, "memory": 0.8, "hub": 0.6}
SOURCE_PRIOR = {"local": 1.0, "memory": 0.8, "hub": 0.5}
BODY_CHARS = 3000
THETA_SKIP = 0.2
THETA_MERGE = 0.5
PREVIEW_CAP = 5

HARD_FLAGS = {
    "prompt_injection": re.compile(r"(?i)ignore (all )?(previous|prior) instructions|disregard (all |your )?(prior|previous|system)"),
    "cmd_injection": re.compile(r"(?i)curl [^\n|]*\|\s*(ba|z)?sh\b|;\s*rm -rf\s+/|\$\(curl"),
    "unsafe_exec": re.compile(r"(?i)\beval\(|\bexec\(|chmod \+x .*&&|sudo rm"),
    "auth_bypass": re.compile(r"(?i)bypass (auth|login|2fa|mfa|verification)|disable (auth|verification|ssl verification)"),
    "csam_risk": re.compile(r"(?!x)x"),  # never matches text; only settable via frontmatter `flags`
}
# soft flag -> (facet, cap)
SOFT_FLAGS = {
    "no_triggers": ("utility", 5),
    "no_examples": ("utility", 7),
    "no_constraints": ("robustness", 7),
    "over_100_lines": ("robustness", 6),
    "no_self_rewrite": ("robustness", 8),
}


def _today():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _clip01(x):
    return max(0.0, min(1.0, x))


# --- frontmatter / manifest ---------------------------------------------------

def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        try:
            fm[k.strip()] = json.loads(v)
        except json.JSONDecodeError:
            fm[k.strip()] = v
    return fm, text[end + 5:]


def render_frontmatter(fm):
    return "---\n" + "\n".join(f"{k}: {json.dumps(v)}" for k, v in fm.items()) + "\n---\n"


def load_manifest(path=None):
    path = path or MANIFEST
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


def upsert_manifest(row, path=None):
    path = path or MANIFEST
    rows = load_manifest(path)
    for i, r in enumerate(rows):
        if r.get("name") == row.get("name"):
            rows[i] = dict(r, **row)
            break
    else:
        rows.append(row)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _skill_path(name, skills_dir=None):
    return os.path.join(skills_dir or SKILLS_DIR, name, "SKILL.md")


# --- admission -----------------------------------------------------------------

def assess(skill_dir, source="local"):
    """Quality facets, flags, admission and composite score for one skill dir."""
    path = os.path.join(skill_dir, "SKILL.md") if os.path.isdir(skill_dir) else skill_dir
    if not os.path.exists(path):
        raise CliError("not_found", f"no SKILL.md at {skill_dir}")
    skill_dir = os.path.dirname(path)
    text = open(path, encoding="utf-8").read()
    fm, body = parse_frontmatter(text)
    q = fm.get("quality") or {}
    facets = {}
    for k in ("utility", "robustness", "safety"):
        v = q.get(k)
        if v is None:
            v = 5
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise CliError("invalid_args", f"quality.{k} must be an integer 0-10")
        facets[k] = max(0, min(10, v))
    flags = []
    for name, pat in HARD_FLAGS.items():
        if pat.search(body):
            flags.append(name)
    for f in fm.get("flags") or []:
        if f in HARD_FLAGS or f in SOFT_FLAGS:
            flags.append(f)
    if not fm.get("triggers"):
        flags.append("no_triggers")
    if "example" not in body.lower():
        flags.append("no_examples")
    if not fm.get("constraints"):
        flags.append("no_constraints")
    if len(text.splitlines()) > 100:
        flags.append("over_100_lines")
    if "self-rewrite" not in body.lower():
        flags.append("no_self_rewrite")
    flags = sorted(set(flags))
    for f in flags:
        if f in SOFT_FLAGS:
            facet, cap = SOFT_FLAGS[f]
            facets[facet] = min(facets[facet], cap)
    hard = [f for f in flags if f in HARD_FLAGS]
    u, r, s = facets["utility"] / 10, facets["robustness"] / 10, facets["safety"] / 10
    license_ok = True
    lic = fm.get("license")
    if source == "hub":
        license_ok = str(lic or "").lower() in {"apache-2.0", "mit", "bsd-2-clause", "bsd-3-clause", "cc0-1.0", "mpl-2.0", "isc"}
    admitted = license_ok and not hard and s >= 0.3
    if s < 0.3:
        atten = 0.0
    elif s < 0.7:
        atten = 0.5 + (s - 0.3) * (0.5 / 0.4)
    else:
        atten = 1.0
    qual_content = atten * (0.50 * u + 0.35 * r + 0.15 * s)
    bonus = (0.05 if os.path.isdir(os.path.join(skill_dir, "scripts")) else 0.0) + \
            (0.02 if os.path.isdir(os.path.join(skill_dir, "references")) else 0.0)
    qual_cur = _clip01(0.85 * qual_content + 0.15 * SOURCE_PRIOR.get(source, 0.5) + bonus)
    return {"name": fm.get("name") or os.path.basename(skill_dir), "facets": facets, "flags": flags,
            "hard_flags": hard, "license_ok": license_ok, "admitted": admitted,
            "qual_content": round(qual_content, 4), "score": round(qual_cur, 4), "source": source}


def admit(skill_dir, manifest=None):
    a = assess(skill_dir)
    upsert_manifest({"name": a["name"], "quality": {**a["facets"], "score": a["score"], "admitted": a["admitted"],
                                                    "flags": a["flags"], "computed_at": _today()}}, manifest)
    return a


# --- retrieval ---------------------------------------------------------------------

def _overlap(q, text):
    if not q:
        return 0.0
    return len(q & word_set(text)) / len(q)


def _score(q, head, body):
    return 0.6 * _overlap(q, head) + 0.4 * _overlap(q, body)


def _local_hits(q, skills_dir, manifest):
    hits = []
    for row in load_manifest(manifest):
        name = row.get("name")
        if not name:
            continue
        path = _skill_path(name, skills_dir)
        body = ""
        if os.path.exists(path):
            _, body = parse_frontmatter(open(path, encoding="utf-8").read())
        head = " ".join([name, " ".join(row.get("triggers") or []), str(row.get("description") or "")])
        quality = row.get("quality") or {}
        hits.append({"name": name, "source": "local", "score": _score(q, head, body[:BODY_CHARS]),
                     "blocked": quality.get("admitted") is False, "path": path,
                     "desc": (row.get("description") or " ".join(row.get("triggers") or []))[:160]})
    return hits


def _memory_hits(q, derived):
    hits = []
    if not os.path.isdir(derived):
        return hits
    for name in sorted(os.listdir(derived)):
        if not name.endswith(".md"):
            continue
        fm, body = parse_frontmatter(open(os.path.join(derived, name), encoding="utf-8").read())
        sname = fm.get("name") or name[:-3]
        head = " ".join([sname, " ".join(fm.get("triggers") or [])])
        hits.append({"name": sname, "source": "memory", "score": _score(q, head, body[:BODY_CHARS]),
                     "blocked": False, "path": os.path.join(derived, name), "desc": body.strip()[:160]})
    return hits


def _hub_hits(q, hub):
    hits = []
    if not os.path.exists(hub):
        return hits
    for line in open(hub, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = row.get("name")
        if not name:
            continue
        head = " ".join([name, str(row.get("desc") or row.get("description") or "")])
        hits.append({"name": name, "source": "hub", "score": _score(q, head, str(row.get("body") or "")[:BODY_CHARS]),
                     "blocked": bool(row.get("blocked")) or (row.get("safety") is not None and float(row["safety"]) < 0.3),
                     "path": row.get("url") or row.get("path") or "", "desc": str(row.get("desc") or row.get("description") or "")[:160]})
    return hits


def search(task, k=5, skills_dir=None, manifest=None, derived=None, hub=None):
    q = word_set(task)
    if not q:
        raise CliError("invalid_args", "task must contain at least one content word")
    per_source = {
        "local": _local_hits(q, skills_dir, manifest),
        "memory": _memory_hits(q, derived or DERIVED),
        "hub": _hub_hits(q, hub or HUB),
    }
    fused, rep = {}, {}
    for src, hits in per_source.items():
        hits = sorted([h for h in hits if h["score"] > 0], key=lambda h: -h["score"])[: 2 * k]
        for rank, h in enumerate(hits, start=1):
            fused[h["name"]] = fused.get(h["name"], 0.0) + SOURCE_WEIGHT[src] / (RRF_K + rank)
            if h["name"] not in rep or h["score"] > rep[h["name"]]["score"]:
                rep[h["name"]] = h
    pool = sorted(fused, key=lambda n: (-fused[n], n))[: 2 * k]
    pool = [n for n in pool if not rep[n]["blocked"]]
    return [dict(rep[n], fused=round(fused[n], 5)) for n in pool[:k]]


# --- explicit update operations ---------------------------------------------------

def _confidence(raw, default):
    try:
        c = float(raw)
    except (TypeError, ValueError):
        return default
    return _clip01(c)


def _lineage_of(name, lineage_path):
    lin = []
    if os.path.exists(lineage_path):
        for line in open(lineage_path, encoding="utf-8"):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("skill") == name:
                lin = row.get("lineage") or lin
    return lin


def apply_ops(ops, skills=None, skills_dir=None, manifest=None, lineage_path=None):
    skills_dir = skills_dir or SKILLS_DIR
    lineage_path = lineage_path or LINEAGE
    skills = list(skills or [])
    if not isinstance(ops, list):
        raise CliError("invalid_args", "ops must be a JSON list")
    seen_targets = set()
    results = []
    for i, op in enumerate(ops):
        kind = (op or {}).get("op")
        if kind not in ("add", "update", "none"):
            raise CliError("invalid_args", f"ops[{i}].op must be add|update|none")
        if kind == "none":
            results.append({"op": "none"})
            continue
        body = str(op.get("body") or "")
        lines = [l for l in body.splitlines() if l.strip()]
        if kind == "add":
            name = op.get("name")
            if not name or not re.match(r"^[a-z0-9][a-z0-9._-]*$", name):
                raise CliError("invalid_args", f"ops[{i}].name must be a lowercase slug")
            if len(lines) < 5 or len(body) < 50:
                raise CliError("invalid_args", f"ops[{i}]: add needs ≥ 5 non-empty lines and ≥ 50 chars")
            path = _skill_path(name, skills_dir)
            if os.path.exists(path):
                raise CliError("conflict", f"skill {name} already exists", hint="use op=update with its index")
            conf = _confidence(op.get("confidence"), 0.5)
            fm = {"name": name, "version": _today(), "triggers": list(op.get("triggers") or []),
                  "tools": list(op.get("tools") or []), "preconditions": [], "constraints": list(op.get("constraints") or []),
                  "category": "forged", "confidence": conf}
            prior = []
        else:
            idx = op.get("index")
            if not isinstance(idx, int) or idx < 0 or idx >= len(skills):
                raise CliError("invalid_args", f"ops[{i}].index must be a zero-based index into --skills")
            if idx in seen_targets:
                raise CliError("invalid_args", f"ops[{i}]: target index {idx} appears twice in one batch")
            seen_targets.add(idx)
            name = skills[idx]
            path = _skill_path(name, skills_dir)
            if not os.path.exists(path):
                raise CliError("not_found", f"skill {name} not found")
            fm, old_body = parse_frontmatter(open(path, encoding="utf-8").read())
            if not lines:
                raise CliError("invalid_args", f"ops[{i}]: update body is empty")
            conf = _confidence(op.get("confidence"), float(fm.get("confidence") or 0.5))
            fm["version"] = _today()
            fm["confidence"] = conf
            prior = _lineage_of(name, lineage_path)
        case_ids = [c for c in (op.get("case_ids") or ([op["case_id"]] if op.get("case_id") else [])) if c]
        lineage = list(prior)
        for c in case_ids:
            if c not in lineage:
                lineage.append(c)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(render_frontmatter(fm) + "\n" + body.strip() + "\n")
        os.replace(tmp, path)
        upsert_manifest({k: fm[k] for k in ("name", "version", "triggers", "tools", "preconditions", "constraints", "category") if k in fm}, manifest)
        os.makedirs(os.path.dirname(lineage_path), exist_ok=True)
        with open(lineage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"skill": name, "op": kind, "confidence": conf, "lineage": lineage,
                                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}) + "\n")
        results.append({"op": kind, "skill": name, "confidence": conf, "lineage": lineage,
                        "low_confidence": conf < 0.1, "path": path})
    return results


# --- task-intent clustering ------------------------------------------------------------

def _intent(case):
    for line in case["body"].splitlines():
        if line.lower().startswith("intent:"):
            return line.split(":", 1)[1].strip()
    return case["body"].splitlines()[0] if case["body"] else ""


def _outcome(case):
    for line in case["body"].splitlines():
        if line.lower().startswith("outcome:"):
            return line.split(":", 1)[1].strip()
    return ""


def _bag(text):
    bag = {}
    for w in word_set(text):
        bag[w] = bag.get(w, 0.0) + 1.0
    return bag


def cluster_cases(root=None, theta_merge=THETA_MERGE, theta_skip=THETA_SKIP):
    clusters = []
    for case in tracks.iter_entries("case", root=root):
        q = case["meta"].get("quality")
        quality = 0.5 if q is None else float(q)
        if quality < theta_skip:
            continue
        mode = "failure" if quality < 0.5 else "success"
        intent = _intent(case)
        z = _bag(intent)
        if not z:
            continue
        best, best_sim = None, 0.0
        for c in clusters:
            sim = tracks.cosine(z, c["centroid"])
            if sim > best_sim:
                best, best_sim = c, sim
        member = {"id": case["id"], "mode": mode, "quality": quality, "intent": intent[:200],
                  "outcome": _outcome(case)[:300]}
        if best is not None and best_sim >= theta_merge:
            n = best["n"]
            cen = {k: v * n / (n + 1) for k, v in best["centroid"].items()}
            for k, v in z.items():
                cen[k] = cen.get(k, 0.0) + v / (n + 1)
            best["centroid"], best["n"] = cen, n + 1
            best["members"].append(member)
        else:
            clusters.append({"id": f"ic_{case['id']}", "centroid": z, "n": 1, "members": [member]})
    out = []
    for c in clusters:
        top = sorted(c["centroid"], key=lambda w: -c["centroid"][w])[:5]
        out.append({"id": c["id"], "keywords": top, "size": c["n"],
                    "success": sum(1 for m in c["members"] if m["mode"] == "success"),
                    "failure": sum(1 for m in c["members"] if m["mode"] == "failure"),
                    "previews": c["members"][:PREVIEW_CAP], "member_ids": [m["id"] for m in c["members"]]})
    return out


def propose(root=None, derived=None, clusters=None):
    derived = derived or DERIVED
    clusters = clusters if clusters is not None else cluster_cases(root=root)
    written = []
    os.makedirs(derived, exist_ok=True)
    for c in clusters:
        if c["success"] < 2:
            continue
        path = os.path.join(derived, f"{c['id']}.md")
        if os.path.exists(path):
            continue
        name = "forged-" + "-".join(c["keywords"][:3]) if c["keywords"] else c["id"]
        fm = {"name": name, "triggers": c["keywords"][:3], "confidence": 0.5, "sources": c["member_ids"],
              "cluster": c["id"], "status": "candidate"}
        succ = [m for m in c["previews"] if m["mode"] == "success"]
        fail = [m for m in c["previews"] if m["mode"] == "failure"]
        body = ["# " + name, "", "Draft forged from agent cases. Review, then install with",
                "`skill_forge.py update --ops` (op=add) or extend an existing skill.", "",
                "## When", *[f"- {m['intent']}" for m in succ], "", "## Procedure (what worked)",
                *[f"- {m['outcome'] or '(no outcome recorded)'}" for m in succ]]
        if fail:
            body += ["", "## Failures to avoid", *[f"- {m['intent']}: {m['outcome']}" for m in fail]]
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_frontmatter(fm) + "\n" + "\n".join(body) + "\n")
        written.append({"cluster": c["id"], "path": path, "name": name})
    return written


# --- CLI ------------------------------------------------------------------------------

def _cmd_search(ns):
    hits = search(ns.task, ns.k, hub=ns.hub)
    text = "\n".join(f"{h['fused']:.4f}  {h['source']:<6} {h['name']:<24} {h['desc']}" for h in hits) or "(no skills matched)"
    return hits, {"count": len(hits)}, text


def _cmd_admit(ns):
    a = admit(ns.skill)
    text = (f"{a['name']}: admitted={a['admitted']} score={a['score']} facets={a['facets']} "
            f"flags={','.join(a['flags']) or '-'}")
    return a, None, text


def _cmd_update(ns):
    try:
        ops = json.load(open(ns.ops, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise CliError("invalid_args", f"cannot read ops file: {e}")
    res = apply_ops(ops, skills=ns.skills)
    return res, {"count": len(res)}, "\n".join(f"{r['op']:<6} {r.get('skill','-'):<24} conf={r.get('confidence','-')}" for r in res)


def _cmd_cluster(ns):
    clusters = cluster_cases()
    os.makedirs(os.path.dirname(CLUSTERS), exist_ok=True)
    with open(CLUSTERS, "w", encoding="utf-8") as f:
        json.dump(clusters, f, indent=2)
    text = "\n".join(f"{c['id']}  size={c['size']} ok={c['success']} fail={c['failure']}  {' '.join(c['keywords'])}" for c in clusters) or "(no cases)"
    return clusters, {"count": len(clusters), "path": CLUSTERS}, text


def _cmd_propose(ns):
    w = propose()
    return w, {"count": len(w)}, "\n".join(f"{r['name']}  {r['path']}" for r in w) or "(nothing to propose)"


def _cmd_lineage(ns):
    lin = _lineage_of(ns.skill, LINEAGE)
    return {"skill": ns.skill, "lineage": lin}, None, f"{ns.skill}: {' -> '.join(lin) or '(no lineage)'}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    add_format_arg(common)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", parents=[common]); s.add_argument("task"); s.add_argument("--k", type=int, default=5)
    s.add_argument("--hub", default=None); s.set_defaults(fn=_cmd_search)
    a = sub.add_parser("admit", parents=[common]); a.add_argument("skill"); a.set_defaults(fn=_cmd_admit)
    u = sub.add_parser("update", parents=[common]); u.add_argument("--ops", required=True)
    u.add_argument("--skills", nargs="*", default=[]); u.set_defaults(fn=_cmd_update)
    c = sub.add_parser("cluster", parents=[common]); c.set_defaults(fn=_cmd_cluster)
    pr = sub.add_parser("propose", parents=[common]); pr.set_defaults(fn=_cmd_propose)
    li = sub.add_parser("lineage", parents=[common]); li.add_argument("skill"); li.set_defaults(fn=_cmd_lineage)
    ns = p.parse_args(argv)
    return run(lambda: ns.fn(ns), fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
