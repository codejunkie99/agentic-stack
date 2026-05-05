"""Portable transfer bundle export/import for agentic-stack memory."""
from __future__ import annotations

import base64
import datetime as dt
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
SENTINEL = "## Auto-promoted entries will be appended below"


class BundleSecurityError(ValueError):
    """Raised when a transfer bundle would include high-risk content."""


SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk|pk)-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:OPENAI|ANTHROPIC|GITHUB|GH|AWS|GOOGLE)_[A-Z0-9_]*(?:KEY|TOKEN|SECRET)\s*="),
)

RUNTIME_PARTS = {
    ".index",
    "snapshots",
    "exports",
    "__pycache__",
}
RUNTIME_SUFFIXES = {
    ".pyc",
    ".db",
    ".sqlite",
    ".tmp",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def scan_text_for_secrets(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def export_bundle(
    agent_root: Path | str,
    targets: Iterable[str],
    scopes: Iterable[str],
    project_name: str | None = None,
) -> dict[str, Any]:
    agent_root = Path(agent_root)
    scopes = list(scopes)
    bundle: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "source": {
            "agentic_stack_version": _version(),
            "project_name": project_name or agent_root.parent.name or "unknown",
        },
        "targets": list(targets),
        "scopes": scopes,
        "files": [],
        "lessons": [],
        "warnings": [],
    }

    if "preferences" in scopes:
        _add_file(bundle, agent_root, agent_root / "memory" / "personal" / "PREFERENCES.md")

    if "accepted_lessons" in scopes:
        bundle["lessons"] = _load_accepted_lessons(agent_root)

    if "skills" in scopes:
        skills_root = agent_root / "skills"
        _add_tree(bundle, agent_root, skills_root)

    if "working" in scopes:
        _add_tree(bundle, agent_root, agent_root / "memory" / "working")

    if "episodic" in scopes:
        _add_tree(bundle, agent_root, agent_root / "memory" / "episodic")

    if "candidates" in scopes:
        _add_tree(bundle, agent_root, agent_root / "memory" / "candidates")

    return bundle


def encode_bundle(bundle: dict[str, Any]) -> tuple[str, str]:
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, mtime=0)
    digest = hashlib.sha256(compressed).hexdigest()
    payload = base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")
    return payload, digest


def decode_payload(payload: str, digest: str) -> dict[str, Any]:
    padded = payload + ("=" * (-len(payload) % 4))
    compressed = base64.urlsafe_b64decode(padded.encode("ascii"))
    actual = hashlib.sha256(compressed).hexdigest()
    if actual != digest:
        raise ValueError("transfer payload digest mismatch")
    data = json.loads(gzip.decompress(compressed).decode("utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported transfer schema: {data.get('schema_version')}")
    return data


def import_bundle(bundle: dict[str, Any], target_root: Path | str) -> dict[str, Any]:
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported transfer schema: {bundle.get('schema_version')}")

    target_root = Path(target_root)
    agent_root = target_root / ".agent"
    (agent_root / "memory" / "personal").mkdir(parents=True, exist_ok=True)
    (agent_root / "memory" / "semantic").mkdir(parents=True, exist_ok=True)
    (agent_root / "skills").mkdir(parents=True, exist_ok=True)

    result = {
        "files_imported": 0,
        "preferences_imported": False,
        "lessons_imported": 0,
        "skills_imported": 0,
    }

    for entry in bundle.get("files", []):
        rel = Path(entry["path"])
        _ensure_allowed(rel)
        content = base64.b64decode(entry["content_b64"]).decode(entry.get("encoding", "utf-8"))
        if scan_text_for_secrets(content):
            raise BundleSecurityError(f"secret-like content detected in {entry['path']}")
        if rel.as_posix() == ".agent/memory/personal/PREFERENCES.md":
            if _merge_preferences(agent_root / "memory" / "personal" / "PREFERENCES.md", content):
                result["preferences_imported"] = True
                result["files_imported"] += 1
            continue
        dest = target_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        result["files_imported"] += 1
        if rel.as_posix().startswith(".agent/skills/"):
            result["skills_imported"] += 1

    result["lessons_imported"] = _import_lessons(
        agent_root / "memory" / "semantic",
        bundle.get("lessons", []),
    )
    _render_lessons(agent_root / "memory" / "semantic")
    _record_import(agent_root, bundle, result)
    return result


def _add_file(bundle: dict[str, Any], agent_root: Path, path: Path) -> None:
    if not path.is_file():
        return
    rel = Path(".agent") / path.relative_to(agent_root)
    _ensure_allowed(rel)
    text = path.read_text(encoding="utf-8")
    if scan_text_for_secrets(text):
        raise BundleSecurityError(f"secret-like content detected in {rel.as_posix()}")
    bundle["files"].append(
        {
            "path": rel.as_posix(),
            "encoding": "utf-8",
            "content_b64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        }
    )


def _add_tree(bundle: dict[str, Any], agent_root: Path, root: Path) -> None:
    if not root.is_dir():
        return
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if _is_runtime_path(path.relative_to(agent_root)):
            continue
        _add_file(bundle, agent_root, path)


def _ensure_allowed(path: Path) -> None:
    parts = path.parts
    if not parts or parts[0] != ".agent":
        raise ValueError(f"transfer path must live under .agent/: {path}")
    if ".." in parts or path.is_absolute():
        raise ValueError(f"unsafe transfer path: {path}")
    if parts[:3] == (".agent", "protocols", "permissions.md"):
        raise ValueError("transfer may not overwrite .agent/protocols/permissions.md")


def _is_runtime_path(path: Path) -> bool:
    if any(part in RUNTIME_PARTS for part in path.parts):
        return True
    return path.suffix in RUNTIME_SUFFIXES


def _load_accepted_lessons(agent_root: Path) -> list[dict[str, Any]]:
    jsonl = agent_root / "memory" / "semantic" / "lessons.jsonl"
    if not jsonl.is_file():
        return []
    lessons = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("status") == "accepted":
            lessons.append(row)
    return lessons


def _merge_preferences(path: Path, imported: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(imported, encoding="utf-8")
        return True
    existing = path.read_text(encoding="utf-8")
    if imported.strip() in existing or "## Imported Preferences" in existing:
        return False
    merged = existing.rstrip() + "\n\n## Imported Preferences\n\n" + imported.strip() + "\n"
    path.write_text(merged, encoding="utf-8")
    return True


def _import_lessons(semantic_dir: Path, lessons: list[dict[str, Any]]) -> int:
    semantic_dir.mkdir(parents=True, exist_ok=True)
    jsonl = semantic_dir / "lessons.jsonl"
    existing_ids = set()
    if jsonl.is_file():
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("id"):
                existing_ids.add(row["id"])
    imported = 0
    with jsonl.open("a", encoding="utf-8") as f:
        for lesson in lessons:
            if lesson.get("status") != "accepted" or not lesson.get("id"):
                continue
            if lesson["id"] in existing_ids:
                continue
            f.write(json.dumps(lesson, separators=(",", ":")) + "\n")
            existing_ids.add(lesson["id"])
            imported += 1
    return imported


def _render_lessons(semantic_dir: Path) -> None:
    jsonl = semantic_dir / "lessons.jsonl"
    md = semantic_dir / "LESSONS.md"
    lessons = _load_rows(jsonl)
    lines = [
        "# Lessons",
        "",
        "> _Auto-managed below. Hand-curated preamble + seed lessons above the sentinel are preserved across renders._",
        "",
        SENTINEL,
        "",
    ]
    for lesson in lessons:
        if lesson.get("status") != "accepted":
            continue
        claim = lesson.get("claim", "")
        lid = lesson.get("id", "?")
        evidence = len(lesson.get("evidence_ids", []))
        lines.append(f"- {claim}  <!-- status=accepted evidence={evidence} id={lid} -->")
    md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _record_import(agent_root: Path, bundle: dict[str, Any], result: dict[str, Any]) -> None:
    imports = agent_root / "transfer" / "imports"
    imports.mkdir(parents=True, exist_ok=True)
    record = {
        "imported_at": now_iso(),
        "bundle_created_at": bundle.get("created_at"),
        "targets": bundle.get("targets", []),
        "scopes": bundle.get("scopes", []),
        "result": result,
    }
    name = record["imported_at"].replace(":", "").replace("-", "")
    (imports / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _version() -> str:
    try:
        from . import __version__

        return __version__
    except Exception:
        return "unknown"


def copy_agent_template(stack_root: Path, target_root: Path) -> None:
    src = stack_root / ".agent"
    dst = target_root / ".agent"
    if not dst.exists() and src.is_dir():
        shutil.copytree(src, dst)
