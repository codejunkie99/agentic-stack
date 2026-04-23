"""adapter.json schema + stdlib-only validator.

Zero deps by design — the repo's other Python touchpoints (onboard.py,
.agent/tools/*) are all stdlib-only and brew-installed users get raw
python3 with no pip step. A 50-line recursive checker is cheaper than
adding a `jsonschema` dependency.
"""
import json
from pathlib import Path
from typing import Any


# Schema version. Bump only when an incompatible change ships.
SCHEMA_VERSION = 1

VALID_MERGE_POLICIES = {"overwrite", "skip_if_exists", "merge_or_alert"}
VALID_FALLBACKS = {"rsync_with_delete"}
VALID_POST_INSTALL_ACTIONS = {"openclaw_register_workspace"}


class ManifestError(ValueError):
    """Raised when adapter.json fails validation. Includes source for context."""

    def __init__(self, source: str, message: str):
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message


def _require(d: dict, key: str, types: tuple, source: str) -> Any:
    if key not in d:
        raise ManifestError(source, f"missing required field '{key}'")
    val = d[key]
    if not isinstance(val, types):
        type_names = " or ".join(t.__name__ for t in types)
        raise ManifestError(
            source, f"field '{key}' must be {type_names}, got {type(val).__name__}"
        )
    return val


def _check_optional(d: dict, key: str, types: tuple, source: str) -> Any:
    if key not in d:
        return None
    val = d[key]
    if not isinstance(val, types):
        type_names = " or ".join(t.__name__ for t in types)
        raise ManifestError(
            source, f"field '{key}' must be {type_names}, got {type(val).__name__}"
        )
    return val


def _validate_files(files: list, source: str) -> None:
    if not files:
        raise ManifestError(source, "'files' must contain at least one entry")
    for i, entry in enumerate(files):
        es = f"{source} files[{i}]"
        if not isinstance(entry, dict):
            raise ManifestError(es, "must be an object")
        src = _require(entry, "src", (str,), es)
        dst = _require(entry, "dst", (str,), es)
        if not src or not dst:
            raise ManifestError(es, "'src' and 'dst' must be non-empty strings")
        if ".." in src.split("/") or ".." in dst.split("/"):
            raise ManifestError(es, "'..' path components not allowed (path traversal)")
        if src.startswith("/") or dst.startswith("/"):
            raise ManifestError(es, "absolute paths not allowed; use repo-relative paths")
        policy = _check_optional(entry, "merge_policy", (str,), es)
        if policy is not None and policy not in VALID_MERGE_POLICIES:
            raise ManifestError(
                es, f"merge_policy must be one of {sorted(VALID_MERGE_POLICIES)}, got '{policy}'"
            )
        _check_optional(entry, "substitute", (bool,), es)
        _check_optional(entry, "from_stack", (bool,), es)


def _validate_skills_link(link: dict, source: str) -> None:
    if not isinstance(link, dict):
        raise ManifestError(source, "'skills_link' must be an object")
    target = _require(link, "target", (str,), f"{source} skills_link")
    dst = _require(link, "dst", (str,), f"{source} skills_link")
    if not target or not dst:
        raise ManifestError(f"{source} skills_link", "'target' and 'dst' must be non-empty")
    fallback = _check_optional(link, "fallback", (str,), f"{source} skills_link")
    if fallback is not None and fallback not in VALID_FALLBACKS:
        raise ManifestError(
            f"{source} skills_link",
            f"fallback must be one of {sorted(VALID_FALLBACKS)}, got '{fallback}'",
        )


def _validate_post_install(actions: list, source: str) -> None:
    for i, action in enumerate(actions):
        if not isinstance(action, str):
            raise ManifestError(
                f"{source} post_install[{i}]",
                f"must be a string naming a built-in action, got {type(action).__name__}",
            )
        if action not in VALID_POST_INSTALL_ACTIONS:
            raise ManifestError(
                f"{source} post_install[{i}]",
                f"unknown action '{action}'; valid: {sorted(VALID_POST_INSTALL_ACTIONS)}",
            )


def validate_dict(manifest: Any, source: str) -> dict:
    """Validate an in-memory manifest dict. Returns the dict on success."""
    if not isinstance(manifest, dict):
        raise ManifestError(source, f"manifest must be a JSON object, got {type(manifest).__name__}")

    name = _require(manifest, "name", (str,), source)
    _require(manifest, "description", (str,), source)
    files = _require(manifest, "files", (list,), source)

    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ManifestError(
            source, f"'name' must be non-empty alphanumeric (with - or _), got '{name}'"
        )

    _validate_files(files, source)

    skills_link = _check_optional(manifest, "skills_link", (dict,), source)
    if skills_link is not None:
        _validate_skills_link(skills_link, source)

    post_install = _check_optional(manifest, "post_install", (list,), source)
    if post_install is not None:
        _validate_post_install(post_install, source)

    primitive = _check_optional(manifest, "brain_root_primitive", (str, type(None)), source)
    if primitive is not None and not primitive.startswith("$"):
        raise ManifestError(
            source,
            f"brain_root_primitive must be a shell env var reference like '$CLAUDE_PROJECT_DIR', "
            f"got '{primitive}'",
        )

    # Reject unknown top-level keys to catch typos early.
    known = {
        "name", "description", "files", "skills_link",
        "post_install", "brain_root_primitive",
    }
    extras = set(manifest.keys()) - known
    if extras:
        raise ManifestError(source, f"unknown top-level field(s): {sorted(extras)}")

    return manifest


def validate(manifest_path: Path | str) -> dict:
    """Load and validate adapter.json from a path. Returns the parsed dict."""
    p = Path(manifest_path)
    if not p.is_file():
        raise ManifestError(str(p), "file not found")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise ManifestError(str(p), f"unreadable: {e}") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ManifestError(str(p), f"invalid JSON: {e.msg} at line {e.lineno}") from e
    # Use the dir name as the source label so error messages are more useful
    # ("adapters/claude-code/adapter.json" beats "/abs/path/.../adapter.json").
    label = str(p.relative_to(p.parents[2])) if len(p.parents) >= 3 else str(p)
    return validate_dict(data, label)


def discover_all(repo_root: Path | str) -> list[tuple[str, dict]]:
    """Return (adapter_name, manifest_dict) for every adapter with adapter.json.

    Adapters without adapter.json are skipped silently — they're not
    manifest-driven yet (during the migration window, this is allowed).
    """
    root = Path(repo_root)
    adapters_dir = root / "adapters"
    out = []
    if not adapters_dir.is_dir():
        return out
    for adapter_dir in sorted(adapters_dir.iterdir()):
        if not adapter_dir.is_dir():
            continue
        manifest_path = adapter_dir / "adapter.json"
        if not manifest_path.is_file():
            continue
        manifest = validate(manifest_path)
        out.append((adapter_dir.name, manifest))
    return out
