"""Manage standalone agent instances, workers, and prompt fanout.

Usage examples:
  python3 .agent/tools/instances.py list
  python3 .agent/tools/instances.py up reviewer
  python3 .agent/tools/instances.py branch skeptic
  python3 .agent/tools/instances.py ask "review the plan"
  python3 .agent/tools/instances.py compare --roles reviewer skeptic "stress this migration"
  python3 .agent/tools/instances.py down reviewer
  python3 .agent/tools/instances.py create reviewer --role reviewer --activate
  python3 .agent/tools/instances.py fork reviewer-20260422103000 --name qa-branch
  python3 .agent/tools/instances.py start reviewer-20260422103000
  python3 .agent/tools/instances.py send reviewer-20260422103000 "review the plan" --wait
  python3 .agent/tools/instances.py fanout --instances a b "stress this migration"
  python3 .agent/tools/instances.py swap reviewer-20260422103000
  python3 .agent/tools/instances.py stop reviewer-20260422103000
"""
import argparse
import json
import os
import subprocess
import sys

# fcntl is POSIX-only. The agentic-stack harness assumes a POSIX environment
# (macOS / Linux); Windows is not a supported runtime for instance workers,
# so we intentionally do not provide an msvcrt fallback here.
import fcntl

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))

from control_plane import (  # noqa: E402
    ensure_instance_control_dirs,
    job_counts,
    merge_instance_semantic,
    pid_is_alive,
    queue_job,
    refresh_active_instance_doc,
    running_instances,
    terminate_worker,
    wait_for_job,
    worker_stderr_log,
    worker_stdout_log,
)
from runtime import (  # noqa: E402
    DEFAULT_ROLE,
    UnknownInstanceError,
    active_instance_id,
    create_instance,
    current_instance,
    get_instance,
    instance_root,
    instance_status,
    list_instances,
    load_registry,
    mark_worker_started,
    mark_worker_stopped,
    start_instance,
    stop_instance,
    swap_instance,
)


def _worker_script():
    return os.path.join(BASE, "harness", "instance_worker.py")


def _entry_created_key(entry):
    return (entry.get("created_at") or "", entry.get("id") or "")


def _entry_state(entry):
    pid = entry.get("worker_pid")
    if entry.get("state") == "running" and pid and not pid_is_alive(pid):
        return "stale"
    return entry.get("state", "stopped")


def _queue_suffix(entry):
    counts = job_counts(entry.get("id"))
    return (
        f"queued={counts['queued']} running={counts['running']} "
        f"done={counts['completed']} failed={counts['failed']}"
    )


def _is_live_worker(entry):
    return bool(entry and entry.get("worker_pid") and pid_is_alive(entry.get("worker_pid")))


def _entries_for_role(role):
    role_key = (role or "").strip().lower()
    if not role_key:
        return []
    matches = [
        entry for entry in list_instances()
        if (entry.get("role") or DEFAULT_ROLE).strip().lower() == role_key
    ]
    return sorted(matches, key=_entry_created_key, reverse=True)


def _entries_for_name(name):
    name_key = (name or "").strip().lower()
    if not name_key:
        return []
    matches = [
        entry for entry in list_instances()
        if (entry.get("name") or "").strip().lower() == name_key
    ]
    return sorted(matches, key=_entry_created_key, reverse=True)


def _pick_preferred(entries):
    if not entries:
        return None
    active_id = active_instance_id(prefer_env=False)
    for entry in entries:
        if entry.get("id") == active_id:
            return entry
    for entry in entries:
        if _is_live_worker(entry):
            return entry
    return entries[0]


def _resolve_instance_ref(ref=None, allow_missing=False):
    if not ref or ref == "active":
        entry = _ensure_target_instance(None)
        return entry

    entry = get_instance(ref)
    if entry:
        return entry

    matches = _entries_for_name(ref)
    if not matches:
        matches = _entries_for_role(ref)
    entry = _pick_preferred(matches)
    if entry:
        return entry
    if allow_missing:
        return None
    raise UnknownInstanceError(f"unknown instance or role: {ref}")


def _ensure_running(entry):
    if _is_live_worker(entry):
        swap_instance(entry.get("id"))
        refresh_active_instance_doc()
        return entry, False, False
    started, created = _spawn_worker(entry.get("id"))
    return started, created, True


def _queue_and_maybe_wait(entry, prompt, wait=True, timeout=60.0, fmt="human",
                          source="instances.py send", metadata=None):
    if not prompt:
        raise ValueError("prompt required")
    job = queue_job(
        entry.get("id"),
        prompt,
        source=source,
        metadata=metadata or {},
    )
    if not wait:
        if fmt == "json":
            print(json.dumps(job, indent=2))
        else:
            print(f"queued {job['id']} -> {entry.get('id')}")
        return 0

    result = wait_for_job(entry.get("id"), job["id"], timeout_sec=timeout)
    if not result or result.get("status") not in {"completed", "failed"}:
        raise ValueError(f"timed out waiting for job: {job['id']}")
    if fmt == "json":
        print(json.dumps(result, indent=2))
    elif result.get("status") == "completed":
        print(result.get("result", ""))
    else:
        print(result.get("error", ""), file=sys.stderr)
        return 1
    return 0


def _print_instance(entry, active_id=None):
    marker = "*" if active_id and entry.get("id") == active_id else " "
    parent = entry.get("parent_instance_id") or "-"
    state = _entry_state(entry)
    pid = entry.get("worker_pid")
    pid_text = f" pid={pid}" if pid and pid_is_alive(pid) else ""
    print(
        f"{marker} {entry.get('id')}  "
        f"state={state}{pid_text}  "
        f"role={entry.get('role', DEFAULT_ROLE)}  "
        f"parent={parent}  "
        f"{_queue_suffix(entry)}"
    )


def _spawn_lock_path(instance_id):
    """Path to the per-instance spawn lock sentinel file."""
    return os.path.join(instance_root(instance_id), "spawn.lock")


def _open_spawn_lock(instance_id):
    """Create (if needed) and open the per-instance spawn lock with 0o600 perms.

    Ensures the parent runtime dir exists, then opens (or creates) the sentinel
    file with restrictive permissions. Returns an open file descriptor that the
    caller is responsible for closing.
    """
    lock_path = _spawn_lock_path(instance_id)
    parent = os.path.dirname(lock_path)
    os.makedirs(parent, exist_ok=True)
    # O_CREAT with mode 0o600 establishes restrictive perms on first creation.
    # If the file already exists, os.open won't widen perms — but enforce
    # 0o600 after open in case a prior process created it with different mode.
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
    except OSError:
        # Best-effort: chmod can fail on exotic filesystems; the lock still works.
        pass
    return fd


def _spawn_worker(instance_id):
    entry = get_instance(instance_id)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {instance_id}")
    # Fast path: already running. We re-check this inside the lock below to
    # close the TOCTOU window, but doing it here avoids the lock cost for the
    # common already-up case.
    if entry.get("worker_pid") and pid_is_alive(entry.get("worker_pid")):
        return entry, False

    # Serialize the spawn check + spawn + mark-started sequence with a per-
    # instance file lock. Two concurrent `start` calls would otherwise both
    # observe no live worker and both spawn a daemon for the same queue.
    lock_fd = _open_spawn_lock(instance_id)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another spawn is in flight for this instance. Bail out fast and
            # return whatever the registry currently shows; the in-flight
            # spawn will publish the live worker_pid shortly.
            print(
                f"another spawn in flight for {instance_id}; skipping",
                file=sys.stderr,
            )
            current = get_instance(instance_id) or entry
            return current, False

        # Re-check liveness now that we hold the lock. Use os.kill(pid, 0)
        # semantics via pid_is_alive: a stale-but-non-None pid (worker died
        # without mark_worker_stopped) must be treated as not-running so we
        # respawn rather than silently keeping the dead pid.
        current = get_instance(instance_id) or entry
        pid = current.get("worker_pid")
        if pid and pid_is_alive(pid):
            return current, False

        ensure_instance_control_dirs(instance_id)
        stdout = open(worker_stdout_log(instance_id), "a")
        stderr = open(worker_stderr_log(instance_id), "a")
        try:
            proc = subprocess.Popen(
                [sys.executable, _worker_script(), instance_id],
                cwd=REPO_ROOT,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
        finally:
            stdout.close()
            stderr.close()
        entry = mark_worker_started(instance_id, proc.pid)
        refresh_active_instance_doc()
        return entry, True
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(lock_fd)


def _ensure_target_instance(instance_id=None):
    target = instance_id or active_instance_id(prefer_env=False)
    if not target:
        raise ValueError("no active instance")
    entry = get_instance(target)
    if not entry:
        raise UnknownInstanceError(f"unknown instance: {target}")
    return entry


def cmd_list(_args):
    refresh_active_instance_doc()
    active_id = active_instance_id(prefer_env=False)
    entries = list_instances()
    if not entries:
        print("no managed instances")
        return 0
    for entry in entries:
        _print_instance(entry, active_id=active_id)
    return 0


def cmd_status(_args):
    refresh_active_instance_doc()
    active = current_instance(prefer_env=False)
    if not active:
        print("active_instance: none")
    else:
        snap = instance_status(active.get("id"))
        print(f"active_instance: {active.get('id')}")
        print(f"role: {active.get('role', DEFAULT_ROLE)}")
        print(f"state: {_entry_state(snap)}")
        if snap.get("worker_pid") and pid_is_alive(snap.get("worker_pid")):
            print(f"worker_pid: {snap.get('worker_pid')}")
        parent = active.get("parent_instance_id")
        if parent:
            print(f"parent_instance_id: {parent}")
    print("")
    return cmd_list(_args)


def cmd_create(args):
    entry = create_instance(
        name=args.name,
        role=args.role,
        source_instance_id=None,
        activate=False,
    )
    print(f"created {entry.get('id')} role={entry.get('role')}")
    if args.activate:
        started, new = _spawn_worker(entry.get("id"))
        print(
            f"started {started.get('id')} pid={started.get('worker_pid')}"
            + ("" if new else " (already running)")
        )
    return 0


def cmd_fork(args):
    source = args.source or active_instance_id(prefer_env=False)
    if not source:
        raise ValueError("fork requires a source instance or an active instance")
    entry = create_instance(
        name=args.name,
        role=args.role,
        source_instance_id=source,
        activate=False,
    )
    print(
        f"forked {entry.get('id')} from {source} "
        f"role={entry.get('role')}"
    )
    if args.activate:
        started, new = _spawn_worker(entry.get("id"))
        print(
            f"started {started.get('id')} pid={started.get('worker_pid')}"
            + ("" if new else " (already running)")
        )
    return 0


def cmd_start(args):
    entry = _resolve_instance_ref(args.instance_id)
    entry, created = _spawn_worker(entry.get("id"))
    print(
        f"started {entry.get('id')} pid={entry.get('worker_pid')}"
        + ("" if created else " (already running)")
    )
    return 0


def cmd_swap(args):
    entry = _resolve_instance_ref(args.instance_id)
    entry = swap_instance(entry.get("id"))
    refresh_active_instance_doc()
    state = _entry_state(entry)
    print(f"active_instance: {entry.get('id')}")
    print(f"state: {state}")
    return 0


def cmd_stop(args):
    entry = _resolve_instance_ref(args.instance_id) if args.instance_id else _ensure_target_instance(None)
    pid = entry.get("worker_pid")
    was_running = bool(pid and pid_is_alive(pid))
    if was_running:
        terminate_worker(entry.get("id"), pid)
    else:
        mark_worker_stopped(entry.get("id"))
    stopped = stop_instance(entry.get("id"))
    refresh_active_instance_doc()

    merge_summary = {"merged": 0, "skipped": 0, "lesson_ids": []}
    if not args.no_merge:
        merge_summary = merge_instance_semantic(entry.get("id"))

    print(f"stopped {stopped.get('id')}")
    if not args.no_merge:
        print(
            f"merged_lessons: {merge_summary['merged']} "
            f"(skipped={merge_summary['skipped']})"
        )
    return 0


def _prompt_from_args(args):
    return " ".join(args.prompt).strip() or sys.stdin.read().strip()


def cmd_send(args):
    entry = _resolve_instance_ref(args.instance) if args.instance else _ensure_target_instance(None)
    if not _is_live_worker(entry):
        raise ValueError(f"instance is not running: {entry.get('id')}")
    prompt = _prompt_from_args(args)
    return _queue_and_maybe_wait(
        entry,
        prompt,
        wait=args.wait,
        timeout=args.timeout,
        fmt=args.format,
        source="instances.py send",
        metadata={"wait": args.wait},
    )


def _resolve_fanout_targets(instance_ids):
    if instance_ids:
        targets = [_resolve_instance_ref(instance_id) for instance_id in instance_ids]
        return targets
    return running_instances()


def cmd_fanout(args):
    targets = _resolve_fanout_targets(args.instances)
    if not targets:
        raise ValueError("fanout requires at least one target instance")
    prompt = _prompt_from_args(args)
    if not prompt:
        raise ValueError("fanout requires a prompt")

    queued = []
    for entry in targets:
        if not (entry.get("worker_pid") and pid_is_alive(entry.get("worker_pid"))):
            raise ValueError(f"instance is not running: {entry.get('id')}")
        job = queue_job(
            entry.get("id"),
            prompt,
            source="instances.py fanout",
            metadata={"fanout": True},
        )
        queued.append({"instance_id": entry.get("id"), "job_id": job["id"]})

    if not args.wait:
        if args.format == "json":
            print(json.dumps({"queued": queued}, indent=2))
        else:
            for item in queued:
                print(f"queued {item['job_id']} -> {item['instance_id']}")
        return 0

    results = []
    exit_code = 0
    for item in queued:
        result = wait_for_job(
            item["instance_id"], item["job_id"], timeout_sec=args.timeout
        )
        if not result or result.get("status") not in {"completed", "failed"}:
            exit_code = 1
            results.append(
                {
                    "instance_id": item["instance_id"],
                    "job_id": item["job_id"],
                    "status": "timeout",
                }
            )
            continue
        results.append(result)
        if result.get("status") != "completed":
            exit_code = 1

    if args.format == "json":
        print(json.dumps({"results": results}, indent=2))
    else:
        for result in results:
            instance_id = result.get("instance_id", "?")
            status = result.get("status", "?")
            print(f"== {instance_id} [{status}] ==")
            if status == "completed":
                print(result.get("result", ""))
            else:
                print(result.get("error", ""))
            print("")
    return exit_code


def cmd_merge(args):
    entry = _resolve_instance_ref(args.instance_id) if args.instance_id else _ensure_target_instance(None)
    summary = merge_instance_semantic(entry.get("id"))
    print(
        f"merged_lessons: {summary['merged']} "
        f"(skipped={summary['skipped']})"
    )
    return 0


def cmd_up(args):
    role = (args.role or DEFAULT_ROLE).strip() or DEFAULT_ROLE
    entry = _pick_preferred(_entries_for_role(role))
    created = False
    worker_started = False
    if not entry:
        entry = create_instance(name=args.name or role, role=role, activate=False)
        created = True
    entry, _already_running, worker_started = _ensure_running(entry)
    print(f"role: {role}")
    print(f"instance: {entry.get('id')}")
    if created:
        print("action: created")
    elif worker_started:
        print("action: started")
    else:
        print("action: selected")
    return 0


def cmd_branch(args):
    source = None
    if args.source:
        source = _resolve_instance_ref(args.source, allow_missing=False)
    else:
        try:
            source = _ensure_target_instance(None)
        except ValueError:
            source = None

    role = (args.role or DEFAULT_ROLE).strip() or DEFAULT_ROLE
    entry = create_instance(
        name=args.name or role,
        role=role,
        source_instance_id=source.get("id") if source else None,
        activate=False,
    )
    entry, _created, _started = _ensure_running(entry)
    parent = source.get("id") if source else "shared"
    print(f"role: {role}")
    print(f"instance: {entry.get('id')}")
    print(f"forked_from: {parent}")
    return 0


def cmd_ask(args):
    if args.role and args.instance:
        raise ValueError("ask accepts either --role or --instance, not both")
    if args.role:
        entry = _pick_preferred(_entries_for_role(args.role))
        if not entry:
            entry = create_instance(name=args.role, role=args.role, activate=False)
    elif args.instance:
        entry = _resolve_instance_ref(args.instance)
    else:
        entry = _ensure_target_instance(None)
    entry, _created, _started = _ensure_running(entry)
    prompt = _prompt_from_args(args)
    return _queue_and_maybe_wait(
        entry,
        prompt,
        wait=not args.no_wait,
        timeout=args.timeout,
        fmt=args.format,
        source="instances.py ask",
        metadata={"wait": not args.no_wait, "role": args.role or ""},
    )


def _ensure_role_targets(roles):
    targets = []
    try:
        source = _ensure_target_instance(None)
    except ValueError:
        source = None
    for role in roles:
        entry = _pick_preferred(_entries_for_role(role))
        if not entry:
            entry = create_instance(
                name=role,
                role=role,
                source_instance_id=source.get("id") if source else None,
                activate=False,
            )
        entry, _created, _started = _ensure_running(entry)
        targets.append(entry)
    return targets


def cmd_compare(args):
    if not args.roles:
        raise ValueError("compare requires at least one role")
    prompt = _prompt_from_args(args)
    if not prompt:
        raise ValueError("compare requires a prompt")
    targets = _ensure_role_targets(args.roles)
    queued = []
    for entry in targets:
        job = queue_job(
            entry.get("id"),
            prompt,
            source="instances.py compare",
            metadata={"compare": True, "roles": args.roles},
        )
        queued.append({"instance_id": entry.get("id"), "job_id": job["id"]})

    results = []
    exit_code = 0
    for item in queued:
        result = wait_for_job(
            item["instance_id"], item["job_id"], timeout_sec=args.timeout
        )
        if not result or result.get("status") not in {"completed", "failed"}:
            exit_code = 1
            results.append(
                {
                    "instance_id": item["instance_id"],
                    "job_id": item["job_id"],
                    "status": "timeout",
                }
            )
            continue
        results.append(result)
        if result.get("status") != "completed":
            exit_code = 1

    if args.format == "json":
        print(json.dumps({"results": results}, indent=2))
    else:
        for result in results:
            print(f"== {result.get('instance_id', '?')} [{result.get('status', '?')}] ==")
            if result.get("status") == "completed":
                print(result.get("result", ""))
            else:
                print(result.get("error", ""))
            print("")
    return exit_code


def cmd_down(args):
    args.instance_id = args.target
    return cmd_stop(args)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manage standalone agent instances."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="List managed instances.")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("status", help="Show the active instance and registry.")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser(
        "up",
        help="Role-first shortcut: create/start/select the latest instance for a role.",
    )
    p.add_argument("role", help="Role label, for example reviewer or qa.")
    p.add_argument("--name", help="Optional human-readable instance name.")
    p.set_defaults(func=cmd_up)

    p = sub.add_parser(
        "branch",
        help="Role-first shortcut: fork from the active route into a new role branch and start it.",
    )
    p.add_argument("role", help="Role label for the new branch.")
    p.add_argument(
        "--source",
        help="Optional source instance id, name, or role. Defaults to the active route.",
    )
    p.add_argument("--name", help="Optional human-readable instance name.")
    p.set_defaults(func=cmd_branch)

    p = sub.add_parser(
        "ask",
        help="Role-first shortcut: send a prompt to the active or named role and wait.",
    )
    p.add_argument("prompt", nargs="*")
    p.add_argument("--role", help="Target a role and auto-start it if needed.")
    p.add_argument(
        "--instance",
        help="Target an instance id, name, or role instead of the active route.",
    )
    p.add_argument("--no-wait", action="store_true", help="Queue the job and return immediately.")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--format", default="human", choices=["human", "json"])
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser(
        "compare",
        help="Role-first shortcut: ensure roles are running, then fan out one prompt to all of them.",
    )
    p.add_argument("prompt", nargs="*")
    p.add_argument("--roles", nargs="+", required=True, help="Role labels to compare.")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--format", default="human", choices=["human", "json"])
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser(
        "down",
        help="Role-first shortcut: stop the active route or a named role/instance.",
    )
    p.add_argument("target", nargs="?", help="Optional instance id, name, or role.")
    p.add_argument(
        "--no-merge",
        action="store_true",
        help="Do not merge accepted local lessons back into shared semantic memory.",
    )
    p.set_defaults(func=cmd_down)

    p = sub.add_parser("create", help="Create a new instance from shared memory.")
    p.add_argument("name", nargs="?", help="Human-readable instance name.")
    p.add_argument("--role", default=DEFAULT_ROLE, help="Role label for the instance.")
    p.add_argument(
        "--activate", action="store_true", help="Start the instance worker immediately."
    )
    p.set_defaults(func=cmd_create)

    p = sub.add_parser(
        "fork",
        help="Fork an instance's working/episodic state into a new instance.",
    )
    p.add_argument(
        "source",
        nargs="?",
        help="Source instance id. Defaults to the active instance.",
    )
    p.add_argument("--name", help="Human-readable instance name.")
    p.add_argument(
        "--role",
        default=None,
        help="Role label for the fork. Defaults to the source instance's role.",
    )
    p.add_argument(
        "--activate", action="store_true", help="Start the new fork's worker immediately."
    )
    p.set_defaults(func=cmd_fork)

    p = sub.add_parser("start", help="Start an instance worker and select it as active.")
    p.add_argument("instance_id")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("swap", help="Swap the active route to a different instance.")
    p.add_argument("instance_id")
    p.set_defaults(func=cmd_swap)

    p = sub.add_parser("stop", help="Stop an instance worker.")
    p.add_argument("instance_id", nargs="?")
    p.add_argument(
        "--no-merge",
        action="store_true",
        help="Do not merge accepted local lessons back into shared semantic memory.",
    )
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("send", help="Queue a prompt to a running instance.")
    p.add_argument("prompt", nargs="*")
    p.add_argument(
        "--instance",
        help="Target a specific instance id. Defaults to the active route.",
    )
    p.add_argument("--wait", action="store_true", help="Wait for the queued job to finish.")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--format", default="human", choices=["human", "json"])
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("fanout", help="Queue the same prompt to multiple running instances.")
    p.add_argument("prompt", nargs="*")
    p.add_argument(
        "--instances",
        nargs="*",
        default=None,
        help="Explicit instance ids. Defaults to all running instances.",
    )
    p.add_argument("--wait", action="store_true", help="Wait for all jobs to finish.")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--format", default="human", choices=["human", "json"])
    p.set_defaults(func=cmd_fanout)

    p = sub.add_parser("merge", help="Merge accepted local lessons into shared semantic memory.")
    p.add_argument("instance_id", nargs="?")
    p.set_defaults(func=cmd_merge)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (UnknownInstanceError, ValueError) as e:
        parser.exit(1, f"error: {e}\n")


if __name__ == "__main__":
    raise SystemExit(main())
