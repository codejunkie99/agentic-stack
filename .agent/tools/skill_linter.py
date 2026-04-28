#!/usr/bin/env python3
"""Validate every .agent/skills/<name>/SKILL.md against the harness skill template.

Checks four kinds of conformance:

  1. **Frontmatter shape.** Each SKILL.md opens with a YAML frontmatter
     block bounded by `---`. Required keys: `name`, `version`, `triggers`.
     Optional but expected: `tools`, `preconditions`, `constraints`,
     `description`.

  2. **Self-rewrite hook present.** Every skill must include a
     "## Self-rewrite hook" section near the bottom (anywhere after
     line 20). This is the convention from the skillforge skill —
     "always include self-rewrite hook" — without which the skill
     cannot self-improve from episodic patterns.

  3. **Manifest entry exists and matches.** The skill directory name
     must appear as a `name` value in `.agent/skills/_manifest.jsonl`.
     The manifest entry must be valid JSON. Triggers in the manifest
     must match the SKILL.md frontmatter triggers.

  4. **Index entry exists.** The skill name must appear as a `## <name>`
     header in `.agent/skills/_index.md`.

Exits 0 if all skills pass. Exits 1 with a structured report if any
fail. Designed to be wired as a pre-commit hook (only runs when
`.agent/skills/` is touched in a commit) but also usable as a standalone
audit tool.

Usage:

    # Full audit
    python3 .agent/tools/skill_linter.py

    # Audit just the skills changed in the staged diff (for pre-commit)
    python3 .agent/tools/skill_linter.py --staged

The linter does NOT modify any file. It only reports.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
SKILLS_DIR = AGENT_ROOT / "skills"
INDEX_PATH = SKILLS_DIR / "_index.md"
MANIFEST_PATH = SKILLS_DIR / "_manifest.jsonl"

REQUIRED_FRONTMATTER_KEYS = {"name", "version", "triggers"}
SELF_REWRITE_HEADER_PATTERN = re.compile(r"^##\s+self.?rewrite", re.IGNORECASE | re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter without pulling in pyyaml.

    Returns (parsed_dict, body_text). For our purposes we need name,
    version, triggers — all of which are simple scalars or simple
    inline lists. A single-pass regex parser is sufficient and keeps
    us stdlib-only (skill_linter must run in any clone of the fork).
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip("\n")
    body = text[end + 4 :]

    parsed: dict = {}
    current_key = None
    for raw_line in fm_block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        # Top-level "key: value" — handle either inline scalar or list opener
        m = re.match(r"^([a-z_][a-z0-9_]*)\s*:\s*(.*)$", line)
        if m and not raw_line.startswith(" "):
            key, value = m.group(1), m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                # Inline list: triggers: ["a", "b", "c"]
                inner = value[1:-1]
                items = re.findall(r'"([^"]*)"|\'([^\']*)\'', inner)
                parsed[key] = [a or b for a, b in items]
            elif value:
                parsed[key] = value.strip("\"'")
            else:
                parsed[key] = None
                current_key = key
        elif raw_line.startswith("  - "):
            # Multi-line list item under a previous key
            item = raw_line[4:].strip().strip("\"'")
            if current_key:
                if not isinstance(parsed.get(current_key), list):
                    parsed[current_key] = []
                parsed[current_key].append(item)
    return parsed, body


def _load_manifest() -> dict[str, dict]:
    """Return name -> manifest entry. Empty if manifest missing."""
    if not MANIFEST_PATH.is_file():
        return {}
    out: dict[str, dict] = {}
    for i, line in enumerate(MANIFEST_PATH.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"_manifest.jsonl line {i}: invalid JSON ({e.msg})")
        name = entry.get("name")
        if name:
            out[name] = entry
    return out


def _load_index_skill_names() -> set[str]:
    """Return set of skill names that appear in _index.md.

    Accepts two index entry formats — both are valid pointer-style
    progressive disclosure:

      ## skill-name
      Brief description...

      - **skill-name** — brief description...

    The compact bullet form (used after slice-3 trim) packs more
    skills into fewer lines while still being a clear pointer.
    """
    if not INDEX_PATH.is_file():
        return set()
    text = INDEX_PATH.read_text(encoding="utf-8")
    names = set(re.findall(r"^##\s+([a-z][a-z0-9-]+)", text, re.MULTILINE))
    names |= set(re.findall(r"^-\s+\*\*([a-z][a-z0-9-]+)\*\*", text, re.MULTILINE))
    return names


def lint_skill(skill_dir: Path, manifest: dict[str, dict], index_names: set[str]) -> list[str]:
    """Return list of violation messages for a single skill. Empty list = clean."""
    skill_path = skill_dir / "SKILL.md"
    name = skill_dir.name
    violations: list[str] = []

    if not skill_path.is_file():
        violations.append(f"missing SKILL.md")
        return violations

    text = skill_path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(text)

    # 1. Frontmatter shape
    if not frontmatter:
        violations.append("frontmatter missing or unparseable (must start with '---')")
    else:
        missing = REQUIRED_FRONTMATTER_KEYS - set(frontmatter.keys())
        if missing:
            violations.append(f"frontmatter missing required keys: {sorted(missing)}")
        if frontmatter.get("name") != name:
            violations.append(
                f"frontmatter name='{frontmatter.get('name')}' does not match dir name='{name}'"
            )
        triggers = frontmatter.get("triggers")
        if not triggers or not isinstance(triggers, list):
            violations.append("frontmatter 'triggers' must be a non-empty list")

    # 2. Self-rewrite hook
    if not SELF_REWRITE_HEADER_PATTERN.search(text):
        violations.append(
            "missing '## Self-rewrite hook' section "
            "(every skill must self-improve — see skillforge convention)"
        )

    # 3. Manifest entry
    if name not in manifest:
        violations.append(f"no entry in skills/_manifest.jsonl for name='{name}'")
    elif frontmatter:
        m_entry = manifest[name]
        m_triggers = set(m_entry.get("triggers") or [])
        f_triggers = set(frontmatter.get("triggers") or [])
        if m_triggers != f_triggers:
            extras_m = m_triggers - f_triggers
            extras_f = f_triggers - m_triggers
            parts = []
            if extras_m:
                parts.append(f"in manifest only: {sorted(extras_m)}")
            if extras_f:
                parts.append(f"in SKILL.md only: {sorted(extras_f)}")
            violations.append(f"manifest triggers differ from SKILL.md ({'; '.join(parts)})")

    # 4. Index entry
    if name not in index_names:
        violations.append(f"no '## {name}' header in skills/_index.md")

    return violations


def _staged_skill_dirs() -> list[Path]:
    """Return list of skill dirs that have staged changes. Used by --staged."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=AGENT_ROOT.parent,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    paths = result.stdout.strip().splitlines()
    skill_names = set()
    for p in paths:
        m = re.match(r"\.agent/skills/([^/]+)/", p)
        if m and m.group(1) not in {"_index.md", "_manifest.jsonl"}:
            skill_names.add(m.group(1))
        # Index/manifest changes trigger full audit
        if p in {".agent/skills/_index.md", ".agent/skills/_manifest.jsonl"}:
            return list(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    return [SKILLS_DIR / n for n in sorted(skill_names) if (SKILLS_DIR / n).is_dir()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Lint only skills that have staged changes (for pre-commit hooks).",
    )
    args = parser.parse_args(argv)

    if not SKILLS_DIR.is_dir():
        print(f"error: {SKILLS_DIR} is not a directory", file=sys.stderr)
        return 2

    try:
        manifest = _load_manifest()
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    index_names = _load_index_skill_names()

    if args.staged:
        targets = _staged_skill_dirs()
        if not targets:
            print("ok: no skill changes staged; nothing to lint")
            return 0
    else:
        targets = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())

    failed = 0
    for skill_dir in targets:
        violations = lint_skill(skill_dir, manifest, index_names)
        if violations:
            failed += 1
            print(f"FAIL: {skill_dir.name}")
            for v in violations:
                print(f"  - {v}")

    total = len(targets)
    if failed:
        print(
            f"\nskill_linter: {failed}/{total} skill(s) failed conformance checks",
            file=sys.stderr,
        )
        return 1

    print(f"ok: all {total} skill(s) pass conformance checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
