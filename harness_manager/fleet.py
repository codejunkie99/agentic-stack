"""Fleet manifest, audit, and transactional portable-brain rollout."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import doctor, upgrade


WORKSPACE_MODES = {"managed", "source", "pending", "external"}
SKIP_DIRECTORIES = {
    ".agent",
    ".git",
    ".idea",
    ".vs",
    ".vscode",
    "bin",
    "build",
    "dist",
    "node_modules",
    "obj",
    "packages",
    "vendor",
}


@dataclass(frozen=True)
class Workspace:
    id: str
    path: str
    mode: str
    display_name: str
    repositories: tuple[str, ...]
    adapters: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class FleetManifest:
    path: Path
    root: Path
    profile: str
    workspaces: tuple[Workspace, ...]
    exclusions: tuple[dict, ...]


@dataclass(frozen=True)
class Finding:
    severity: str
    workspace: str
    message: str


def load_manifest(path: Path | str) -> tuple[FleetManifest | None, list[str]]:
    manifest_path = Path(path).resolve()
    errors: list[str] = []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"fleet manifest does not exist: {manifest_path}"]
    except json.JSONDecodeError as error:
        return None, [f"fleet manifest is not valid JSON: {error.msg}"]
    if not isinstance(data, dict):
        return None, ["fleet manifest must be a JSON object"]
    if data.get("schemaVersion") != 1:
        errors.append("fleet manifest schemaVersion must be 1")
    profile = data.get("profile")
    if not isinstance(profile, str) or not profile.strip():
        errors.append("fleet manifest profile must be a non-empty string")
        profile = ""
    root_value = data.get("fleetRoot", ".")
    if not isinstance(root_value, str) or not root_value:
        errors.append("fleetRoot must be a non-empty string")
        root_value = "."
    root = (manifest_path.parent / root_value).resolve()
    if not root.is_dir():
        errors.append(f"fleetRoot does not exist: {root}")

    workspace_rows = data.get("workspaces")
    workspaces: list[Workspace] = []
    if not isinstance(workspace_rows, list) or not workspace_rows:
        errors.append("fleet manifest must define at least one workspace")
        workspace_rows = []
    for index, row in enumerate(workspace_rows, start=1):
        label = f"workspace {index}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be an object")
            continue
        workspace_id = row.get("id")
        path_value = row.get("path")
        mode = row.get("mode")
        display_name = row.get("displayName")
        repositories = row.get("repositories", [])
        adapters = row.get("adapters", [])
        rationale = row.get("rationale", "")
        if not isinstance(workspace_id, str) or not workspace_id:
            errors.append(f"{label} id must be a non-empty string")
            workspace_id = f"invalid-{index}"
        if not isinstance(path_value, str) or not path_value:
            errors.append(f"{label} path must be a non-empty string")
            path_value = f"invalid-{index}"
        if mode not in WORKSPACE_MODES:
            errors.append(f"{label} has invalid mode: {mode}")
            mode = "pending"
        if not isinstance(display_name, str) or not display_name:
            errors.append(f"{label} displayName must be a non-empty string")
            display_name = workspace_id
        if not _string_list(repositories, allow_empty=True):
            errors.append(f"{label} repositories must be an array of unique strings")
            repositories = []
        if not _string_list(adapters, allow_empty=True):
            errors.append(f"{label} adapters must be an array of unique strings")
            adapters = []
        if mode in {"pending", "external"} and not isinstance(rationale, str):
            errors.append(f"{label} rationale must be a string")
            rationale = ""
        if mode in {"pending", "external"} and not rationale.strip():
            errors.append(f"{label} mode {mode} requires a rationale")
        workspaces.append(
            Workspace(
                id=workspace_id,
                path=path_value,
                mode=mode,
                display_name=display_name,
                repositories=tuple(repositories),
                adapters=tuple(adapters),
                rationale=rationale,
            )
        )

    exclusions = data.get("exclusions", [])
    if not isinstance(exclusions, list):
        errors.append("fleet manifest exclusions must be an array")
        exclusions = []
    normalized_exclusions: list[dict] = []
    for index, row in enumerate(exclusions, start=1):
        if not isinstance(row, dict):
            errors.append(f"exclusion {index} must be an object")
            continue
        path_value = row.get("path")
        reason = row.get("reason")
        if not isinstance(path_value, str) or not path_value:
            errors.append(f"exclusion {index} path must be a non-empty string")
            continue
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"exclusion {index} requires a reason")
            continue
        normalized_exclusions.append({"path": path_value, "reason": reason})

    manifest = FleetManifest(
        path=manifest_path,
        root=root,
        profile=profile,
        workspaces=tuple(workspaces),
        exclusions=tuple(normalized_exclusions),
    )
    errors.extend(validate_manifest(manifest))
    return manifest, errors


def validate_manifest(manifest: FleetManifest) -> list[str]:
    errors: list[str] = []
    ids = [workspace.id for workspace in manifest.workspaces]
    paths = [workspace.path for workspace in manifest.workspaces]
    if len(ids) != len(set(ids)):
        errors.append("workspace ids must be unique")
    if len(paths) != len(set(paths)):
        errors.append("workspace paths must be unique")

    exclusion_paths = [row["path"] for row in manifest.exclusions]
    if len(exclusion_paths) != len(set(exclusion_paths)):
        errors.append("exclusion paths must be unique")
    overlaps = sorted(set(paths) & set(exclusion_paths))
    if overlaps:
        errors.append("paths cannot be both workspaces and exclusions: " + ", ".join(overlaps))

    assigned_repositories: dict[str, list[str]] = {}
    for workspace in manifest.workspaces:
        workspace_root = _safe_resolve(manifest.root, workspace.path, errors, f"workspace {workspace.id}")
        if workspace_root is None:
            continue
        if not workspace_root.is_dir():
            errors.append(f"workspace path does not exist: {workspace.path}")
        for repository in workspace.repositories:
            repository_root = _safe_resolve(manifest.root, repository, errors, f"repository {repository}")
            if repository_root is None:
                continue
            try:
                repository_root.relative_to(workspace_root)
            except ValueError:
                errors.append(
                    f"workspace {workspace.id} repository is outside its workspace: {repository}"
                )
            assigned_repositories.setdefault(repository, []).append(workspace.id)
    for repository, owners in assigned_repositories.items():
        if len(owners) > 1:
            errors.append(f"repository has multiple workspace owners: {repository} -> {owners}")

    discovered_repositories = {
        path.relative_to(manifest.root).as_posix() for path in discover_git_repositories(manifest.root)
    }
    declared_repositories = set(assigned_repositories)
    excluded = set(exclusion_paths)
    for repository in sorted(discovered_repositories - declared_repositories - excluded):
        errors.append(f"Git repository is not assigned or excluded: {repository}")
    for repository in sorted(declared_repositories - discovered_repositories):
        errors.append(f"declared repository has no .git directory: {repository}")

    discovered_top = {
        path.relative_to(manifest.root).as_posix()
        for path in manifest.root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    for path in sorted(discovered_top - set(paths) - excluded):
        errors.append(f"top-level directory is not a workspace or exclusion: {path}")

    discovered_brains = {
        path.relative_to(manifest.root).as_posix() for path in discover_brain_roots(manifest.root)
    }
    declared_brains = {
        workspace.path for workspace in manifest.workspaces if workspace.mode in {"managed", "source"}
    }
    for path in sorted(discovered_brains - declared_brains):
        errors.append(f"portable brain has no managed or source workspace owner: {path}")
    return errors


def audit_fleet(manifest: FleetManifest, stack_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for workspace in manifest.workspaces:
        root = (manifest.root / workspace.path).resolve()
        if workspace.mode == "external":
            findings.append(Finding("info", workspace.id, f"external owner: {workspace.rationale}"))
            continue
        if workspace.mode == "pending":
            findings.append(Finding("error", workspace.id, f"adoption pending: {workspace.rationale}"))
            continue
        if workspace.mode == "source":
            status, detail = _audit_source_workspace(root)
            findings.append(Finding(status, workspace.id, detail))
            continue
        install_json = root / ".agent" / "install.json"
        if not install_json.is_file():
            findings.append(Finding("error", workspace.id, "managed workspace has no install.json"))
            continue
        profile_errors = _profile_errors(root, manifest, workspace)
        for error in profile_errors:
            findings.append(Finding("error", workspace.id, error))
        status, lines = doctor._audit_portable_brain(root)
        severity = "ok" if status == doctor.GREEN else "error" if status == doctor.RED else "warning"
        findings.append(Finding(severity, workspace.id, "; ".join(lines)))
        try:
            install = json.loads(install_json.read_text(encoding="utf-8"))
            version = install.get("agentic_stack_version", "unknown")
        except (OSError, json.JSONDecodeError):
            findings.append(Finding("error", workspace.id, "install.json is not valid JSON"))
        else:
            actual_adapters = set((install.get("adapters") or {}).keys())
            expected_adapters = set(workspace.adapters)
            if actual_adapters != expected_adapters:
                findings.append(
                    Finding(
                        "error",
                        workspace.id,
                        "adapter set differs from fleet manifest: "
                        f"expected={sorted(expected_adapters)}, actual={sorted(actual_adapters)}",
                    )
                )
            findings.append(Finding("info", workspace.id, f"installed version: {version}"))
    return findings


def upgrade_fleet(
    manifest: FleetManifest,
    stack_root: Path,
    *,
    dry_run: bool,
    yes: bool,
    log: Callable[[str], None] = print,
) -> int:
    if not dry_run and not yes:
        print("error: fleet upgrade requires --dry-run or --yes", file=sys.stderr)
        return 2
    failures = 0
    for workspace in manifest.workspaces:
        if workspace.mode != "managed":
            log(f"skip {workspace.id}: mode={workspace.mode}")
            if workspace.mode == "pending":
                failures += 1
            continue
        root = (manifest.root / workspace.path).resolve()
        log(f"workspace {workspace.id}: {root}")
        if dry_run:
            actions = upgrade._plan(stack_root / ".agent", root / ".agent")
            agents_change = upgrade._agents_block_needs_update(
                stack_root / ".agent" / "AGENTS.md", root / ".agent" / "AGENTS.md"
            )
            profile_change = bool(_profile_errors(root, manifest, workspace))
            log(
                f"  would update {len(actions)} managed file(s), "
                f"agents_block={str(agents_change).lower()}, profile={str(profile_change).lower()}"
            )
            continue
        if not _transactional_upgrade(root, stack_root, manifest, workspace, log):
            failures += 1
    return 1 if failures else 0


def _transactional_upgrade(
    root: Path,
    stack_root: Path,
    manifest: FleetManifest,
    workspace: Workspace,
    log: Callable[[str], None],
) -> bool:
    src_agent = stack_root / ".agent"
    dst_agent = root / ".agent"
    if not dst_agent.is_dir():
        log("  failed: .agent is missing")
        return False
    actions = upgrade._plan(src_agent, dst_agent)
    touched = {dst for _src, dst in actions}
    touched.update(
        {
            dst_agent / "AGENTS.md",
            dst_agent / "config" / "profile.json",
            dst_agent / "skills" / "_manifest.jsonl",
        }
    )
    with tempfile.TemporaryDirectory(prefix="agentic-stack-fleet-") as temp_name:
        snapshot = Path(temp_name)
        records = _snapshot_files(root, touched, snapshot)
        try:
            result = upgrade.upgrade(root, stack_root, yes=True, log=lambda line: log(f"  {line}"))
            if result != 0:
                raise RuntimeError(f"upgrade exited with status {result}")
            _write_profile(root, manifest, workspace)
            status, lines = doctor._audit_portable_brain(root)
            if status != doctor.GREEN:
                raise RuntimeError("; ".join(lines))
            remaining = _profile_errors(root, manifest, workspace)
            if remaining:
                raise RuntimeError("; ".join(remaining))
        except Exception as error:
            _restore_files(root, records, snapshot)
            log(f"  rolled back: {error}")
            return False
    log("  verified")
    return True


def _profile_document(manifest: FleetManifest, workspace: Workspace) -> dict:
    return {
        "schemaVersion": 1,
        "profile": manifest.profile,
        "projectId": workspace.id,
        "workspacePath": workspace.path,
        "displayName": workspace.display_name,
        "mode": "brain-primary",
        "repositories": list(workspace.repositories),
        "adapters": list(workspace.adapters),
    }


def _write_profile(root: Path, manifest: FleetManifest, workspace: Workspace) -> None:
    path = root / ".agent" / "config" / "profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(_profile_document(manifest, workspace), indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, prefix=".profile-"
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _profile_errors(root: Path, manifest: FleetManifest, workspace: Workspace) -> list[str]:
    path = root / ".agent" / "config" / "profile.json"
    if not path.is_file():
        return ["profile identity is missing"]
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["profile identity is not valid JSON"]
    expected = _profile_document(manifest, workspace)
    return [] if actual == expected else ["profile identity differs from the fleet manifest"]


def _snapshot_files(root: Path, paths: set[Path], snapshot: Path) -> list[dict]:
    records: list[dict] = []
    for index, path in enumerate(sorted(paths)):
        existed = path.is_file() or path.is_symlink()
        record = {"path": path, "existed": existed, "snapshot": None}
        if existed:
            target = snapshot / str(index)
            if path.is_symlink():
                record["link"] = os.readlink(path)
            else:
                shutil.copy2(path, target)
                record["snapshot"] = target
        records.append(record)
    return records


def _restore_files(root: Path, records: list[dict], snapshot: Path) -> None:
    del root, snapshot
    for record in reversed(records):
        path: Path = record["path"]
        if path.is_symlink() or path.is_file():
            path.unlink()
        if not record["existed"]:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if "link" in record:
            path.symlink_to(record["link"])
        else:
            shutil.copy2(record["snapshot"], path)


def _audit_source_workspace(root: Path) -> tuple[str, str]:
    validator = root / ".agent" / "tools" / "validate_extracted_artifacts.py"
    if not validator.is_file():
        return "error", "source validator is missing"
    result = subprocess.run(
        [sys.executable, str(validator), "--repo-root", str(root)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    detail = (result.stdout + result.stderr).strip()
    return ("ok" if result.returncode == 0 else "error", detail)


def discover_git_repositories(root: Path) -> list[Path]:
    repositories: list[Path] = []
    for current, directories, _files in os.walk(root):
        directories[:] = [name for name in directories if name not in SKIP_DIRECTORIES]
        current_path = Path(current)
        if (current_path / ".git").is_dir():
            repositories.append(current_path)
            directories[:] = [name for name in directories if name != ".git"]
    return sorted(repositories)


def discover_brain_roots(root: Path) -> list[Path]:
    roots: list[Path] = []
    seen_agents: set[Path] = set()
    for current, directories, _files in os.walk(root):
        directories.sort()
        directories[:] = [name for name in directories if name not in SKIP_DIRECTORIES - {".agent"}]
        current_path = Path(current)
        agent_root = current_path / ".agent"
        canonical_agent = agent_root.resolve()
        if (agent_root / "AGENTS.md").is_file() and canonical_agent not in seen_agents:
            roots.append(current_path)
            seen_agents.add(canonical_agent)
        directories[:] = [name for name in directories if name != ".agent"]
    return sorted(roots)


def _safe_resolve(root: Path, value: str, errors: list[str], label: str) -> Path | None:
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        errors.append(f"{label} escapes fleetRoot: {value}")
        return None
    return path


def _string_list(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value))
    )
