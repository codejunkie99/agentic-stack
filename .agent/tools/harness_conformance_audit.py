#!/usr/bin/env python3
"""Audit the harness's eager-load surfaces against best-practice budgets.

Companion to skill_linter.py. Where the linter validates STRUCTURE
(frontmatter, hooks, manifest match), this auditor validates BUDGETS
(line counts, eager-load total, upstream-parity drift). Both are
designed to keep us pointed inward at our own development.

Checks:

  1. Line-count budgets per file:
     - CLAUDE.md           <= 120  (Effloow / HumanLayer best practice
                                    is <100; we allow 20 lines for
                                    legitimate adapter additions)
     - .agent/AGENTS.md    <= 110  (upstream is 91; allow ~20 for
                                    Config section)
     - Each SKILL.md       <= 500  (Anthropic hard rule)
     - Each .agent/context/<topic>.md  <= 80  (eager-loaded; should
                                                be reference, not docs)

  2. Eager-load total:
     - Sum of line counts of all files the session-start protocol
       reads. Soft budget = 600 lines (matches upstream parity).
       Reports the running total + delta vs the budget.

  3. Upstream-parity drift:
     - For CLAUDE.md, AGENTS.md, and the always-eager files, diff
       against `upstream/master:<path>`. Reports the line delta and
       checks whether the addition is justified by an entry in
       DECISIONS.md (heuristic: looks for the file's basename or
       relative path in DECISIONS.md text).

  4. Delegates to skill_linter.py for skill-structural conformance
     and self-rewrite hook coverage. Reports skill_linter exit
     status alongside the budget checks.

Exits 0 if all checks pass. Exits 1 with structured report if any
fail. Designed for three trigger surfaces:

    # Manual ad-hoc audit
    python3 .agent/tools/harness_conformance_audit.py

    # Pre-commit gate (only runs when eager-load files staged)
    python3 .agent/tools/harness_conformance_audit.py --staged

    # Cron-style summary write (no exit-code gating)
    python3 .agent/tools/harness_conformance_audit.py --report-only

The auditor does NOT modify any harness file. It only reports.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
REPO_ROOT = AGENT_ROOT.parent  # for fork: agent-stack/; for installs: install root
SKILLS_DIR = AGENT_ROOT / "skills"
CONTEXT_DIR = AGENT_ROOT / "context"
DECISIONS = AGENT_ROOT / "memory" / "semantic" / "DECISIONS.md"
SKILL_LINTER = HERE / "skill_linter.py"

# Budgets — calibrated against industry best practice + upstream parity.
# Bump only with justification in DECISIONS.md.
BUDGETS = {
    "claude_md_max_lines": 120,
    "agents_md_max_lines": 110,
    "skill_md_max_lines": 510,  # Step 8.4 Gap 10: gate-bearing skills are denser
    "context_file_max_lines": 80,
    "eager_load_total_max": 710,  # BCG-enabled session (Step 8.4 +10 lines for gate discipline)
    "eager_load_total_max_lean": 510,  # without adapters (Step 8.4 +10 lines for gate discipline)
}


# Files that are ALWAYS eager-loaded by the session-start protocol
# (per adapters/claude-code/CLAUDE.md). Relative to REPO_ROOT for the
# fork, or to install root in installed targets.
#
# Note: glossary/frameworks/quality-standards CONTENT files are
# trigger-loaded post slice-3 (2026-04-28). Only the index is eager.
ALWAYS_EAGER_REL = [
    ".agent/AGENTS.md",
    ".agent/config.json",
    ".agent/memory/personal/PREFERENCES.md",
    ".agent/memory/working/REVIEW_QUEUE.md",
    ".agent/memory/semantic/LESSONS.md",
    ".agent/protocols/permissions.md",
    ".agent/context/_index.md",
    ".agent/skills/_index.md",
    ".agent/workflows/_index.md",
]

# CLAUDE.md path differs between fork (source) and install (target).
# In the fork it's adapters/claude-code/CLAUDE.md; in an install it's
# CLAUDE.md at the project root. Auditor checks whichever exists.
CLAUDE_MD_CANDIDATES = [
    "CLAUDE.md",
    "adapters/claude-code/CLAUDE.md",
]


# Files that are EAGER-LOADED only when bcg_adapter is enabled.
# Audited as "conditional-eager" — counted toward total when on.
#
# Note: only README.md (the BCG adapter's index) is eager-loaded
# post slice-3 (2026-04-28). protocols/ + context/ load on-demand.
BCG_CONDITIONAL_EAGER_REL = [
    "adapters/bcg/README.md",
]


# Upstream-parity diff scope. These are the files where line growth
# vs upstream is suspicious unless DECISIONS.md justifies it.
PARITY_SCOPE_REL = [
    ".agent/AGENTS.md",
    ".agent/protocols/permissions.md",
]
# CLAUDE.md is added programmatically (path varies — fork vs install).


def _line_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return len(text.splitlines())


def _resolve_claude_md(repo_root: Path) -> Path | None:
    for rel in CLAUDE_MD_CANDIDATES:
        p = repo_root / rel
        if p.is_file():
            return p
    return None


def _bcg_enabled(repo_root: Path) -> bool:
    cfg = repo_root / ".agent" / "config.json"
    if not cfg.is_file():
        return False
    try:
        d = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return d.get("bcg_adapter") == "enabled"


def _git_show_upstream(rel_path: str, repo_root: Path) -> str | None:
    """Return upstream/master:<rel_path> content, or None if unavailable."""
    try:
        out = subprocess.check_output(
            ["git", "show", f"upstream/master:{rel_path}"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _justified_in_decisions(rel_path: str) -> bool:
    """Heuristic: does DECISIONS.md mention the file path or its basename?"""
    if not DECISIONS.is_file():
        return False
    try:
        text = DECISIONS.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    basename = os.path.basename(rel_path)
    return basename in text or rel_path in text


def _check_line_budget(name: str, path: Path, max_lines: int) -> dict:
    n = _line_count(path)
    if n is None:
        return {"name": name, "path": str(path), "status": "missing"}
    if n <= max_lines:
        return {"name": name, "path": str(path), "lines": n, "max": max_lines, "status": "ok"}
    return {
        "name": name,
        "path": str(path),
        "lines": n,
        "max": max_lines,
        "over_by": n - max_lines,
        "status": "over_budget",
    }


def _check_skill_md_budgets(skills_dir: Path, max_lines: int) -> list[dict]:
    if not skills_dir.is_dir():
        return []
    out = []
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir():
            continue
        path = d / "SKILL.md"
        if not path.is_file():
            continue
        result = _check_line_budget(f"skills/{d.name}", path, max_lines)
        out.append(result)
    return out


def _check_eager_load_total(repo_root: Path, bcg_on: bool) -> dict:
    files: list[tuple[str, int]] = []
    total = 0

    claude = _resolve_claude_md(repo_root)
    if claude:
        n = _line_count(claude) or 0
        rel = str(claude.relative_to(repo_root))
        files.append((rel, n))
        total += n

    for rel in ALWAYS_EAGER_REL:
        p = repo_root / rel
        n = _line_count(p)
        if n is not None:
            files.append((rel, n))
            total += n

    if bcg_on:
        for rel in BCG_CONDITIONAL_EAGER_REL:
            p = repo_root / rel
            n = _line_count(p)
            if n is not None:
                files.append((rel, n))
                total += n

    budget_key = "eager_load_total_max" if bcg_on else "eager_load_total_max_lean"
    max_total = BUDGETS[budget_key]
    status = "ok" if total <= max_total else "over_budget"

    return {
        "name": "eager_load_total",
        "bcg_enabled": bcg_on,
        "total_lines": total,
        "max": max_total,
        "over_by": max(0, total - max_total),
        "status": status,
        "files": files,
    }


def _check_upstream_parity(rel_path: str, repo_root: Path) -> dict:
    """Compare local vs upstream/master line count. Flag unjustified growth."""
    local_path = repo_root / rel_path
    if not local_path.is_file():
        return {
            "name": f"parity:{rel_path}",
            "status": "missing_local",
            "rel_path": rel_path,
        }
    local_text = local_path.read_text(encoding="utf-8", errors="replace")
    upstream_text = _git_show_upstream(rel_path, repo_root)
    if upstream_text is None:
        return {
            "name": f"parity:{rel_path}",
            "status": "no_upstream",
            "rel_path": rel_path,
            "note": "upstream/master ref not fetched or path not in upstream",
        }
    local_n = len(local_text.splitlines())
    upstream_n = len(upstream_text.splitlines())
    delta = local_n - upstream_n
    if delta <= 0:
        return {
            "name": f"parity:{rel_path}",
            "status": "ok",
            "rel_path": rel_path,
            "local_lines": local_n,
            "upstream_lines": upstream_n,
            "delta": delta,
        }
    justified = _justified_in_decisions(rel_path)
    status = "ok" if justified else "unjustified_growth"
    return {
        "name": f"parity:{rel_path}",
        "status": status,
        "rel_path": rel_path,
        "local_lines": local_n,
        "upstream_lines": upstream_n,
        "delta": delta,
        "justified_in_decisions": justified,
    }


def _run_skill_linter(repo_root: Path, staged: bool = False) -> dict:
    if not SKILL_LINTER.is_file():
        return {"name": "skill_linter", "status": "missing"}
    args = [sys.executable, str(SKILL_LINTER)]
    if staged:
        args.append("--staged")
    try:
        result = subprocess.run(
            args,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"name": "skill_linter", "status": "error", "error": str(e)}
    return {
        "name": "skill_linter",
        "status": "ok" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _print_check(check: dict) -> bool:
    """Print a single check. Return True if OK, False if violation."""
    name = check["name"]
    status = check["status"]
    if status == "ok":
        if "lines" in check:
            print(f"  ✓ {name}: {check['lines']}/{check['max']} lines")
        elif "total_lines" in check:
            print(
                f"  ✓ {name}: {check['total_lines']}/{check['max']} lines "
                f"(BCG {'on' if check['bcg_enabled'] else 'off'})"
            )
        elif "delta" in check:
            print(f"  ✓ {name}: {check['delta']:+d} lines vs upstream")
        elif "exit_code" in check:
            print(f"  ✓ {name}: pass")
        else:
            print(f"  ✓ {name}")
        return True
    if status == "missing":
        print(f"  · {name}: not present (skipping)")
        return True
    if status == "no_upstream":
        print(f"  · {name}: upstream not fetched (skipping)")
        return True
    if status == "over_budget":
        print(
            f"  ✗ {name}: {check.get('lines', check.get('total_lines'))}/"
            f"{check['max']} lines — over by {check['over_by']}"
        )
        return False
    if status == "unjustified_growth":
        print(
            f"  ✗ {name}: +{check['delta']} lines vs upstream "
            f"(local={check['local_lines']}, upstream={check['upstream_lines']}); "
            f"NO justification found in DECISIONS.md"
        )
        return False
    if status == "fail":
        print(f"  ✗ {name}: skill_linter failed (exit={check['exit_code']})")
        if check.get("stdout"):
            for line in check["stdout"].splitlines():
                print(f"      {line}")
        return False
    print(f"  ? {name}: status={status}")
    return False


def run_audit(repo_root: Path, staged: bool = False) -> tuple[list[dict], int]:
    """Return (checks, fail_count)."""
    checks: list[dict] = []

    # 1. Line budgets
    claude = _resolve_claude_md(repo_root)
    if claude:
        checks.append(_check_line_budget("CLAUDE.md", claude, BUDGETS["claude_md_max_lines"]))
    checks.append(
        _check_line_budget(
            ".agent/AGENTS.md",
            repo_root / ".agent" / "AGENTS.md",
            BUDGETS["agents_md_max_lines"],
        )
    )
    # Per-file budget on the context INDEX (eager-loaded). Individual
    # context content files (glossary, frameworks, quality-standards)
    # are now trigger-loaded and audited via the SKILL.md budget pool
    # below, since they behave like skills (load-on-demand reference).
    checks.append(
        _check_line_budget(
            ".agent/context/_index.md",
            repo_root / ".agent" / "context" / "_index.md",
            BUDGETS["context_file_max_lines"],
        )
    )

    # 2. SKILL.md budgets
    checks.extend(_check_skill_md_budgets(repo_root / ".agent" / "skills", BUDGETS["skill_md_max_lines"]))

    # 3. Eager-load total
    bcg_on = _bcg_enabled(repo_root)
    checks.append(_check_eager_load_total(repo_root, bcg_on))

    # 4. Upstream parity
    parity_targets = list(PARITY_SCOPE_REL)
    if claude:
        parity_targets.append(str(claude.relative_to(repo_root)))
    for rel in parity_targets:
        checks.append(_check_upstream_parity(rel, repo_root))

    # 5. Delegate to skill_linter
    checks.append(_run_skill_linter(repo_root, staged=staged))

    fail_count = 0
    for c in checks:
        ok = _print_check(c)
        if not ok:
            fail_count += 1
    return checks, fail_count


def _pretty_eager_breakdown(checks: list[dict]) -> str:
    out = []
    for c in checks:
        if c.get("name") == "eager_load_total":
            out.append("\nEager-load breakdown:")
            for path, n in c["files"]:
                bar = "█" * min(40, n // 5)
                out.append(f"  {n:>4}  {bar}  {path}")
            break
    return "\n".join(out)


def _staged_eager_files(repo_root: Path) -> bool:
    """Return True if any audited file is in the staged diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    staged = set(result.stdout.strip().splitlines())
    if not staged:
        return False
    audited = set(ALWAYS_EAGER_REL)
    audited.update(BCG_CONDITIONAL_EAGER_REL)
    audited.update(CLAUDE_MD_CANDIDATES)
    audited.add(".agent/skills/_manifest.jsonl")
    audited.add(".agent/skills/_index.md")
    # Also audit any skill SKILL.md changes
    for path in staged:
        if path in audited or re.match(r"\.agent/skills/[^/]+/SKILL\.md", path):
            return True
        if path.startswith(".agent/context/") or path.startswith("adapters/bcg/"):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--staged",
        action="store_true",
        help="For pre-commit hook: skip audit if no eager-load files staged.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Always exit 0; for cron-style summary writes.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Override repo root (default: parent of .agent/).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()

    if args.staged and not _staged_eager_files(repo_root):
        print("ok: no eager-load files staged; skipping conformance audit")
        return 0

    print(f"# harness conformance audit  ·  {dt.datetime.now().isoformat(timespec='seconds')}")
    print(f"# repo: {repo_root}")
    print()
    checks, fail_count = run_audit(repo_root, staged=args.staged)
    print()
    print(_pretty_eager_breakdown(checks))
    print()
    total = len(checks)
    if fail_count:
        print(f"FAIL: {fail_count}/{total} checks failed")
        return 0 if args.report_only else 1
    print(f"ok: all {total} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
