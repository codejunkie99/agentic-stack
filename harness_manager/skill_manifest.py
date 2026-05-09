"""Sync .agent/skills/_manifest.jsonl from SKILL.md frontmatter."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable


LIST_FIELDS = {"triggers", "tools", "preconditions", "constraints"}
ORDER = ["name", "version", "triggers", "tools", "preconditions", "constraints", "category"]


def sync_manifest(target_root: Path | str, log: Callable[[str], None] | None = None) -> int:
    """Upsert every skills/*/SKILL.md frontmatter block into _manifest.jsonl."""
    if log is None:
        log = print
    target_root = Path(target_root)
    skills_dir = target_root / ".agent" / "skills"
    if not skills_dir.is_dir():
        raise FileNotFoundError(f"skills directory not found: {skills_dir}")

    manifest_path = skills_dir / "_manifest.jsonl"
    existing_rows = _load_existing(manifest_path)
    by_name = {row.get("name"): row for row in existing_rows if row.get("name")}
    seen = set()

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        parsed = parse_skill_frontmatter(skill_md)
        name = parsed.get("name")
        if not name:
            continue
        seen.add(name)
        merged = dict(by_name.get(name) or {})
        merged.update(parsed)
        by_name[name] = _ordered(merged)

    ordered_names = []
    for row in existing_rows:
        name = row.get("name")
        if name and name in by_name and name not in ordered_names:
            ordered_names.append(name)
    for name in sorted(seen):
        if name not in ordered_names:
            ordered_names.append(name)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        for name in ordered_names:
            f.write(json.dumps(by_name[name], separators=(",", ":")) + "\n")
    log(f"synced {len(seen)} skill manifest entr{'y' if len(seen) == 1 else 'ies'}")
    return len(seen)


def parse_skill_frontmatter(skill_md: Path | str) -> dict:
    lines = Path(skill_md).read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        if not key:
            continue
        fields[key] = _parse_value(raw, key)
    return fields


def _load_existing(manifest_path: Path) -> list[dict]:
    if not manifest_path.is_file():
        return []
    rows = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _parse_value(raw: str, key: str):
    if key in LIST_FIELDS:
        return _parse_list(raw)
    return _strip_quotes(raw)


def _parse_list(raw: str) -> list[str]:
    raw = raw.strip()
    if raw in ("", "[]"):
        return []
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [_strip_quotes(item.strip()) for item in next(csv.reader([raw], skipinitialspace=True)) if item.strip()]


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _ordered(row: dict) -> dict:
    out = {key: row[key] for key in ORDER if key in row}
    for key in sorted(k for k in row if k not in out):
        out[key] = row[key]
    return out
