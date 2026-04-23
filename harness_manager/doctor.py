"""Read-only audit of installed adapters.

Reads .agent/install.json, verifies each adapter's tracked files still
exist and post-install state is still valid. Reports green/yellow/red
per adapter. Exits 0 on all-green-or-yellow, 1 on any red.

First run on a pre-v0.9.0 project (no install.json) detects adapters
from filesystem signals and ASKS before synthesizing — never silently
writes. Codex's UX framing: doctor must not mutate without consent.
"""
import shutil
import sys
from pathlib import Path
from typing import Callable

from . import schema as schema_mod
from . import state as state_mod
from . import __version__


# Detection signals: (filename, signal_strength) tuples per adapter.
# Strong signals = file exists AND has the expected shape.
DETECT_SIGNALS = {
    "claude-code": [
        ("CLAUDE.md", "weak"),
        (".claude/settings.json", "strong"),
    ],
    "cursor": [(".cursor/rules/agentic-stack.mdc", "strong")],
    "windsurf": [(".windsurfrules", "strong")],
    "openclaw": [(".openclaw-system.md", "strong")],
    "pi": [(".pi/extensions/memory-hook.ts", "strong")],
    "codex": [(".agents/skills", "strong")],
    "antigravity": [("ANTIGRAVITY.md", "strong")],
    "opencode": [("opencode.json", "strong")],
    "hermes": [("AGENTS.md", "weak")],  # AGENTS.md alone is ambiguous
    "standalone-python": [("run.py", "weak")],
}


# ---- statuses ---------------------------------------------------------

GREEN = "green"
YELLOW = "yellow"
RED = "red"


def audit(target_root: Path | str, log: Callable[[str], None] | None = None) -> int:
    """Run read-only audit. Returns exit code (0 if no red, 1 otherwise)."""
    if log is None:
        log = print

    target_root = Path(target_root).resolve()
    doc = state_mod.load(target_root)

    if doc is None:
        return _audit_pre_v090(target_root, log)

    # install.json present → strict read-only audit
    log(f"auditing {len(doc.get('adapters', {}))} installed adapter(s) in {target_root}")
    log("")
    any_red = False
    for adapter_name in sorted(doc.get("adapters", {}).keys()):
        entry = doc["adapters"][adapter_name]
        status, lines = _audit_adapter(target_root, adapter_name, entry)
        glyph = {GREEN: "✓", YELLOW: "⚠", RED: "✗"}[status]
        log(f"{glyph} {adapter_name:18s} {status}")
        for line in lines:
            log(f"    {line}")
        if status == RED:
            any_red = True

    log("")
    log(f"summary: {_summary(doc, any_red)}")
    return 1 if any_red else 0


def _audit_adapter(
    target_root: Path, adapter_name: str, entry: dict
) -> tuple[str, list[str]]:
    """Returns (status, list_of_detail_lines)."""
    lines: list[str] = []

    # Check all tracked files (both freshly-written and overwritten) still exist.
    # Both categories matter for "is the adapter still wired" — only the
    # remove-time semantics differ (overwritten files are user-owned and
    # NOT deleted on remove).
    missing = []
    for f in entry.get("files_written", []) + entry.get("files_overwritten", []):
        if not (target_root / f).exists():
            missing.append(f)
    if missing:
        lines.append(f"missing files: {', '.join(missing)}")
        return RED, lines

    status_overall = GREEN

    # Files where install hit `merge_or_alert` and the existing file did
    # NOT reference .agent/. The adapter is "installed" in the sense that
    # we recorded the entry, but the brain is not actually wired until
    # the user merges the snippet. Re-check current file content — they
    # may have merged it since install. Yellow if still un-merged; green
    # if they merged.
    still_alerted = []
    for f in entry.get("files_alerted", []):
        p = target_root / f
        if not p.is_file():
            still_alerted.append(f"{f} (file missing entirely)")
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            still_alerted.append(f"{f} (unreadable)")
            continue
        if ".agent/" not in content:
            still_alerted.append(f)
    if still_alerted:
        lines.append(
            f"merge required: {', '.join(still_alerted)} — install printed a snippet to paste in"
        )
        status_overall = YELLOW

    # Check skills_link target exists
    sl = entry.get("skills_link")
    if sl:
        dst = target_root / sl["dst"]
        if not dst.exists():
            lines.append(f"skills_link {sl['dst']} missing")
            return RED, lines
        # If it's a symlink, check it doesn't dangle
        if dst.is_symlink() and not dst.exists():
            lines.append(f"skills_link {sl['dst']} dangles")
            return RED, lines

    # Check post_install state. Only verify external state for actions that
    # actually succeeded — if registration was skipped at install time
    # (binary_missing, failed, etc.), the recorded result IS the source of
    # truth and there's nothing on-disk to verify against.
    for r in entry.get("post_install_results", []):
        action = r.get("action", "?")
        st = r.get("status", "?")
        if action == "openclaw_register_workspace":
            agent = r.get("agent_name", "?")
            if st in ("ok", "already_exists"):
                # Registration claimed success at install time; verify it's
                # still true. RED if the agent is now gone from openclaw config.
                check_status = _check_openclaw_agent(agent)
                if check_status == "ok":
                    lines.append(f"openclaw agent '{agent}' registered")
                elif check_status == "binary_missing":
                    lines.append(
                        f"openclaw agent '{agent}' was registered, but openclaw "
                        f"binary not on PATH now — can't verify"
                    )
                    status_overall = max(status_overall, YELLOW, key=_status_rank)
                elif check_status == "missing":
                    lines.append(
                        f"openclaw agent '{agent}' was registered, but no longer "
                        f"present in ~/.openclaw/openclaw.json"
                    )
                    status_overall = RED
            elif st == "binary_missing":
                lines.append(
                    f"openclaw registration skipped at install time (binary not "
                    f"on PATH); fallback hint was printed. install with `openclaw` "
                    f"present, or use the `--system-prompt-file` fallback."
                )
                status_overall = max(status_overall, YELLOW, key=_status_rank)
            else:
                # Failed at install time and we recorded that. Don't escalate
                # to red on every audit — the failure is already known and the
                # user has a fallback hint.
                lines.append(
                    f"openclaw registration {st} at install time "
                    f"(see install.json for details / fallback hint)"
                )
                status_overall = max(status_overall, YELLOW, key=_status_rank)
        else:
            # Unknown post_install action — just record
            lines.append(f"post_install {action}: {st}")

    # .agent/ brain still intact?
    if not (target_root / ".agent" / "AGENTS.md").is_file():
        lines.append(".agent/AGENTS.md missing — brain not present")
        return RED, lines

    return status_overall, lines


def _check_openclaw_agent(agent_name: str) -> str:
    """Check if openclaw agent is still registered. ok | missing | binary_missing"""
    binary = shutil.which("openclaw")
    if not binary:
        return "binary_missing"
    # Read ~/.openclaw/openclaw.json directly (faster + more deterministic
    # than parsing `openclaw agents list` output).
    try:
        import json
        cfg = Path.home() / ".openclaw" / "openclaw.json"
        if not cfg.is_file():
            return "missing"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        agents = (data.get("agents") or {}).get("list") or []
        for a in agents:
            if a.get("id") == agent_name:
                return "ok"
        return "missing"
    except (OSError, json.JSONDecodeError):
        return "binary_missing"


def _status_rank(s: str) -> int:
    return {GREEN: 0, YELLOW: 1, RED: 2}[s]


def _summary(doc: dict, any_red: bool) -> str:
    n = len(doc.get("adapters", {}))
    if any_red:
        return f"{n} adapter(s), at least 1 red — see above"
    return f"{n} adapter(s), all green or yellow"


# ---- pre-v0.9.0 migration prompt -------------------------------------

def _audit_pre_v090(target_root: Path, log: Callable[[str], None]) -> int:
    """No install.json. Detect adapters from filesystem and prompt to register.

    Codex UX rule: never silently mutate. Show user what we found, ask Y/N,
    write only on confirmation. On N or non-tty, exit 0 with no write.
    """
    detected: list[tuple[str, str]] = []  # (name, signal_strength_summary)
    for name, signals in DETECT_SIGNALS.items():
        present = [(f, strength) for f, strength in signals
                   if (target_root / f).exists()]
        if not present:
            continue
        strength = "strong" if any(s == "strong" for _, s in present) else "weak"
        sig_str = ", ".join(f for f, _ in present)
        detected.append((name, f"{strength} — {sig_str}"))

    if not detected:
        log(f"no install.json found at {target_root / '.agent/install.json'}")
        log("no adapter signals detected either. nothing to audit.")
        log("install an adapter with: ./install.sh <adapter-name>")
        return 0

    log(f"no install.json found at {target_root / '.agent/install.json'}")
    log("but I see these adapters appear to be installed:")
    log("")
    for name, sig in detected:
        log(f"  ✓ {name:18s} ({sig})")
    log("")
    log("register them in install.json so I can audit them in future runs?")

    # Non-interactive (no tty) → don't prompt, just exit 0 cleanly.
    if not sys.stdin.isatty():
        log("(non-interactive shell; skipping. re-run from a terminal to register.)")
        return 0

    try:
        answer = input("[Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        log("")
        log("aborted; no changes written.")
        return 0
    if answer not in ("", "y", "yes"):
        log("ok, leaving install.json absent. you can run `./install.sh <adapter>` "
            "per adapter to register explicitly.")
        return 0

    # Synthesize install.json from detected adapters.
    doc = state_mod.empty(target_root, __version__)
    now = state_mod._iso_now()  # type: ignore  # internal helper, fine here
    for name, _sig in detected:
        # Best-effort entry — files_written is empty because we don't know
        # what was written historically. Future audits will treat this as
        # "registered but no files tracked"; subsequent re-installs of
        # the adapter via ./install.sh <name> will populate files_written.
        doc["adapters"][name] = {
            "installed_at": now,
            "files_written": [],
            "file_results": [],
            "post_install_results": [],
            "_synthesized": True,  # marker for future migrations
        }
    state_mod.save(target_root, doc)
    log(f"  ✓ wrote install.json with {len(detected)} synthesized adapter(s)")
    log("  tip: re-run `./install.sh <adapter>` per adapter to populate files_written.")
    return 0
