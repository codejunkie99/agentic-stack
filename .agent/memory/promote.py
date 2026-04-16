"""Cluster + extract + stage candidates. No graduation here — CLI tools do that.

Pipeline:
  1. cluster_and_extract(entries) — content clusters → structured patterns
  2. write_candidates(patterns, dir) — patterns → candidate JSON files

Every staged candidate carries lifecycle metadata (status, decisions,
rejection_count) from birth so repeated churn is visible rather than looking
fresh each time the pattern recurs.
"""
import os, json, datetime, hashlib
from cluster import content_cluster, extract_pattern


def cluster_and_extract(entries, threshold=0.3):
    """Cluster entries by content similarity, extract a pattern per cluster."""
    clusters = content_cluster(entries, threshold=threshold)
    return {p["name"]: p for p in (extract_pattern(c) for c in clusters)}


def _slug(key):
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _find_prior(slug, candidates_dir):
    """Look up any prior record for this slug across lifecycle subdirs.

    Returns (prev_dict, location) where location is one of
    'staged' | 'rejected' | 'graduated' | None. A slug can only live in
    one place at a time; the caller is responsible for cleaning up the
    old location when moving the candidate back to staged.
    """
    staged_path = os.path.join(candidates_dir, f"{slug}.json")
    if os.path.isfile(staged_path):
        try:
            with open(staged_path) as f:
                return json.load(f), "staged"
        except (OSError, json.JSONDecodeError):
            pass
    for sub in ("rejected", "graduated"):
        path = os.path.join(candidates_dir, sub, f"{slug}.json")
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    return json.load(f), sub
            except (OSError, json.JSONDecodeError):
                pass
    return {}, None


def write_candidates(patterns, candidates_dir):
    """Stage each pattern as a candidate JSON with lifecycle metadata.

    Checks all three lifecycle subdirs (staged / rejected / graduated) for an
    existing record with the same slug, and preserves its history.
      - staged already: append a new 'staged' decision, keep original staged_at.
      - rejected previously: move back to staged with rejection_count and
        decision log intact. The reviewer sees this as a recurring pattern,
        not a fresh one.
      - graduated previously: skip entirely. The lesson already lives in
        lessons.jsonl; re-staging would only create work the heuristic
        prefilter would then reject on exact-duplicate grounds.
    """
    if not patterns:
        return 0
    os.makedirs(candidates_dir, exist_ok=True)
    written = 0
    for key, p in patterns.items():
        claim = (p.get("claim") or "").strip()
        if not claim:
            continue
        slug = _slug(key)
        prev, prev_loc = _find_prior(slug, candidates_dir)

        # Already accepted upstream — don't resurrect as a candidate.
        if prev_loc == "graduated":
            continue

        now = datetime.datetime.now().isoformat()
        decisions = prev.get("decisions", [])
        decisions.append({"ts": now, "action": "staged", "reviewer": "auto_dream"})

        # Preserve original staged_at so priority + backlog age signals stay
        # meaningful across re-detections.
        staged_at = prev.get("staged_at") or now

        candidate = {
            "id": slug,
            "key": key,
            "name": p.get("name", key),
            "claim": claim,
            "conditions": p.get("conditions", []),
            "evidence_ids": p.get("evidence_ids", []),
            "cluster_size": p.get("cluster_size", 1),
            "canonical_salience": p.get("canonical_salience", 0.0),
            "staged_at": staged_at,
            "status": "staged",
            "decisions": decisions,
            "rejection_count": prev.get("rejection_count", 0),
        }

        staged_path = os.path.join(candidates_dir, f"{slug}.json")
        with open(staged_path, "w") as f:
            json.dump(candidate, f, indent=2)

        # If the candidate was previously rejected, remove it from the
        # rejected subdir so the same id isn't tracked in two states at once.
        if prev_loc == "rejected":
            try:
                os.remove(os.path.join(candidates_dir, "rejected", f"{slug}.json"))
            except OSError:
                pass
        written += 1
    return written
