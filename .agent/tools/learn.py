"""One-shot lesson teaching.

    python3 .agent/tools/learn.py "Always serialize timestamps in UTC" \\
        --rationale "prior bugs from mixed local/UTC comparisons"

Stages a candidate and graduates it in a single command. Removes the
stage-then-graduate ceremony for the common case: you already know the
lesson, you just want the agent to know it too.

The candidate id comes from the shared `cluster.pattern_id` helper (same
algorithm auto-dream uses) so repeat calls are idempotent within the manual
path: same claim + same conditions → same id → safe retry. IDs will differ
from auto-dream's ids for the same claim because auto-dream infers
conditions from a cluster's common vocabulary, not from the claim alone;
that's intentional (different birth paths, different context).

If graduation fails (e.g., exact-duplicate heuristic reject), the staged
candidate file is removed so `show.py` / `REVIEW_QUEUE.md` don't show
orphaned dead-ends.
"""
import argparse, datetime, errno, json, os, subprocess, sys, tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANDIDATES = os.path.join(BASE, "memory/candidates")
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.join(BASE, "memory"))
from hooks._episodic_io import append_jsonl_once, has_jsonl_timestamp  # noqa: E402
from text import word_set  # noqa: E402
from cluster import pattern_id  # noqa: E402


def _lesson_already_appended(cid):
    """Did graduate.py get as far as writing the lesson to lessons.jsonl?

    Read-only probe. If the lesson_<cid> row is present, graduate.py's
    retry-safety path will complete the move on the next run — the staged
    candidate file MUST stay put for that to work.
    """
    lessons_path = os.path.join(BASE, "memory/semantic/lessons.jsonl")
    if not os.path.exists(lessons_path):
        return False
    target = f"lesson_{cid}"
    try:
        with open(lessons_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("id") == target:
                    return True
    except OSError:
        return False
    return False


def _append_episodic_mirror(cid, claim, source="learn"):
    """Return the canonical timestamp for `manual-stage:{cid}`.

    Inserts one episodic row when that action is absent. A later call
    returns the earliest existing row's timestamp and does not append.
    The check and the insert share the episodic flock inside
    ``append_jsonl_once``. This does not lock ``CANDIDATES``.

    Raises OSError on write failure. ``stage()`` must not publish a
    candidate that references a timestamp until this returns.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    action = f"manual-stage:{cid}"
    entry = {
        "timestamp": ts,
        "skill": "learn",
        "action": action,
        "result": "success",
        "detail": f"Manually staged lesson {cid} via .agent/tools/learn.py: {claim!r}",
        "pain_score": 1,
        "importance": 6,
        "reflection": "",
        "confidence": 0.9,
        "source": {"skill": "learn", "profile": "manual", "run_id": f"manual_{cid[:6]}"},
        "evidence_ids": [ts],
    }
    canonical = append_jsonl_once(_episodic_path(), entry, match_action=action)
    canonical_ts = canonical.get("timestamp")
    if not isinstance(canonical_ts, str) or not canonical_ts:
        raise OSError(f"episodic mirror for {cid} has no timestamp")
    return canonical_ts


def _episodic_path():
    return os.path.join(BASE, "memory/episodic/AGENT_LEARNINGS.jsonl")


def _fsync_dir(directory):
    """Best-effort directory fsync. Portability failures are ignored.

    Directory durability is not part of the evidence invariant. EINVAL,
    ENOTSUP, EBADF, and EPERM (Windows and some filesystems) must not
    decide whether a candidate is published.
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError as err:
        if err.errno in (errno.EINVAL, errno.ENOTSUP, errno.EBADF, errno.EPERM):
            return
        raise
    try:
        try:
            os.fsync(fd)
        except OSError as err:
            if err.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EBADF, errno.EPERM):
                raise
    finally:
        os.close(fd)


def _leftover_temps(cid):
    """Absolute paths of `.{cid}.*.tmp` files in CANDIDATES, sorted."""
    if not os.path.isdir(CANDIDATES):
        return []
    prefix = f".{cid}."
    found = []
    for name in os.listdir(CANDIDATES):
        if name.startswith(prefix) and name.endswith(".tmp"):
            found.append(os.path.join(CANDIDATES, name))
    return sorted(found)


def _evidence_landed(episodic_path, timestamp):
    """True when a parsed JSONL row has this exact timestamp field.

    Raw substring search is intentionally not used. A timestamp that
    appears only inside another string must not count as evidence. The
    complete read holds the episodic LOCK_EX. Without fcntl that lock
    is a no-op.
    """
    return has_jsonl_timestamp(episodic_path, timestamp)


def _load_json_object(path):
    """Load a JSON object. ``None`` means corrupt or the wrong shape.

    ``OSError`` propagates. A transient read error must not look like
    corrupt JSON, or recovery will delete a fsynced temp.
    """
    try:
        with open(path, encoding="utf-8") as stream:
            payload = json.load(stream)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _one_evidence_id(payload):
    evidence = payload.get("evidence_ids")
    if (
        not isinstance(evidence, list)
        or len(evidence) != 1
        or not isinstance(evidence[0], str)
        or not evidence[0]
    ):
        return None
    return evidence[0]


def _resumable_evidence(temp_path, cid):
    """Evidence timestamp if this temp is safe to publish, else None."""
    payload = _load_json_object(temp_path)
    if payload is None or payload.get("id") != cid:
        return None
    evidence = _one_evidence_id(payload)
    if evidence is None:
        return None
    if not _evidence_landed(_episodic_path(), evidence):
        return None
    return evidence


def _remove_or_raise(temp_path):
    try:
        os.remove(temp_path)
    except OSError as err:
        raise OSError(f"failed to remove temp {temp_path}: {err}") from err


def _resume_temp(temp_path, path):
    try:
        os.replace(temp_path, path)
    except OSError as err:
        raise OSError(
            f"{err}; candidate publish failed; fsynced temp kept at {temp_path}"
        ) from err
    # The rename already published the candidate. A directory fsync
    # failure must not make the caller retry and append a second mirror.
    try:
        _fsync_dir(CANDIDATES)
    except OSError:
        pass


def _published_evidence(path, cid):
    if not os.path.isfile(path):
        return None
    payload = _load_json_object(path)
    if payload is None or payload.get("id") != cid:
        return None
    return _one_evidence_id(payload)


def _shared_resumable_evidence(leftovers, cid):
    """One timestamp when every temp is resumable with that same value."""
    stamps = []
    for temp_path in leftovers:
        evidence = _resumable_evidence(temp_path, cid)
        if evidence is None:
            return None
        stamps.append(evidence)
    if len(set(stamps)) != 1:
        return None
    return stamps[0]


def _publish_shared_temps(leftovers, cid, path, evidence):
    published = _published_evidence(path, cid)
    if published is not None and published >= evidence:
        for temp_path in leftovers:
            _remove_or_raise(temp_path)
        return True
    _resume_temp(leftovers[0], path)
    for temp_path in leftovers[1:]:
        _remove_or_raise(temp_path)
    return True


def _resolve_leftovers(cid, path):
    """Finish or discard a prior transaction before a new one starts.

    Returns True when `{cid}.json` is already the file the caller should
    return. Returns False when the caller must start a fresh publish.

    A resumable temp (valid JSON, matching id, evidence timestamp present
    as a JSONL `timestamp` field) is published with `os.replace` and no
    second mirror. If the published evidence timestamp is the same or
    newer, that temp is stale and is removed instead. An evidence-less
    or corrupt temp is
    never published.

    The episodic flock makes the mirror row single-flight for one action.
    Temp files are not locked. Two callers can still each leave a temp
    with the same evidence timestamp. Those twins are one transaction:
    publish one and delete the rest. Temps whose evidence differs stay
    fail-closed. This function does not add a lock.
    """
    leftovers = _leftover_temps(cid)
    if not leftovers:
        return False
    if len(leftovers) > 1:
        shared = _shared_resumable_evidence(leftovers, cid)
        if shared is None:
            raise OSError(
                "ambiguous leftover temps for {cid}; refusing to publish: {paths}".format(
                    cid=cid,
                    paths=", ".join(leftovers),
                )
            )
        return _publish_shared_temps(leftovers, cid, path, shared)
    temp_path = leftovers[0]
    evidence = _resumable_evidence(temp_path, cid)
    if evidence is None:
        _remove_or_raise(temp_path)
        return os.path.isfile(path)
    published = None
    if os.path.isfile(path):
        published_payload = _load_json_object(path)
        if published_payload is not None and published_payload.get("id") == cid:
            published = _one_evidence_id(published_payload)
    # ISO-8601 timestamps from datetime.isoformat() sort lexicographically.
    if published is not None and published >= evidence:
        _remove_or_raise(temp_path)
        return True
    _resume_temp(temp_path, path)
    return True


def stage(claim, conditions, source="learn", importance=7):
    os.makedirs(CANDIDATES, exist_ok=True)
    cid = pattern_id(claim, conditions)
    path = os.path.join(CANDIDATES, f"{cid}.json")
    # Resolve any prior temp before creating another one, so a retry
    # cannot append a second mirror while the first payload is still
    # recoverable.
    if _resolve_leftovers(cid, path):
        return cid, path
    # The mirror assigns the evidence id. A repeat call returns the
    # earliest row's timestamp and does not append another line.
    now = _append_episodic_mirror(cid, claim, source)
    candidate = {
        "id": cid,
        "key": f"manual_{cid[:6]}",
        "name": f"manual_{cid[:6]}",
        "claim": claim,
        "conditions": sorted(conditions),
        "evidence_ids": [now],
        "cluster_size": 1,
        # Manual lessons skip the promotion threshold — they're author-attested,
        # not pattern-extracted. Set salience high enough that retrieval ranks
        # them alongside auto-promoted entries.
        "canonical_salience": 8.0,
        "staged_at": now,
        "status": "staged",
        "decisions": [{"ts": now, "action": "staged", "reviewer": source}],
        "rejection_count": 0,
    }
    # Publish the candidate only after the episodic mirror succeeds, so a
    # visible staged file never carries a dangling evidence_id. Temp file
    # stays in CANDIDATES so os.replace stays same-filesystem.
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CANDIDATES,
            prefix=f".{cid}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = stream.name
            json.dump(candidate, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_dir(CANDIDATES)
        os.replace(temp_path, path)
        temp_path = None
        # Rename already published. Directory fsync must not fail the call.
        try:
            _fsync_dir(CANDIDATES)
        except OSError:
            pass
    except BaseException as primary:
        # The mirror already returned. Keep a temp that was written so
        # the next call can publish it. Do not turn KeyboardInterrupt
        # into OSError.
        if temp_path is not None and isinstance(primary, OSError):
            raise OSError(
                f"{primary}; candidate publish failed; "
                f"fsynced temp kept at {temp_path}"
            ) from primary
        raise
    return cid, path


def main():
    p = argparse.ArgumentParser(
        description="Teach the agent a lesson in one command.")
    p.add_argument("claim", help="The lesson, phrased as a rule or principle.")
    p.add_argument("--rationale", default=None,
                   help="Why this lesson holds. Recommended. If omitted, a "
                        "timestamp-only rationale is used.")
    p.add_argument("--conditions", nargs="*", default=None,
                   help="Optional trigger keywords. Inferred from claim words "
                        "if omitted.")
    p.add_argument("--provisional", action="store_true",
                   help="Graduate as provisional (probationary) — safer for "
                        "experimental rules.")
    p.add_argument("--stage-only", action="store_true",
                   help="Stage the candidate but don't auto-graduate. Useful "
                        "if you want a reviewer to see it first.")
    args = p.parse_args()

    claim = args.claim.strip()
    if len(claim) < 20:
        print(f"ERROR: claim too short ({len(claim)} chars, need >=20). "
              f"Heuristic check would reject this.", file=sys.stderr)
        sys.exit(2)

    conditions = args.conditions
    if conditions is None:
        # Infer conditions from ALL content words in the claim (stopwords
        # stripped by word_set). No truncation — truncation broke id
        # determinism for long claims and drifted from the auto-dream path
        # in ways Codex caught. Fixed list here is the stable signature.
        conditions = sorted(word_set(claim))

    try:
        cid, path = stage(claim, conditions)
    except OSError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
    print(f"staged candidate {cid}")
    print(f"  path: {path}")
    print(f"  conditions: {conditions}")

    if args.stage_only:
        print("\n(stopping here — run graduate.py to accept)")
        return

    rationale = args.rationale or f"manual via learn.py at {datetime.datetime.now(datetime.timezone.utc).isoformat()}"
    grad_args = [
        sys.executable,
        os.path.join(BASE, "tools", "graduate.py"),
        cid,
        "--rationale", rationale,
        "--reviewer", "learn.py",
    ]
    if args.provisional:
        grad_args.append("--provisional")
    result = subprocess.run(grad_args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nERROR: graduation failed (exit {result.returncode})",
              file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        # Decide whether the staged file is safe to delete:
        #   graduate.py's flow is (a) heuristic_check (b) append_lesson
        #   (c) render_lessons (d) mark_graduated.
        # Safe to delete only when we KNOW we're in state (a) — a clean
        # heuristic rejection, nothing written downstream. That's exit
        # code 2 per graduate.py:94. For any other nonzero exit (1,
        # crash, signal, unhandled exception), we can't be sure the
        # lesson wasn't partially written, so preserve the staged file
        # for manual inspection and a retry via graduate.py.
        lesson_written = _lesson_already_appended(cid)
        is_heuristic_reject = (result.returncode == 2 and not lesson_written)
        if os.path.isfile(path) and is_heuristic_reject:
            try:
                os.remove(path)
                print(f"(cleaned up orphaned candidate at {path})",
                      file=sys.stderr)
            except OSError:
                pass
        elif lesson_written:
            print(
                f"(preserved staged file {path} — lesson_{cid} already in "
                f"lessons.jsonl; re-run graduate.py to complete the move)",
                file=sys.stderr)
        else:
            print(
                f"(preserved staged file {path} — graduation exited {result.returncode} "
                f"pre-append; inspect or re-run graduate.py, then delete "
                f"manually if unrecoverable)",
                file=sys.stderr)
        sys.exit(result.returncode)
    print("\n" + result.stdout.strip())


if __name__ == "__main__":
    main()
