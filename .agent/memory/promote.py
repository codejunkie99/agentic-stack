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


def write_candidates(patterns, candidates_dir):
    """Stage each pattern as a candidate JSON with initial lifecycle metadata.

    Idempotent per pattern key: re-staging preserves prior decision history
    and rejection_count. A pattern rejected three times and re-detected a
    fourth time still shows rejection_count=3 to the reviewer.
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
        path = os.path.join(candidates_dir, f"{slug}.json")
        now = datetime.datetime.now().isoformat()

        prev = {}
        if os.path.exists(path):
            try:
                with open(path) as f:
                    prev = json.load(f)
            except (OSError, json.JSONDecodeError):
                prev = {}

        decisions = prev.get("decisions", [])
        decisions.append({"ts": now, "action": "staged", "reviewer": "auto_dream"})

        candidate = {
            "id": slug,
            "key": key,
            "name": p.get("name", key),
            "claim": claim,
            "conditions": p.get("conditions", []),
            "evidence_ids": p.get("evidence_ids", []),
            "cluster_size": p.get("cluster_size", 1),
            "canonical_salience": p.get("canonical_salience", 0.0),
            "staged_at": now,
            "status": "staged",
            "decisions": decisions,
            "rejection_count": prev.get("rejection_count", 0),
        }
        with open(path, "w") as f:
            json.dump(candidate, f, indent=2)
        written += 1
    return written
