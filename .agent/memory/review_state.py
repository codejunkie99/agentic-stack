"""Candidate lifecycle + decision log.

Each candidate JSON under memory/candidates/ carries:
  status:    staged | provisional | accepted | rejected | superseded
  decisions: append-only list of {ts, action, reviewer, notes, **fields}

Host-agent CLI tools (.agent/tools/graduate.py, reject.py, reopen.py) call
into this module to transition state. Rejection and re-stage preserve full
history so a candidate that keeps reappearing is visibly churning rather
than looking novel each time.
"""
import os, json, datetime, hashlib


def _now():
    return datetime.datetime.now().isoformat()


def _touch(candidate, action, reviewer, notes="", **fields):
    decisions = candidate.setdefault("decisions", [])
    decisions.append({
        "ts": _now(),
        "action": action,
        "reviewer": reviewer,
        "notes": notes,
        **fields,
    })


def _lessons_sha(candidates_dir):
    """Short hash of current LESSONS.md, used to stamp decisions.

    Re-staging logic uses this to tell 'semantic state changed since this
    decision' apart from 'nothing has changed, skip to avoid churn'.
    """
    lessons_path = os.path.join(
        os.path.dirname(candidates_dir), "semantic", "LESSONS.md")
    if not os.path.exists(lessons_path):
        return ""
    try:
        with open(lessons_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:12]
    except OSError:
        return ""


def _stamp_evidence_and_lessons(cand, candidates_dir):
    """Attach evidence + lessons snapshots to the most recent decision.

    Called on every terminal-ish transition (rejected, graduated). Lets
    write_candidates decide whether a later re-detection represents genuinely
    new information or the same state we already judged.
    """
    if not cand.get("decisions"):
        return
    last = cand["decisions"][-1]
    last["evidence_snapshot"] = list(cand.get("evidence_ids", []))
    last["lessons_sha"] = _lessons_sha(candidates_dir)


def load_candidate(path):
    with open(path) as f:
        return json.load(f)


def save_candidate(candidate, path):
    with open(path, "w") as f:
        json.dump(candidate, f, indent=2)


def stage_candidate(candidate_path, reviewer="auto_dream"):
    """Mark a freshly-written candidate as staged with an initial decision entry."""
    cand = load_candidate(candidate_path)
    cand.setdefault("status", "staged")
    _touch(cand, "staged", reviewer)
    save_candidate(cand, candidate_path)


def _default_queue_path(candidates_dir):
    """By convention, memory/candidates/ sits next to memory/working/REVIEW_QUEUE.md."""
    memory_dir = os.path.dirname(candidates_dir)
    return os.path.join(memory_dir, "working", "REVIEW_QUEUE.md")


def _refresh_queue(candidates_dir):
    """Keep REVIEW_QUEUE.md in sync after any lifecycle transition.

    build_context loads this file into every host session, so a stale file
    makes reviewed items keep appearing as pending and reopened items stay
    invisible until the next dream cycle.
    """
    try:
        write_review_queue_summary(candidates_dir, _default_queue_path(candidates_dir))
    except Exception:
        # Never let queue bookkeeping break a graduation / rejection action.
        pass


def mark_graduated(candidate_id, reviewer, rationale, candidates_dir,
                   provisional=False):
    """Move a staged candidate to candidates/graduated/ with an accept decision.

    Returns the graduated candidate dict. Caller is responsible for writing
    the structured lesson entry to semantic/lessons.jsonl and re-rendering
    LESSONS.md — this function only handles the candidate side.
    """
    src = os.path.join(candidates_dir, f"{candidate_id}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"candidate not found: {candidate_id}")
    cand = load_candidate(src)
    cand["status"] = "provisional" if provisional else "accepted"
    cand["accepted_at"] = _now()
    cand["reviewer"] = reviewer
    cand["rationale"] = rationale
    _touch(cand, "graduated", reviewer, notes=rationale,
           provisional=provisional)
    _stamp_evidence_and_lessons(cand, candidates_dir)

    graduated_dir = os.path.join(candidates_dir, "graduated")
    os.makedirs(graduated_dir, exist_ok=True)
    dst = os.path.join(graduated_dir, f"{candidate_id}.json")
    save_candidate(cand, dst)
    os.remove(src)
    _refresh_queue(candidates_dir)
    return cand


def mark_rejected(candidate_id, reviewer, reason, candidates_dir, **extra_stamp):
    """Move a staged candidate to candidates/rejected/ with a reject decision.

    rejection_count tracks how many times this id has been rejected — if it
    keeps coming back, the reviewer sees churn instead of a 'fresh' item.

    extra_stamp kwargs are merged into the decision entry. heuristic_prefilter
    uses this to record which specific lessons triggered the duplicate rejection
    (duplicate_claims=[...]); write_candidates later checks whether those
    specific lessons are still present before re-staging, so unrelated LESSONS
    edits don't cause the candidate to churn.
    """
    src = os.path.join(candidates_dir, f"{candidate_id}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"candidate not found: {candidate_id}")
    cand = load_candidate(src)
    cand["status"] = "rejected"
    cand["rejection_count"] = cand.get("rejection_count", 0) + 1
    _touch(cand, "rejected", reviewer, notes=reason, **extra_stamp)
    _stamp_evidence_and_lessons(cand, candidates_dir)

    rejected_dir = os.path.join(candidates_dir, "rejected")
    os.makedirs(rejected_dir, exist_ok=True)
    dst = os.path.join(rejected_dir, f"{candidate_id}.json")
    save_candidate(cand, dst)
    os.remove(src)
    _refresh_queue(candidates_dir)
    return cand


def mark_reopened(candidate_id, reviewer, candidates_dir):
    """Move a rejected candidate back to the staged pool with history intact."""
    src = os.path.join(candidates_dir, "rejected", f"{candidate_id}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"rejected candidate not found: {candidate_id}")
    cand = load_candidate(src)
    cand["status"] = "staged"
    _touch(cand, "reopened", reviewer)

    dst = os.path.join(candidates_dir, f"{candidate_id}.json")
    save_candidate(cand, dst)
    os.remove(src)
    _refresh_queue(candidates_dir)
    return cand


def _age_factor(staged_at):
    """1.0 at stage time, grows to 2.0 for candidates ~14 days old."""
    try:
        staged = datetime.datetime.fromisoformat(staged_at)
    except (ValueError, TypeError):
        return 1.0
    age_days = (datetime.datetime.now() - staged).days
    return 1.0 + min(1.0, age_days / 14.0)


def candidate_priority(candidate):
    """priority = cluster_size * canonical_salience * age_factor.

    Reviewers attack high-priority items first. Older + more-recurrent +
    higher-salience patterns deserve attention ahead of one-offs.
    """
    return (
        max(1, candidate.get("cluster_size", 1)) *
        max(0.1, candidate.get("canonical_salience", 0.1)) *
        _age_factor(candidate.get("staged_at", ""))
    )


def list_candidates(candidates_dir, status="staged", sort_by="priority"):
    """Return candidate dicts with the given status, sorted by the key."""
    if status == "staged":
        search_dir = candidates_dir
    else:
        search_dir = os.path.join(candidates_dir, status)
    if not os.path.isdir(search_dir):
        return []

    out = []
    for fname in os.listdir(search_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(search_dir, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as f:
                out.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue

    if sort_by == "priority":
        out.sort(key=candidate_priority, reverse=True)
    elif sort_by == "age":
        out.sort(key=lambda c: c.get("staged_at", ""))
    return out


def write_review_queue_summary(candidates_dir, summary_path):
    """Emit a compact REVIEW_QUEUE.md so the host agent sees the backlog.

    On-demand review without a surfacing mechanism grows silent backlog.
    This file sits in memory/working/ and gets loaded by context_budget into
    every host session — impossible to miss.
    """
    pending = list_candidates(candidates_dir, status="staged")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    if not pending:
        with open(summary_path, "w") as f:
            f.write("# Review Queue\n\n_No pending candidates._\n")
        return 0

    staged_ats = [c.get("staged_at", "") for c in pending if c.get("staged_at")]
    oldest = min(staged_ats) if staged_ats else ""
    lines = ["# Review Queue", ""]
    lines.append(f"**Pending:** {len(pending)}")
    if oldest:
        lines.append(f"**Oldest staged:** {oldest}")
    lines.append("")
    lines.append("Run `python .agent/tools/list_candidates.py` for detail, then:")
    lines.append("- `python .agent/tools/graduate.py <id> --rationale \"...\"` to accept")
    lines.append("- `python .agent/tools/reject.py <id> --reason \"...\"` to reject")
    lines.append("- Review in a batch so cross-candidate contradictions are caught.")
    lines.append("")
    lines.append("## Priority order (top 10)")
    lines.append("")
    for cand in pending[:10]:
        prio = candidate_priority(cand)
        claim_preview = (cand.get("claim") or "")[:80]
        lines.append(
            f"- **{cand.get('id')}** (priority={prio:.2f}, "
            f"size={cand.get('cluster_size', '?')}, "
            f"rejections={cand.get('rejection_count', 0)}) "
            f"— {claim_preview}"
        )
    with open(summary_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return len(pending)
