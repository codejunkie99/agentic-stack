#!/usr/bin/env python3
"""Fold a dependent ticket branch into the branch that carries its files.

Identifier: fold-branch
Version: 1.0.0
Owner: portable-brain
Provenance: extracted from DDI-1035, where the portal half of one work item could
            only edit files that an unmerged DDI-704 branch introduced. The fold
            was done by hand: soft reset, commit -C, tree-hash comparison, then a
            deletion held back until the receiving push landed. Every one of those
            steps is deterministic and every one of them is easy to get wrong in
            an order that loses a commit.

Purpose
    A work item sometimes has to change files that exist only on another, still
    unmerged branch. A branch cut from the base cannot edit a file the base does
    not have. The change therefore rides on the branch that introduces the files.
    This tool decides whether that is the case, performs the fold so the carrier
    keeps exactly one commit, and proves by tree hash that the folded tree equals
    the tree that already passed the quality gate.

Responsibility boundary
    This tool rewrites LOCAL refs only. It never pushes and never deletes a remote
    branch. `create-ticket-pr` owns the surrounding judgment: whether folding is
    the right call at all, and how the plan records owner against carrier.

Commands
    check <carrier> <source>
        Read-only. Classifies the source commits against the base and prints the
        verdict. Run this before deciding.

    fold <carrier> <source>
        Rewrites the local carrier ref to one commit holding the source tree.
        Prints the push and delete commands. Runs neither.

    verify <carrier> <source>
        Read-only. Confirms the remote carrier holds the folded commit. Until it
        does, deleting the remote source branch would drop the only remote copy
        of the work. Exits 3 while that is true.

Typed inputs
    carrier   str, branch that introduces the files and receives the fold
    source    str, dependent branch whose commits are folded in
    --base    str, default "origin/dev", the branch both target
    --remote  str, default "origin", verify only
    --repo    str, default ".", path to the git worktree
    --json    flag, machine-readable output

Outputs
    Human report on stdout, or one JSON object with --json.

Side effects
    `check` and `verify`: none.
    `fold`: moves HEAD and the local carrier ref. Permission class: local-write.
    The pre-fold commit stays reachable through the reflog.

Idempotency
    `check` and `verify` are pure. `fold` refuses to run a second time, because
    after a successful fold the source is no longer ahead of the carrier.

Failure exit codes
    0 success
    2 usage error or unmet precondition, nothing was changed
    3 unsafe to delete the remote source branch
    4 git invocation failed

Secrets
    Reads no credentials and prints none.

Platforms
    Any platform with git 2.23 or later and Python 3.9 or later. No dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

EXIT_OK = 0
EXIT_PRECONDITION = 2
EXIT_UNSAFE = 3
EXIT_GIT = 4


class GitError(RuntimeError):
    """A git command failed."""


def git(repo: str, *args: str) -> str:
    """Run one git command and return stripped stdout, or raise GitError."""
    proc = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def rev(repo: str, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")


def tree_of(repo: str, ref: str) -> str:
    return git(repo, "rev-parse", f"{ref}^{{tree}}")


def count(repo: str, a: str, b: str) -> int:
    """Number of commits reachable from b but not from a."""
    return int(git(repo, "rev-list", "--count", f"{a}..{b}"))


def files_touched(repo: str, a: str, b: str) -> list[str]:
    out = git(repo, "diff", "--name-only", f"{a}..{b}")
    return [line for line in out.splitlines() if line]


def exists_on(repo: str, ref: str, path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", repo, "cat-file", "-e", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def tracked_dirty(repo: str) -> list[str]:
    out = git(repo, "status", "--porcelain", "--untracked-files=no")
    return [line for line in out.splitlines() if line]


def in_progress_merge(repo: str) -> str | None:
    """Name the in-progress operation that makes any ref rewrite unsafe."""
    git_dir = git(repo, "rev-parse", "--git-dir")
    root = repo if os.path.isabs(git_dir) else repo
    for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD"):
        path = git(repo, "rev-parse", "--git-path", marker)
        if not os.path.isabs(path):
            path = os.path.join(root, path)
        if os.path.exists(path):
            return marker
    return None


def classify(repo: str, base: str, carrier: str, source: str) -> dict:
    """Decide whether the source commits can live anywhere but the carrier."""
    if count(repo, carrier, source) == 0:
        raise GitError(f"{source} is not ahead of {carrier}; there is nothing to fold")
    if count(repo, source, carrier) != 0:
        raise GitError(f"{carrier} has commits {source} does not; rebase before folding")

    touched = files_touched(repo, carrier, source)
    on_base = [p for p in touched if exists_on(repo, base, p)]
    only_on_carrier = [p for p in touched if p not in on_base]

    if not touched:
        verdict = "empty"
        reason = "the source commits change no file"
    elif not on_base:
        verdict = "fold-required"
        reason = (
            f"every changed file is absent from {base}, so a branch cut from "
            f"{base} could not edit them"
        )
    elif not only_on_carrier:
        verdict = "fold-optional"
        reason = (
            f"every changed file already exists on {base}, so the source can "
            f"stand as its own branch"
        )
    else:
        verdict = "mixed"
        reason = (
            "some changed files exist on the base and some do not; split the "
            "commit before folding so each half has one owner"
        )

    return {
        "base": base,
        "baseSha": rev(repo, base),
        "carrier": carrier,
        "carrierSha": rev(repo, carrier),
        "source": source,
        "sourceSha": rev(repo, source),
        "carrierCommitsAboveBase": count(repo, base, carrier),
        "sourceCommitsAboveCarrier": count(repo, carrier, source),
        "filesTouched": touched,
        "filesOnBase": on_base,
        "filesOnlyOnCarrier": only_on_carrier,
        "verdict": verdict,
        "reason": reason,
    }


def do_check(repo: str, base: str, carrier: str, source: str) -> tuple[int, dict]:
    return EXIT_OK, classify(repo, base, carrier, source)


def do_fold(repo: str, base: str, carrier: str, source: str) -> tuple[int, dict]:
    info = classify(repo, base, carrier, source)

    blocking = in_progress_merge(repo)
    if blocking:
        raise GitError(f"a {blocking} is in progress; finish or abort it before folding")
    dirty = tracked_dirty(repo)
    if dirty:
        raise GitError(f"{len(dirty)} tracked file(s) are modified; commit or stash first")
    if info["verdict"] == "empty":
        raise GitError("nothing to fold")
    if info["carrierCommitsAboveBase"] != 1:
        raise GitError(
            f"{carrier} is {info['carrierCommitsAboveBase']} commits above {base}; "
            f"a ticket branch must be one commit. Squash it before folding."
        )
    head = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if rev(repo, "HEAD") != info["sourceSha"]:
        raise GitError(f"HEAD is {head}, not {source}; check out {source} first")

    want_tree = tree_of(repo, source)
    carrier_sha = info["carrierSha"]

    git(repo, "reset", "--soft", info["baseSha"])
    git(repo, "commit", "-C", carrier_sha, "--no-verify", "--quiet")

    folded = rev(repo, "HEAD")
    got_tree = tree_of(repo, "HEAD")
    if got_tree != want_tree:
        raise GitError(
            f"folded tree {got_tree} does not equal the source tree {want_tree}; "
            f"the carrier ref was not moved. Recover with: git reset --hard {info['sourceSha']}"
        )
    if count(repo, base, "HEAD") != 1:
        raise GitError(f"the folded branch is not one commit above {base}")

    git(repo, "branch", "--force", carrier, folded)

    info.update(
        {
            "foldedSha": folded,
            "foldedTree": got_tree,
            "treeMatchesSourceTree": True,
            "previousCarrierSha": carrier_sha,
            "nextCommands": [
                f"git push --force-with-lease=refs/heads/{carrier}:{carrier_sha} "
                f"origin {carrier}",
                f"git push origin --delete {source}",
                f"git branch -D {source}",
            ],
        }
    )
    return EXIT_OK, info


def do_verify(repo: str, base: str, carrier: str, source: str, remote: str) -> tuple[int, dict]:
    local_carrier = rev(repo, carrier)
    try:
        remote_carrier = rev(repo, f"{remote}/{carrier}")
    except GitError:
        remote_carrier = None
    try:
        remote_source = rev(repo, f"{remote}/{source}")
    except GitError:
        remote_source = None

    pushed = remote_carrier == local_carrier
    result = {
        "carrier": carrier,
        "localCarrierSha": local_carrier,
        "remoteCarrierSha": remote_carrier,
        "remoteSourceSha": remote_source,
        "carrierPushed": pushed,
        "safeToDeleteRemoteSource": pushed,
        "reason": (
            "the remote carrier holds the folded commit, so the remote source "
            "branch is no longer the only remote copy"
            if pushed
            else "the remote carrier does not hold the folded commit yet; deleting "
            "the remote source branch now would drop the only remote copy"
        ),
    }
    if remote_source is None:
        result["reason"] = "the remote source branch is already gone"
    return (EXIT_OK if pushed else EXIT_UNSAFE), result


def render(command: str, data: dict) -> str:
    lines: list[str] = []
    if command == "verify":
        lines.append(f"carrier            {data['carrier']}")
        lines.append(f"local carrier      {(data['localCarrierSha'] or '-')[:7]}")
        lines.append(f"remote carrier     {(data['remoteCarrierSha'] or '-')[:7]}")
        lines.append(f"remote source      {(data['remoteSourceSha'] or '-')[:7]}")
        lines.append("")
        verdict = "SAFE" if data["safeToDeleteRemoteSource"] else "UNSAFE"
        lines.append(f"delete remote source: {verdict}")
        lines.append(f"  {data['reason']}")
        return "\n".join(lines)

    lines.append(f"base               {data['base']} {data['baseSha'][:7]}")
    lines.append(f"carrier            {data['carrier']} {data['carrierSha'][:7]}"
                 f" ({data['carrierCommitsAboveBase']} above base)")
    lines.append(f"source             {data['source']} {data['sourceSha'][:7]}"
                 f" ({data['sourceCommitsAboveCarrier']} above carrier)")
    lines.append("")
    lines.append(f"files changed      {len(data['filesTouched'])}")
    lines.append(f"  absent from base {len(data['filesOnlyOnCarrier'])}")
    lines.append(f"  present on base  {len(data['filesOnBase'])}")
    for path in data["filesOnBase"]:
        lines.append(f"    {path}")
    lines.append("")
    lines.append(f"verdict            {data['verdict']}")
    lines.append(f"  {data['reason']}")

    if "foldedSha" in data:
        lines.append("")
        lines.append(f"folded             {data['foldedSha'][:7]}")
        lines.append(f"  tree {data['foldedTree'][:7]} equals the source tree, so gate "
                     f"evidence recorded against {data['sourceSha'][:7]} still holds")
        lines.append("")
        lines.append("Run these in order. This tool runs neither.")
        for cmd in data["nextCommands"]:
            lines.append(f"  {cmd}")
        lines.append("")
        lines.append("Do not run the delete commands until "
                     "`fold_branch.py verify` reports SAFE.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fold a dependent ticket branch into the branch carrying its files",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("check", "classify the source commits against the base, read-only"),
        ("fold", "rewrite the local carrier ref to one commit holding the source tree"),
        ("verify", "confirm the remote carrier holds the folded commit"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("carrier")
        p.add_argument("source")
        p.add_argument("--base", default="origin/dev")
        p.add_argument("--remote", default="origin")
        p.add_argument("--repo", default=".")
        p.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            code, data = do_check(args.repo, args.base, args.carrier, args.source)
        elif args.command == "fold":
            code, data = do_fold(args.repo, args.base, args.carrier, args.source)
        else:
            code, data = do_verify(
                args.repo, args.base, args.carrier, args.source, args.remote
            )
    except GitError as exc:
        print(f"fold-branch: {exc}", file=sys.stderr)
        return EXIT_PRECONDITION
    except ValueError as exc:
        print(f"fold-branch: {exc}", file=sys.stderr)
        return EXIT_GIT

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(render(args.command, data))
    return code


if __name__ == "__main__":
    sys.exit(main())
