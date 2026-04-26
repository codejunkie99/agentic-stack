"""Lightweight runtime control plane for managed instances.

This module intentionally stays file-backed and stdlib-only:
  - per-instance job queues under `.agent/runtime/instances/<id>/jobs/`
  - per-instance transcripts under `.agent/runtime/instances/<id>/`
  - one adapter-facing active-instance projection at `.agent/ACTIVE_INSTANCE.md`
"""
import datetime
import json
import os
import signal
import sys
import time
import uuid

MEMORY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memory"))
if MEMORY_ROOT not in sys.path:
    sys.path.insert(0, MEMORY_ROOT)

from lesson_store import load_accepted_lessons
from render_lessons import append_lesson, load_lessons, render_lessons
from runtime import (
    AGENT_ROOT,
    UnknownInstanceError,
    get_instance,
    instance_root,
    list_instances,
    load_registry,
    resolve_runtime,
    save_registry,
    shared_runtime_context,
)

ACTIVE_INSTANCE_DOC = os.path.join(AGENT_ROOT, "ACTIVE_INSTANCE.md")


def _now():
    return datetime.datetime.now().isoformat()


def _atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _atomic_write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)


def jobs_root(instance_id):
    return os.path.join(instance_root(instance_id), "jobs")


def queued_jobs_dir(instance_id):
    return os.path.join(jobs_root(instance_id), "queued")


def running_jobs_dir(instance_id):
    return os.path.join(jobs_root(instance_id), "running")


def completed_jobs_dir(instance_id):
    return os.path.join(jobs_root(instance_id), "completed")


def failed_jobs_dir(instance_id):
    return os.path.join(jobs_root(instance_id), "failed")


def worker_stdout_log(instance_id):
    return os.path.join(instance_root(instance_id), "worker.stdout.log")


def worker_stderr_log(instance_id):
    return os.path.join(instance_root(instance_id), "worker.stderr.log")


def worker_stop_flag(instance_id):
    return os.path.join(instance_root(instance_id), "STOP")


def transcript_path(instance_id):
    return os.path.join(instance_root(instance_id), "TRANSCRIPT.jsonl")


def ensure_instance_control_dirs(instance_id):
    for path in (
        queued_jobs_dir(instance_id),
        running_jobs_dir(instance_id),
        completed_jobs_dir(instance_id),
        failed_jobs_dir(instance_id),
    ):
        os.makedirs(path, exist_ok=True)


def pid_is_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def job_counts(instance_id):
    def _count(path):
        if not os.path.isdir(path):
            return 0
        return sum(
            1
            for name in os.listdir(path)
            if name.endswith(".json") and os.path.isfile(os.path.join(path, name))
        )

    return {
        "queued": _count(queued_jobs_dir(instance_id)),
        "running": _count(running_jobs_dir(instance_id)),
        "completed": _count(completed_jobs_dir(instance_id)),
        "failed": _count(failed_jobs_dir(instance_id)),
    }


def queue_job(instance_id, prompt, source="instances.py", metadata=None):
    ensure_instance_control_dirs(instance_id)
    job_id = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    payload = {
        "id": job_id,
        "instance_id": instance_id,
        "prompt": prompt,
        "source": source,
        "metadata": metadata or {},
        "created_at": _now(),
        "status": "queued",
    }
    path = os.path.join(queued_jobs_dir(instance_id), f"{job_id}.json")
    _atomic_write_json(path, payload)
    return payload


def _job_path(search_dir, job_id):
    return os.path.join(search_dir, f"{job_id}.json")


def claim_next_job(instance_id):
    ensure_instance_control_dirs(instance_id)
    queued = queued_jobs_dir(instance_id)
    running = running_jobs_dir(instance_id)
    for name in sorted(os.listdir(queued)):
        if not name.endswith(".json"):
            continue
        src = os.path.join(queued, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(running, name)
        try:
            os.replace(src, dst)
        except OSError:
            continue
        try:
            with open(dst) as f:
                job = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            failed_dir = failed_jobs_dir(instance_id)
            os.makedirs(failed_dir, exist_ok=True)
            quarantined = os.path.join(failed_dir, name)
            try:
                os.replace(dst, quarantined)
            except OSError as move_exc:
                sys.stderr.write(
                    f"[control_plane] WARNING: failed to quarantine corrupt job "
                    f"{dst!r}: {move_exc}\n"
                )
                continue
            sidecar_path = os.path.join(failed_dir, f"{name}.error.json")
            sidecar = {
                "error": str(exc),
                "quarantined_at": datetime.datetime.utcnow().isoformat() + "Z",
                "original_path": src,
            }
            try:
                _atomic_write_json(sidecar_path, sidecar)
            except OSError as side_exc:
                sys.stderr.write(
                    f"[control_plane] WARNING: failed to write quarantine sidecar "
                    f"{sidecar_path!r}: {side_exc}\n"
                )
            sys.stderr.write(
                f"[control_plane] WARNING: quarantined corrupt queued job "
                f"{name!r} for instance {instance_id!r}: {exc}\n"
            )
            continue
        job["status"] = "running"
        job["started_at"] = _now()
        _atomic_write_json(dst, job)
        return job
    return None


def load_job(instance_id, job_id):
    for folder, status in (
        (queued_jobs_dir(instance_id), "queued"),
        (running_jobs_dir(instance_id), "running"),
        (completed_jobs_dir(instance_id), "completed"),
        (failed_jobs_dir(instance_id), "failed"),
    ):
        path = _job_path(folder, job_id)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            job = json.load(f)
        job.setdefault("status", status)
        return job
    return None


def _append_transcript(instance_id, payload):
    os.makedirs(os.path.dirname(transcript_path(instance_id)), exist_ok=True)
    with open(transcript_path(instance_id), "a") as f:
        f.write(json.dumps(payload) + "\n")


def finish_job(instance_id, job, ok, result=None, error=None):
    running_path = _job_path(running_jobs_dir(instance_id), job["id"])
    target_dir = completed_jobs_dir(instance_id) if ok else failed_jobs_dir(instance_id)
    finished = dict(job)
    finished["status"] = "completed" if ok else "failed"
    finished["finished_at"] = _now()
    if ok:
        finished["result"] = result
    else:
        finished["error"] = error
    target_path = _job_path(target_dir, job["id"])
    _atomic_write_json(target_path, finished)
    try:
        if os.path.exists(running_path):
            os.remove(running_path)
    except OSError:
        pass
    transcript = {
        "timestamp": finished["finished_at"],
        "job_id": job["id"],
        "instance_id": instance_id,
        "prompt": job.get("prompt", ""),
        "status": finished["status"],
    }
    if ok:
        transcript["result"] = result
    else:
        transcript["error"] = error
    _append_transcript(instance_id, transcript)
    return finished


def wait_for_job(instance_id, job_id, timeout_sec=60, poll_interval=0.2):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        job = load_job(instance_id, job_id)
        if job and job.get("status") in {"completed", "failed"}:
            return job
        time.sleep(poll_interval)
    return load_job(instance_id, job_id)


def request_worker_stop(instance_id):
    os.makedirs(instance_root(instance_id), exist_ok=True)
    with open(worker_stop_flag(instance_id), "w") as f:
        f.write(_now() + "\n")


def clear_worker_stop_request(instance_id):
    try:
        os.remove(worker_stop_flag(instance_id))
    except OSError:
        pass


def terminate_worker(instance_id, pid, grace_sec=5):
    if not pid_is_alive(pid):
        return False
    request_worker_stop(instance_id)
    try:
        os.kill(int(pid), signal.SIGTERM)
    except OSError:
        return False

    deadline = time.time() + grace_sec
    while time.time() < deadline:
        if not pid_is_alive(pid):
            return True
        time.sleep(0.1)

    try:
        os.kill(int(pid), signal.SIGKILL)
    except OSError:
        pass
    return not pid_is_alive(pid)


def refresh_active_instance_doc(registry=None):
    reg = registry or load_registry()
    runtime_ctx = resolve_runtime(prefer_env=False, registry=reg)
    if runtime_ctx.instance_id:
        body = f"""# Active Instance

Active instance: `{runtime_ctx.instance_id}`
Role: `{runtime_ctx.instance_role}`
State: `{runtime_ctx.state}`

## Active paths
- workspace: `{runtime_ctx.workspace_path}`
- review_queue: `{runtime_ctx.review_queue_path}`
- episodic: `{runtime_ctx.episodic_path}`
- semantic: `{runtime_ctx.semantic_path}`
- candidates: `{runtime_ctx.candidates_path}`
- role_file: `{runtime_ctx.role_path or '(none)'}`

## Adapter rule
If your harness does not have the standalone context builder, treat these
paths as authoritative for this session. Prefer:

```bash
python3 .agent/tools/show.py --instance {runtime_ctx.instance_id}
python3 .agent/tools/recall.py --instance {runtime_ctx.instance_id} "<intent>"
python3 .agent/tools/learn.py --instance {runtime_ctx.instance_id} "<rule>" --rationale "<why>"
python3 .agent/tools/list_candidates.py --instance {runtime_ctx.instance_id}
```
"""
    else:
        body = """# Active Instance

Active instance: `shared`

No managed instance is currently selected. Use the shared `.agent/memory/...`
paths, or start/swap a managed instance with:

```bash
python3 .agent/tools/instances.py list
python3 .agent/tools/instances.py swap <instance-id>
```
"""
    _atomic_write_text(ACTIVE_INSTANCE_DOC, body)
    return ACTIVE_INSTANCE_DOC


def _norm_claim(text):
    import re

    normalized = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", normalized).strip()


def merge_instance_semantic(instance_id):
    runtime_ctx = resolve_runtime(instance_override=instance_id)
    local_rows = [
        row
        for row in load_lessons(runtime_ctx.semantic_path)
        if row.get("status") == "accepted"
    ]
    if not local_rows:
        return {"merged": 0, "skipped": 0, "lesson_ids": []}

    shared_ctx = shared_runtime_context()
    visible_shared, _ = load_accepted_lessons(runtime_ctx=shared_ctx)
    shared_ids = {row.get("id") for row in visible_shared if row.get("id")}
    shared_claims = {_norm_claim(row.get("claim", "")) for row in visible_shared}

    merged = []
    skipped = 0
    for row in local_rows:
        lesson_id = row.get("id")
        claim_key = _norm_claim(row.get("claim", ""))
        if (lesson_id and lesson_id in shared_ids) or claim_key in shared_claims:
            skipped += 1
            continue
        merged_row = dict(row)
        merged_row["merged_from_instance"] = instance_id
        merged_row["merged_at"] = _now()
        append_lesson(merged_row, shared_ctx.semantic_path)
        merged.append(merged_row.get("id"))
        if lesson_id:
            shared_ids.add(lesson_id)
        if claim_key:
            shared_claims.add(claim_key)

    if merged:
        render_lessons(shared_ctx.semantic_path)
    return {"merged": len(merged), "skipped": skipped, "lesson_ids": merged}


def running_instances():
    out = []
    for entry in list_instances():
        if entry.get("state") == "running" and pid_is_alive(entry.get("worker_pid")):
            out.append(entry)
    return out
