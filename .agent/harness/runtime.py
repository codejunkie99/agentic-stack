"""Instance registry and runtime path helpers for the standalone harness.

Managed instances always share the base `personal/` memory. Shared semantic
memory remains the global base corpus, while each managed instance can carry a
branch-local semantic/candidate overlay under `.agent/runtime/instances/<id>/`.
"""
from dataclasses import dataclass
import datetime
import json
import os
import re
import shutil

AGENT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHARED_MEMORY_ROOT = os.path.join(AGENT_ROOT, "memory")
RUNTIME_ROOT = os.path.join(AGENT_ROOT, "runtime")
INSTANCES_ROOT = os.path.join(RUNTIME_ROOT, "instances")
REGISTRY_PATH = os.path.join(RUNTIME_ROOT, "instances.json")

DEFAULT_ROLE = "generalist"
REVIEW_QUEUE_TEMPLATE = "# Review Queue\n\n_No pending candidates._\n"
WORKSPACE_TEMPLATE = """# Workspace (live task state)

> Replace this template on your first real task. The dream cycle auto-archives
> this file after 2 days of inactivity - don't keep long-lived notes here.

## Current task
_none_

## Open files
- _(none)_

## Active hypotheses
- _(none)_

## Checkpoints
- [ ] _(none)_

## Next step
_(what would you do if interrupted and resumed tomorrow?)_
"""

_SLUG_RE = re.compile(r"[^a-z0-9]+")


class UnknownInstanceError(ValueError):
    """Raised when a managed instance id cannot be resolved."""


@dataclass(frozen=True)
class RuntimeContext:
    mode: str
    instance_id: str | None
    instance_name: str | None
    instance_role: str
    parent_instance_id: str | None
    state: str
    workspace_path: str
    episodic_path: str
    candidates_path: str
    semantic_path: str
    shared_semantic_path: str
    lessons_jsonl_path: str
    lessons_md_path: str
    review_queue_path: str
    role_path: str

    def as_metadata(self):
        return {
            "mode": self.mode,
            "instance_id": self.instance_id,
            "instance_name": self.instance_name,
            "instance_role": self.instance_role,
            "parent_instance_id": self.parent_instance_id,
            "state": self.state,
            "workspace_path": self.workspace_path,
            "episodic_path": self.episodic_path,
            "candidates_path": self.candidates_path,
            "semantic_path": self.semantic_path,
            "shared_semantic_path": self.shared_semantic_path,
            "lessons_jsonl_path": self.lessons_jsonl_path,
            "lessons_md_path": self.lessons_md_path,
            "review_queue_path": self.review_queue_path,
            "role_path": self.role_path,
        }


def _now():
    return datetime.datetime.now().isoformat()


def _pid_is_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True


def _default_registry():
    return {"version": 1, "active_instance": None, "instances": []}


def _ensure_runtime_dirs():
    os.makedirs(INSTANCES_ROOT, exist_ok=True)


def _atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _slug(value):
    s = _SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return s or "agent"


def _generate_instance_id(name, registry):
    base = f"{_slug(name)}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    used = {entry.get("id") for entry in registry.get("instances", [])}
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _copy_text_file(src, dst, default_text=""):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if src and os.path.exists(src):
        shutil.copyfile(src, dst)
        return
    with open(dst, "w") as f:
        f.write(default_text)


def _copy_tree(src, dst):
    if src and os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return
    os.makedirs(dst, exist_ok=True)


def _latest_source(episodic_path):
    if not os.path.exists(episodic_path):
        return {}
    latest = {}
    with open(episodic_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                latest = json.loads(line).get("source", {}) or {}
            except json.JSONDecodeError:
                continue
    return latest


def load_registry():
    if not os.path.exists(REGISTRY_PATH):
        return _default_registry()
    try:
        with open(REGISTRY_PATH) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _default_registry()
    if not isinstance(data, dict):
        return _default_registry()
    data.setdefault("version", 1)
    data.setdefault("active_instance", None)
    data.setdefault("instances", [])
    for entry in data["instances"]:
        entry.setdefault("state", "stopped")
        entry.setdefault("worker_pid", None)
        entry.setdefault("worker_started_at", None)
        entry.setdefault("worker_heartbeat_at", None)
        entry.setdefault("last_job_id", None)
        entry.setdefault("last_job_at", None)
    return data


def save_registry(registry):
    _ensure_runtime_dirs()
    _atomic_write_json(REGISTRY_PATH, registry)


def list_instances():
    return load_registry().get("instances", [])


def get_instance(instance_id, registry=None):
    if not instance_id:
        return None
    reg = registry or load_registry()
    for entry in reg.get("instances", []):
        if entry.get("id") == instance_id:
            return entry
    return None


def active_instance_id(registry=None, prefer_env=True):
    explicit = os.environ.get("AGENT_INSTANCE_ID", "").strip()
    if prefer_env and explicit:
        return explicit
    reg = registry or load_registry()
    return reg.get("active_instance") or None


def instance_root(instance_id):
    return os.path.join(INSTANCES_ROOT, instance_id)


def instance_memory_root(instance_id):
    return os.path.join(instance_root(instance_id), "memory")


def shared_workspace_path():
    return os.path.join(SHARED_MEMORY_ROOT, "working", "WORKSPACE.md")


def shared_review_queue_path():
    return os.path.join(SHARED_MEMORY_ROOT, "working", "REVIEW_QUEUE.md")


def shared_episodic_path():
    return os.path.join(SHARED_MEMORY_ROOT, "episodic", "AGENT_LEARNINGS.jsonl")


def shared_candidates_path():
    return os.path.join(SHARED_MEMORY_ROOT, "candidates")


def shared_semantic_path():
    return os.path.join(SHARED_MEMORY_ROOT, "semantic")


def shared_lessons_jsonl_path():
    return os.path.join(shared_semantic_path(), "lessons.jsonl")


def shared_lessons_md_path():
    return os.path.join(shared_semantic_path(), "LESSONS.md")


def instance_workspace_path(instance_id):
    return os.path.join(instance_memory_root(instance_id), "working", "WORKSPACE.md")


def instance_review_queue_path(instance_id):
    return os.path.join(instance_memory_root(instance_id), "working", "REVIEW_QUEUE.md")


def instance_episodic_path(instance_id):
    return os.path.join(
        instance_memory_root(instance_id), "episodic", "AGENT_LEARNINGS.jsonl"
    )


def instance_candidates_path(instance_id):
    return os.path.join(instance_memory_root(instance_id), "candidates")


def instance_semantic_path(instance_id):
    return os.path.join(instance_memory_root(instance_id), "semantic")


def instance_lessons_jsonl_path(instance_id):
    return os.path.join(instance_semantic_path(instance_id), "lessons.jsonl")


def instance_lessons_md_path(instance_id):
    return os.path.join(instance_semantic_path(instance_id), "LESSONS.md")


def instance_role_path(instance_id):
    return os.path.join(instance_root(instance_id), "ROLE.md")


def _shared_runtime_context():
    shared_semantic = shared_semantic_path()
    return RuntimeContext(
        mode="shared",
        instance_id=None,
        instance_name=None,
        instance_role=DEFAULT_ROLE,
        parent_instance_id=None,
        state="shared",
        workspace_path=shared_workspace_path(),
        episodic_path=shared_episodic_path(),
        candidates_path=shared_candidates_path(),
        semantic_path=shared_semantic,
        shared_semantic_path=shared_semantic,
        lessons_jsonl_path=shared_lessons_jsonl_path(),
        lessons_md_path=shared_lessons_md_path(),
        review_queue_path=shared_review_queue_path(),
        role_path="",
    )


def shared_runtime_context():
    return _shared_runtime_context()


def _runtime_context_from_entry(entry):
    instance_id = entry.get("id")
    role_path = instance_role_path(instance_id)
    return RuntimeContext(
        mode="managed",
        instance_id=instance_id,
        instance_name=entry.get("name") or instance_id,
        instance_role=entry.get("role") or DEFAULT_ROLE,
        parent_instance_id=entry.get("parent_instance_id"),
        state=entry.get("state") or "stopped",
        workspace_path=instance_workspace_path(instance_id),
        episodic_path=instance_episodic_path(instance_id),
        candidates_path=instance_candidates_path(instance_id),
        semantic_path=instance_semantic_path(instance_id),
        shared_semantic_path=shared_semantic_path(),
        lessons_jsonl_path=instance_lessons_jsonl_path(instance_id),
        lessons_md_path=instance_lessons_md_path(instance_id),
        review_queue_path=instance_review_queue_path(instance_id),
        role_path=role_path if os.path.exists(role_path) else "",
    )


def resolve_runtime(instance_override=None, allow_unknown=False, prefer_env=True,
                    registry=None):
    reg = registry or load_registry()
    selected = ""
    if instance_override:
        selected = instance_override.strip()
    else:
        selected = active_instance_id(registry=reg, prefer_env=prefer_env) or ""

    if not selected:
        return _shared_runtime_context()

    entry = get_instance(selected, reg)
    if entry:
        return _runtime_context_from_entry(entry)

    if allow_unknown:
        role_path = instance_role_path(selected)
        return RuntimeContext(
            mode="ephemeral",
            instance_id=selected,
            instance_name=selected,
            instance_role=os.environ.get("AGENT_INSTANCE_ROLE", DEFAULT_ROLE),
            parent_instance_id=None,
            state="ephemeral",
            workspace_path=instance_workspace_path(selected),
            episodic_path=instance_episodic_path(selected),
            candidates_path=instance_candidates_path(selected),
            semantic_path=instance_semantic_path(selected),
            shared_semantic_path=shared_semantic_path(),
            lessons_jsonl_path=instance_lessons_jsonl_path(selected),
            lessons_md_path=instance_lessons_md_path(selected),
            review_queue_path=instance_review_queue_path(selected),
            role_path=role_path if os.path.exists(role_path) else "",
        )
    raise UnknownInstanceError(f"unknown instance: {selected}")


def current_instance(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    if runtime_ctx.mode == "shared":
        return None
    return {
        "id": runtime_ctx.instance_id,
        "name": runtime_ctx.instance_name or runtime_ctx.instance_id,
        "role": runtime_ctx.instance_role,
        "state": runtime_ctx.state,
        "parent_instance_id": runtime_ctx.parent_instance_id,
    }


def _entry_snapshot(entry):
    if not entry:
        return None
    worker_pid = entry.get("worker_pid")
    if not _pid_is_alive(worker_pid):
        worker_pid = None
    return {
        "id": entry.get("id"),
        "name": entry.get("name") or entry.get("id"),
        "role": entry.get("role", DEFAULT_ROLE),
        "state": entry.get("state", "stopped"),
        "parent_instance_id": entry.get("parent_instance_id"),
        "worker_pid": worker_pid,
        "worker_started_at": entry.get("worker_started_at"),
        "worker_heartbeat_at": entry.get("worker_heartbeat_at"),
        "last_job_id": entry.get("last_job_id"),
        "last_job_at": entry.get("last_job_at"),
    }


def instance_status(instance_id, registry=None):
    reg = registry or load_registry()
    return _entry_snapshot(get_instance(instance_id, reg))


def current_workspace_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.workspace_path


def current_review_queue_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.review_queue_path


def current_candidates_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.candidates_path


def current_semantic_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.semantic_path


def current_lessons_jsonl_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.lessons_jsonl_path


def current_lessons_md_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.lessons_md_path


def current_episodic_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.episodic_path


def current_role_path(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    return runtime_ctx.role_path


def semantic_dirs(runtime_ctx=None, prefer_env=True):
    runtime_ctx = runtime_ctx or resolve_runtime(prefer_env=prefer_env)
    dirs = [runtime_ctx.shared_semantic_path]
    if runtime_ctx.semantic_path != runtime_ctx.shared_semantic_path:
        dirs.append(runtime_ctx.semantic_path)
    return dirs


def _write_role_file(path, instance_id, role, parent_instance_id=None):
    parent_line = parent_instance_id or "shared-base"
    content = f"""# Instance Role

Role: `{role}`
Instance ID: `{instance_id}`
Forked from: `{parent_line}`

> This file is loaded only for the active instance. Tighten the role here if
> this branch should behave differently from the shared base agent.

## Focus
- Operate as `{role}`.
"""
    _copy_text_file(None, path, default_text=content)


def _seed_review_queue(path, src=None):
    _copy_text_file(src, path, REVIEW_QUEUE_TEMPLATE)


def _seed_instance_memory(instance_id, workspace_src, episodic_src, semantic_src,
                          candidates_src, review_queue_src, role, parent=None):
    _copy_text_file(
        workspace_src, instance_workspace_path(instance_id), WORKSPACE_TEMPLATE
    )
    _copy_text_file(episodic_src, instance_episodic_path(instance_id), "")
    _copy_tree(semantic_src, instance_semantic_path(instance_id))
    _copy_tree(candidates_src, instance_candidates_path(instance_id))
    _seed_review_queue(instance_review_queue_path(instance_id), review_queue_src)
    _write_role_file(instance_role_path(instance_id), instance_id, role, parent)


def _source_paths(source_instance_id=None):
    if source_instance_id:
        if not get_instance(source_instance_id):
            raise UnknownInstanceError(f"unknown instance: {source_instance_id}")
        return (
            instance_workspace_path(source_instance_id),
            instance_episodic_path(source_instance_id),
            instance_semantic_path(source_instance_id),
            instance_candidates_path(source_instance_id),
            instance_review_queue_path(source_instance_id),
        )
    return (
        shared_workspace_path(),
        shared_episodic_path(),
        "",
        "",
        "",
    )


def create_instance(name=None, role=None, source_instance_id=None, activate=False):
    reg = load_registry()
    source_entry = get_instance(source_instance_id, reg) if source_instance_id else None
    inherited_role = source_entry.get("role") if source_entry else None
    role = (role or inherited_role or DEFAULT_ROLE).strip() or DEFAULT_ROLE
    label = name or role or "agent"
    instance_id = _generate_instance_id(label, reg)
    (
        workspace_src,
        episodic_src,
        semantic_src,
        candidates_src,
        review_queue_src,
    ) = _source_paths(source_instance_id)

    _seed_instance_memory(
        instance_id,
        workspace_src=workspace_src,
        episodic_src=episodic_src,
        semantic_src=semantic_src,
        candidates_src=candidates_src,
        review_queue_src=review_queue_src,
        role=role,
        parent=source_instance_id,
    )

    entry = {
        "id": instance_id,
        "name": name or instance_id,
        "role": role,
        "state": "stopped",
        "worker_pid": None,
        "worker_started_at": None,
        "worker_heartbeat_at": None,
        "last_job_id": None,
        "last_job_at": None,
        "created_at": _now(),
        "parent_instance_id": source_instance_id,
        "seed": {
            "workspace": workspace_src,
            "episodic": episodic_src,
            "semantic": semantic_src or shared_semantic_path(),
            "candidates": candidates_src or "",
            "source": _latest_source(episodic_src),
        },
    }
    reg.setdefault("instances", []).append(entry)
    save_registry(reg)
    if activate:
        return start_instance(instance_id)
    return entry


def start_instance(instance_id):
    reg = load_registry()
    entry = get_instance(instance_id, reg)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {instance_id}")
    now = _now()
    entry["state"] = "running"
    entry["started_at"] = entry.get("started_at") or now
    reg["active_instance"] = instance_id
    save_registry(reg)
    return entry


def stop_instance(instance_id=None):
    reg = load_registry()
    target_id = instance_id or reg.get("active_instance")
    if not target_id:
        raise ValueError("no active instance")
    entry = get_instance(target_id, reg)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {target_id}")
    entry["state"] = "stopped"
    entry["worker_pid"] = None
    entry["worker_heartbeat_at"] = _now()
    entry["stopped_at"] = _now()
    if reg.get("active_instance") == target_id:
        reg["active_instance"] = None
    save_registry(reg)
    return entry


def swap_instance(instance_id):
    reg = load_registry()
    entry = get_instance(instance_id, reg)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {instance_id}")
    reg["active_instance"] = instance_id
    save_registry(reg)
    return entry


def mark_worker_started(instance_id, pid):
    reg = load_registry()
    entry = get_instance(instance_id, reg)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {instance_id}")
    now = _now()
    entry["state"] = "running"
    entry["worker_pid"] = pid
    entry["worker_started_at"] = now
    entry["worker_heartbeat_at"] = now
    reg["active_instance"] = instance_id
    save_registry(reg)
    return entry


def mark_worker_heartbeat(instance_id, pid=None, job_id=None):
    reg = load_registry()
    entry = get_instance(instance_id, reg)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {instance_id}")
    entry["worker_heartbeat_at"] = _now()
    if pid is not None:
        entry["worker_pid"] = pid
    if job_id:
        entry["last_job_id"] = job_id
        entry["last_job_at"] = entry["worker_heartbeat_at"]
    save_registry(reg)
    return entry


def mark_worker_stopped(instance_id):
    reg = load_registry()
    entry = get_instance(instance_id, reg)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {instance_id}")
    entry["state"] = "stopped"
    entry["worker_pid"] = None
    entry["worker_heartbeat_at"] = _now()
    entry["stopped_at"] = entry["worker_heartbeat_at"]
    save_registry(reg)
    return entry
