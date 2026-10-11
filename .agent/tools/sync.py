"""Cross-device memory sync over the project's own git remote.

    python3 .agent/tools/sync.py            # commit memory/skills/knowledge, pull --rebase, push
    python3 .agent/tools/sync.py --dry-run  # show what would happen
    python3 .agent/tools/sync.py --no-push  # commit + pull only

Only the portable-brain paths are staged (memory, skills, playbooks,
personas, protocols/agents.json). Never force-pushes; refuses when the
working tree has unrelated staged changes so it cannot sweep your work into
a "memory sync" commit. Any device signed into the same remote draws from
the same brain after `git pull`.
"""
import argparse
import datetime
import os
import socket
import subprocess
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cli import CliError, add_format_arg, run as cli_run  # noqa: E402

SYNC_PATHS = [".agent/memory", ".agent/skills", ".agent/playbooks", ".agent/personas", ".agent/protocols/agents.json"]


def _git(args, cwd, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise CliError("io", f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()[:300]}")
    return r


def sync(project_root=None, remote="origin", dry_run=False, push=True, message=None):
    root = project_root or os.path.dirname(BASE)
    if _git(["rev-parse", "--is-inside-work-tree"], root, check=False).returncode != 0:
        raise CliError("invalid_args", f"{root} is not a git repository")
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], root).stdout.strip()
    staged = _git(["diff", "--cached", "--name-only"], root).stdout.split()
    foreign = [p for p in staged if not any(p == s or p.startswith(s.rstrip("/") + "/") for s in SYNC_PATHS)]
    if foreign:
        raise CliError("conflict", "index has unrelated staged changes; commit or unstage them first",
                       detail={"staged": foreign[:10]})
    existing = [p for p in SYNC_PATHS if os.path.exists(os.path.join(root, p))]
    changed = _git(["status", "--porcelain", "--", *existing], root).stdout.splitlines() if existing else []
    message = message or f"memory: sync from {socket.gethostname()} {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M}Z"
    plan = {"branch": branch, "remote": remote, "changed": [c.strip() for c in changed], "commit": bool(changed),
            "pull": True, "push": push, "message": message}
    if dry_run:
        return dict(plan, dry_run=True)
    if changed:
        _git(["add", "--", *existing], root)
        _git(["commit", "-m", message], root)
        plan["commit_sha"] = _git(["rev-parse", "--short", "HEAD"], root).stdout.strip()
    has_remote = _git(["remote", "get-url", remote], root, check=False).returncode == 0
    has_upstream = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root, check=False).returncode == 0
    plan["pull"] = has_remote and has_upstream
    if plan["pull"]:
        r = _git(["pull", "--rebase", remote, branch], root, check=False)
        if r.returncode != 0:
            _git(["rebase", "--abort"], root, check=False)
            raise CliError("conflict", "pull --rebase hit a conflict; aborted rebase, nothing lost",
                           hint="resolve manually: git pull --rebase " + remote + " " + branch)
    if push and has_remote:
        r = _git(["push", remote, branch], root, check=False)
        if r.returncode != 0:
            raise CliError("network", f"push failed: {(r.stderr or r.stdout).strip()[:300]}")
    else:
        plan["push"] = False
    return plan


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_format_arg(p)
    p.add_argument("--remote", default="origin")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-push", action="store_true")
    p.add_argument("--message")
    p.add_argument("--project-root", default=None, help=argparse.SUPPRESS)
    ns = p.parse_args(argv)

    def go():
        r = sync(ns.project_root, remote=ns.remote, dry_run=ns.dry_run, push=not ns.no_push, message=ns.message)
        text = (f"branch={r['branch']} changed={len(r['changed'])} commit={r.get('commit_sha') or r['commit']} "
                f"pull={r['pull']} push={r['push']}" + (" (dry-run)" if r.get("dry_run") else ""))
        return r, None, text
    return cli_run(go, fmt=ns.format)


if __name__ == "__main__":
    sys.exit(main())
