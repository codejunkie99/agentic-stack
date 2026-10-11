"""Offline reflection: consolidate clusters of similar, time-adjacent episodes.

Mechanical, model-free, safe to cron. Pipeline:

  1. scene formation — each episode is a bag of words; it joins the nearest
     scene whose last entry is within `time_window_days` and whose centroid
     cosine ≥ `threshold`, otherwise starts a new scene. Centroid is a
     running mean (μ⁺ = (nμ + z)/(n+1)).
  2. select — scenes with ≥ 2 members that were never consolidated, or that
     gained members since; at most `max_clusters` per run, largest first.
  3. merge — one consolidated episode in chronological order, exact
     duplicate lines dropped, ending with the latest state. Lossy by design;
     originals are kept.
  4. deprecate — members get `deprecated_by: <merged id>` so retrieval and
     the context builder skip them. An audit row lands in
     `memory/reflection_report.jsonl`.

Cluster ids are stable (`cl_<first member id>`), so a scene that grows is
re-consolidated as an `update`, never duplicated.

    python3 .agent/memory/reflect_episodes.py            # run
    python3 .agent/memory/reflect_episodes.py --dry-run  # show what would merge
    0 2 * * 1 python3 /path/.agent/memory/reflect_episodes.py   # weekly cron
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tracks  # noqa: E402

DEFAULT_THRESHOLD = 0.65
DEFAULT_WINDOW_DAYS = 7.0
MAX_CLUSTERS = 10


def _bag(text):
    bag = {}
    for w in tracks.word_set(text):
        bag[w] = bag.get(w, 0.0) + 1.0
    return bag


def _time(e):
    try:
        return tracks._now(datetime.datetime.fromisoformat(e["meta"].get("time") or f"{e['date']}T00:00:00"))
    except (ValueError, TypeError):
        return tracks._now(datetime.datetime(1970, 1, 1))


def form_scenes(entries, threshold=DEFAULT_THRESHOLD, window_days=DEFAULT_WINDOW_DAYS):
    scenes = []
    for e in sorted(entries, key=_time):
        if e["meta"].get("parent_type") == "cluster":
            continue  # merged narratives never re-cluster
        z = _bag(e["body"])
        t = _time(e)
        best, best_sim = None, 0.0
        for s in scenes:
            if abs((t - s["t_last"]).total_seconds()) > window_days * 86400:
                continue
            sim = tracks.cosine(z, s["centroid"])
            if sim > best_sim:
                best, best_sim = s, sim
        if best is not None and best_sim >= threshold:
            n = best["n"]
            cen = {k: v * n / (n + 1) for k, v in best["centroid"].items()}
            for k, v in z.items():
                cen[k] = cen.get(k, 0.0) + v / (n + 1)
            best["centroid"] = cen
            best["n"] = n + 1
            best["members"].append(e)
            best["t_last"] = max(best["t_last"], t)
        else:
            scenes.append({"id": f"cl_{e['id']}", "centroid": z, "n": 1, "members": [e], "t_last": t})
    return scenes


def _state_path(root):
    return os.path.join(root, ".reflection_state.json")


def _load_state(root):
    try:
        with open(_state_path(root), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def merge_narrative(members):
    seen, lines = set(), []
    for m in sorted(members, key=_time):
        stamp = (m["meta"].get("time") or m["date"] or "")[:16]
        for line in m["body"].splitlines():
            key = line.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            lines.append(f"- [{stamp}] {line.strip()}")
    return "\n".join(lines)


def reflect(root=None, threshold=DEFAULT_THRESHOLD, window_days=DEFAULT_WINDOW_DAYS,
            max_clusters=MAX_CLUSTERS, dry_run=False, now=None):
    root = root or tracks.MEMORY_ROOT
    state = _load_state(root)
    entries = tracks.iter_entries("episode", root=root, include_deprecated=True)
    live = [e for e in entries if not e["deprecated_by"] or e["meta"].get("parent_type") == "cluster"]
    scenes = [s for s in form_scenes(live, threshold, window_days) if len(s["members"]) >= 2]

    todo = []
    for s in scenes:
        prev = state.get(s["id"])
        member_ids = [m["id"] for m in s["members"]]
        if prev and set(prev.get("members", [])) >= set(member_ids):
            continue  # consolidated and unchanged
        todo.append((s, "update" if prev else "init"))
    todo.sort(key=lambda t: len(t[0]["members"]), reverse=True)
    todo = todo[:max_clusters]

    reports = []
    for s, mode in todo:
        member_ids = [m["id"] for m in s["members"]]
        narrative = merge_narrative(s["members"])
        header = f"Consolidated {len(member_ids)} episodes ({mode})."
        report = {"cluster_id": s["id"], "mode": mode, "source_count": len(member_ids),
                  "merged_entry_id": None, "deprecated_count": 0,
                  "created_at": tracks._now(now).isoformat(), "members": member_ids}
        if not dry_run:
            prev_merged = (state.get(s["id"]) or {}).get("merged_entry_id")
            merged = tracks.append_entry(
                "episode", header + "\n" + narrative,
                {"parent_type": "cluster", "parent_id": s["id"], "session_id": None,
                 "mode": mode, "sources": member_ids}, root=root, now=now)
            report["merged_entry_id"] = merged["id"]
            for mid in member_ids:
                if tracks.deprecate("episode", mid, merged["id"], root=root):
                    report["deprecated_count"] += 1
            if prev_merged:
                tracks.deprecate("episode", prev_merged, merged["id"], root=root)
            state[s["id"]] = {"members": member_ids, "merged_entry_id": merged["id"]}
            with open(os.path.join(root, "reflection_report.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({k: v for k, v in report.items() if k != "members"}) + "\n")
        reports.append(report)
    if not dry_run:
        tmp = _state_path(root) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
        os.replace(tmp, _state_path(root))
    return reports


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    p.add_argument("--window-days", type=float, default=DEFAULT_WINDOW_DAYS)
    p.add_argument("--max-clusters", type=int, default=MAX_CLUSTERS)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--root", default=None, help=argparse.SUPPRESS)
    ns = p.parse_args(argv)
    reports = reflect(root=ns.root, threshold=ns.threshold, window_days=ns.window_days,
                      max_clusters=ns.max_clusters, dry_run=ns.dry_run)
    if ns.json:
        print(json.dumps(reports, indent=2))
    else:
        for r in reports:
            print(f"{r['cluster_id']}  {r['mode']}  sources={r['source_count']}  "
                  f"merged={r['merged_entry_id'] or '(dry-run)'}")
        if not reports:
            print("nothing to consolidate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
