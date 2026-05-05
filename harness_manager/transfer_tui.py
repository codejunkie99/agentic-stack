"""Onboarding-style transfer wizard and non-interactive transfer CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from . import install as install_mod
from . import schema as schema_mod
from .transfer_bundle import (
    BundleSecurityError,
    copy_agent_template,
    decode_payload,
    encode_bundle,
    export_bundle,
    import_bundle,
)
from .transfer_plan import DEFAULT_SCOPES, VALID_TARGETS, build_plan


def run(argv: list[str], target_root: Path, stack_root: Path) -> int:
    if not argv:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print(
                "error: agentic-stack transfer is interactive in a TTY.\n"
                "use `agentic-stack transfer --help` for non-interactive export/import flags.",
                file=sys.stderr,
            )
            return 2
        return run_wizard(target_root=target_root, stack_root=stack_root)

    if argv[0] in ("--help", "-h"):
        print_help()
        return 0

    cmd = argv[0]
    if cmd == "export":
        return cmd_export(argv[1:], target_root=target_root, stack_root=stack_root)
    if cmd == "import":
        return cmd_import(argv[1:], target_root=target_root, stack_root=stack_root)

    print(f"error: unknown transfer command '{cmd}'", file=sys.stderr)
    print("run `agentic-stack transfer --help` for usage.", file=sys.stderr)
    return 2


def print_help() -> None:
    print(
        """agentic-stack transfer

Open an onboarding-style TUI wizard for moving portable .agent memory into
Codex, Cursor, Windsurf, or a terminal-only AGENTS.md setup.

Usage:
  agentic-stack transfer
  agentic-stack transfer export --target codex --print-curl
  agentic-stack transfer import --payload <payload> --sha256 <digest> --target codex

Commands:
  export    Build a portable transfer bundle from this repo's .agent memory
  import    Import a transfer bundle into this repo and install target adapters
"""
    )


def cmd_export(argv: list[str], target_root: Path, stack_root: Path) -> int:
    parser = argparse.ArgumentParser(prog="agentic-stack transfer export")
    parser.add_argument("--intent", default="transfer memory")
    parser.add_argument("--target", action="append", choices=VALID_TARGETS)
    parser.add_argument("--scope", action="append")
    parser.add_argument("--print-curl", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--payload-file")
    args = parser.parse_args(argv)

    agent_root = target_root / ".agent"
    if not agent_root.is_dir():
        print("error: .agent/ not found in current project", file=sys.stderr)
        return 2

    plan = build_plan(
        args.intent,
        stack_root,
        targets=args.target,
        scopes=args.scope or DEFAULT_SCOPES,
        operation="generate-curl",
    )
    try:
        bundle = export_bundle(agent_root, targets=plan.targets, scopes=plan.scopes)
    except (BundleSecurityError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    payload, digest = encode_bundle(bundle)
    command = build_curl_command(payload, digest, plan.targets[0])

    if args.payload_file:
        Path(args.payload_file).write_text(payload, encoding="utf-8")

    if args.print_curl:
        print(command)

    summary = {
        "targets": list(plan.targets),
        "scopes": list(plan.scopes),
        "payload": payload,
        "sha256": digest,
        "curl": command,
    }
    if args.json:
        print(json.dumps(summary, separators=(",", ":")))
    elif not args.print_curl:
        print(f"payload={payload}")
        print(f"sha256={digest}")
        print(f"curl={command}")
    return 0


def cmd_import(argv: list[str], target_root: Path, stack_root: Path) -> int:
    parser = argparse.ArgumentParser(prog="agentic-stack transfer import")
    parser.add_argument("--payload")
    parser.add_argument("--payload-file")
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--target", action="append", choices=VALID_TARGETS)
    args = parser.parse_args(argv)

    if not args.payload and not args.payload_file:
        print("error: provide --payload or --payload-file", file=sys.stderr)
        return 2

    payload = args.payload
    if args.payload_file:
        payload = Path(args.payload_file).read_text(encoding="utf-8").strip()
    try:
        bundle = decode_payload(payload or "", args.sha256)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.target:
        bundle["targets"] = args.target

    try:
        copy_agent_template(stack_root, target_root)
        result = import_bundle(bundle, target_root)
        adapter_results = apply_adapters(bundle.get("targets", []), target_root, stack_root)
    except (BundleSecurityError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        "imported transfer bundle: "
        f"files={result['files_imported']} "
        f"lessons={result['lessons_imported']} "
        f"skills={result['skills_imported']}"
    )
    if adapter_results:
        print("installed adapters: " + ", ".join(adapter_results))
    return 0


def run_wizard(target_root: Path, stack_root: Path) -> int:
    sys.path.insert(0, str(stack_root))
    from onboard_ui import intro, note, outro, print_banner  # noqa: E402
    import onboard_widgets as widgets  # noqa: E402

    print_banner()
    intro("agentic-stack transfer")
    note(
        "What this does",
        [
            "Builds a portable .agent memory bundle.",
            "Lets you preview target adapter files before writing.",
            "Generates a curl or PowerShell command for another project.",
        ],
    )

    intent = widgets.ask_text(
        "What do you want to transfer?",
        default="move my memory into Codex",
        hint="natural language is fine",
    )
    detected = build_plan(intent, stack_root)
    target_choices = list(VALID_TARGETS)
    target_defaults = [target_choices.index(t) for t in detected.targets if t in target_choices]
    chosen_targets = widgets.ask_multiselect(
        "Which targets should receive it?",
        target_choices,
        defaults=target_defaults,
    )
    scope_choices = [
        "preferences",
        "accepted_lessons",
        "skills",
        "working",
        "episodic",
        "candidates",
    ]
    scope_defaults = [scope_choices.index(s) for s in DEFAULT_SCOPES]
    chosen_scopes = widgets.ask_multiselect(
        "What should move?",
        scope_choices,
        defaults=scope_defaults,
    )
    plan = build_plan(intent, stack_root, targets=chosen_targets, scopes=chosen_scopes)
    if plan.sensitive_scopes:
        ok = widgets.ask_confirm(
            "Sensitive memory selected. Continue after reviewing the preview?",
            default=False,
        )
        if not ok:
            outro(["Transfer cancelled before writing."])
            return 1

    note("Preview", preview_lines(plan))
    if not widgets.ask_confirm("Proceed with this transfer plan?", default=True):
        outro(["Transfer cancelled before writing."])
        return 1

    action = widgets.ask_select(
        "What should happen now?",
        ["Generate curl command", "Apply here now", "Both"],
        default=0,
    )
    operation = {
        "Generate curl command": "generate-curl",
        "Apply here now": "apply-here",
        "Both": "both",
    }[action]
    final_plan = build_plan(intent, stack_root, targets=plan.targets, scopes=plan.scopes, operation=operation)

    agent_root = target_root / ".agent"
    bundle = export_bundle(agent_root, targets=final_plan.targets, scopes=final_plan.scopes)
    payload, digest = encode_bundle(bundle)
    command = build_curl_command(payload, digest, final_plan.targets[0])
    lines = []
    if operation in ("generate-curl", "both"):
        lines.append(command)
    if operation in ("apply-here", "both"):
        import_result = import_bundle(bundle, target_root)
        adapters = apply_adapters(final_plan.targets, target_root, stack_root)
        lines.append(
            f"Applied locally: files={import_result['files_imported']} "
            f"lessons={import_result['lessons_imported']} adapters={', '.join(adapters) or 'none'}"
        )
    lines.append("Verify: python3 .agent/tools/show.py")
    outro(lines)
    return 0


def preview_lines(plan) -> list[str]:
    lines = [
        f"Targets: {', '.join(plan.targets)}",
        f"Scopes: {', '.join(plan.scopes)}",
        f"Operation: {plan.operation}",
    ]
    for warning in plan.warnings:
        lines.append(f"Warning: {warning}")
    lines.append("Adapter files:")
    for action in plan.adapter_actions:
        lines.append(f"- {action.target}: {action.dst} ({action.merge_policy})")
    return lines


def build_curl_command(payload: str, digest: str, target: str) -> str:
    url = "https://raw.githubusercontent.com/codejunkie99/agentic-stack/master/scripts/import-transfer.sh"
    return (
        f"curl -fsSL {url} | sh -s -- "
        f"--target {target} --payload '{payload}' --sha256 {digest}"
    )


def apply_adapters(targets: Iterable[str], target_root: Path, stack_root: Path) -> list[str]:
    applied: list[str] = []
    for target in targets:
        if target == "terminal":
            _ensure_terminal_agents(target_root)
            applied.append("terminal")
            continue
        manifest_path = stack_root / "adapters" / target / "adapter.json"
        if not manifest_path.is_file():
            continue
        manifest = schema_mod.validate(manifest_path)
        install_mod.install(
            manifest=manifest,
            target_root=target_root,
            adapter_dir=stack_root / "adapters" / target,
            stack_root=stack_root,
        )
        applied.append(target)
    return applied


def _ensure_terminal_agents(target_root: Path) -> None:
    path = target_root / "AGENTS.md"
    snippet = (
        "# Agentic-stack brain\n\n"
        "This project uses a portable brain in `.agent/`. Read `.agent/AGENTS.md`, "
        "`.agent/memory/personal/PREFERENCES.md`, and "
        "`.agent/memory/semantic/LESSONS.md` before acting.\n"
    )
    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="replace")
        if ".agent/" in existing:
            return
        path.write_text(existing.rstrip() + "\n\n" + snippet, encoding="utf-8")
    else:
        path.write_text(snippet, encoding="utf-8")
