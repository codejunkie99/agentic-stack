"""Content-based clustering + deterministic pattern extraction.

Phase 3's replacement for action-prefix clustering. Works without an LLM:
similarity is Jaccard on word_set, and extraction picks a canonical episode
rather than synthesizing a new claim. Structured candidates flow through the
Phase 1 validation gate — if no LLM is available, they defer as before.
"""
import os, sys, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from text import word_set, jaccard
from salience import salience_score


def _entry_features(entry):
    """Content feature set for clustering: action + reflection + detail."""
    text = " ".join([
        entry.get("action", ""),
        entry.get("reflection", ""),
        entry.get("detail", ""),
    ])
    return word_set(text)


def content_cluster(entries, threshold=0.3, min_size=2):
    """Single-linkage agglomerative clustering on Jaccard similarity.

    An entry joins the first cluster where any member's similarity meets
    threshold. Entries with empty feature sets are dropped (they can't
    cluster meaningfully — jaccard on two empty sets returns 1.0 in the
    shared helper, so we filter here rather than fight the math).

    Returns only clusters with >= min_size members so singletons don't
    create candidate churn.
    """
    featured = [(e, _entry_features(e)) for e in entries]
    featured = [(e, fs) for e, fs in featured if fs]

    clusters = []  # each: list of (entry, feature_set)
    for item in featured:
        e_i, fs_i = item
        joined = False
        for c in clusters:
            if any(jaccard(fs_i, fs_j) >= threshold for _, fs_j in c):
                c.append(item)
                joined = True
                break
        if not joined:
            clusters.append([item])

    return [[e for e, _ in c] for c in clusters if len(c) >= min_size]


def extract_pattern(cluster):
    """Extractive summarization from a cluster of episodes.

    Without an LLM we cannot synthesize a generalization, so:
      - claim: canonical (highest-salience) member's reflection or action
      - conditions: tokens shared by every cluster member
      - name: longest shared terms + content hash (deterministic, collision-free)
      - evidence_ids: all member timestamps
      - cluster_size, canonical_salience: fed into the promotion gate
    """
    canonical = max(cluster, key=salience_score)
    claim = (canonical.get("reflection") or canonical.get("action") or "").strip()

    feature_sets = [_entry_features(e) for e in cluster]
    common = set.intersection(*feature_sets) if feature_sets else set()

    top_terms = sorted(common, key=lambda t: (-len(t), t))[:3]
    sig = hashlib.md5(" ".join(sorted(common)).encode()).hexdigest()[:6]
    name_base = "_".join(top_terms) if top_terms else "untitled"
    name = f"pattern_{name_base}_{sig}"

    return {
        "name": name,
        "claim": claim,
        "conditions": sorted(common),
        "evidence_ids": [e.get("timestamp", "") for e in cluster if e.get("timestamp")],
        "cluster_size": len(cluster),
        "canonical_salience": salience_score(canonical),
    }
