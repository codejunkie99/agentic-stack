"""Content-based clustering + deterministic pattern extraction.

Phase 3's replacement for action-prefix clustering. Works without an LLM:
similarity is Jaccard on word_set, and extraction picks a canonical episode
rather than synthesizing a new claim. Structured candidates flow through the
Phase 1 validation gate — if no LLM is available, they defer as before.
"""
import os, re, sys, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from text import word_set, jaccard
from salience import salience_score


def _normalize_claim(text):
    """Lowercase, strip punctuation, collapse whitespace.

    Used to derive a stable pattern id — same claim text must always produce
    the same id so lifecycle state (decisions, rejection_count, graduation
    status) carries across dream cycles even when the cluster membership
    shifts by one episode. Kept in sync with validate._normalize.
    """
    t = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


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

    An entry joins every existing cluster it's similar to, and all such
    clusters merge into one — proper single-linkage. Without the merge
    step, ordering matters: entries [A, C, B] where A~B~C but A⊄C would
    produce two clusters [A,B] + [C] instead of one, so recurrence
    counts and promotion thresholds become input-order dependent.

    Entries with empty feature sets are dropped (jaccard of two empty
    sets would otherwise be 1.0). Clusters smaller than min_size are
    filtered so singletons don't create candidate churn.
    """
    featured = [(e, _entry_features(e)) for e in entries]
    featured = [(e, fs) for e, fs in featured if fs]

    clusters = []  # each: list of (entry, feature_set)
    for item in featured:
        e_i, fs_i = item
        matching_indices = [
            i for i, c in enumerate(clusters)
            if any(jaccard(fs_i, fs_j) >= threshold for _, fs_j in c)
        ]
        if not matching_indices:
            clusters.append([item])
            continue
        # Merge the new item + every cluster it connects to into one.
        target = clusters[matching_indices[0]]
        target.append(item)
        # Absorb the rest, tail-first so indexing stays valid.
        for idx in reversed(matching_indices[1:]):
            target.extend(clusters[idx])
            del clusters[idx]

    return [[e for e, _ in c] for c in clusters if len(c) >= min_size]


def extract_pattern(cluster):
    """Extractive summarization from a cluster of episodes.

    Without an LLM we cannot synthesize a generalization, so:
      - claim: canonical (highest-salience) member's reflection or action
      - conditions: tokens shared by every cluster member
      - name: longest shared terms + content hash (deterministic, collision-free)
      - evidence_ids: all member timestamps
      - cluster_size: recurrence count
      - canonical_salience: salience of the canonical episode *boosted by*
        cluster_size. Repetition is a learning signal; a recurring-but-moderate
        pattern must be able to clear the promotion threshold even when no
        single episode was extreme. salience_score already caps recurrence at 3.
    """
    canonical = max(cluster, key=salience_score)
    claim = (canonical.get("reflection") or canonical.get("action") or "").strip()

    feature_sets = [_entry_features(e) for e in cluster]
    common = set.intersection(*feature_sets) if feature_sets else set()

    top_terms = sorted(common, key=lambda t: (-len(t), t))[:3]
    name_base = "_".join(top_terms) if top_terms else "untitled"
    # Id derived from normalized claim + conditions (shared tokens). Claim
    # alone would collide for generic canonical text (e.g., "the test
    # failed") occurring in unrelated contexts. Conditions usually stay
    # stable as cluster members shift (intersection of the cluster's common
    # vocabulary), so lifecycle history carries across membership changes
    # in the common case while genuinely-different clusters with the same
    # canonical get distinct ids.
    conditions_key = "|".join(sorted(common))
    pattern_id = hashlib.md5(
        (_normalize_claim(claim) + "||" + conditions_key).encode()
    ).hexdigest()[:12]
    name = f"pattern_{name_base}_{pattern_id[:6]}"

    # Recurrence-aware salience: give the scoring function cluster context
    # without mutating the source episode dict.
    canonical_with_recurrence = dict(canonical)
    canonical_with_recurrence["recurrence_count"] = len(cluster)
    canonical_salience = salience_score(canonical_with_recurrence)

    return {
        "id": pattern_id,
        "name": name,
        "claim": claim,
        "conditions": sorted(common),
        "evidence_ids": [e.get("timestamp", "") for e in cluster if e.get("timestamp")],
        "cluster_size": len(cluster),
        "canonical_salience": canonical_salience,
    }
