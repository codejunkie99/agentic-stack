#!/usr/bin/env python3
"""agentic-stack onboarding wizard — populates .agent/memory/personal/PREFERENCES.md."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from onboard_ui       import print_banner, intro, note, outro, step_done, BAR, R, MUTED, GREEN, PURPLE, WHITE, B, ORANGE
from onboard_widgets  import ask_text, ask_select, ask_confirm
from onboard_render   import render
from onboard_write    import write_prefs, is_customized, REL
from onboard_features import write_features

_CI_VARS = ("CI", "GITHUB_ACTIONS", "CIRCLECI", "BUILDKITE", "JENKINS_URL", "TRAVIS")


def _is_ci():
    if not sys.stdin.isatty(): return True
    return any(os.environ.get(v) for v in _CI_VARS)


_KNOWN_FLAGS = {"--yes", "-y", "--force", "--reconfigure"}


def _parse_args(argv=None):
    # Whitelist known flags + honor `--` separator so paths beginning with `-`
    # (e.g. a target accidentally set to `--yes` by install.sh) are not consumed.
    args = sys.argv[1:] if argv is None else list(argv)
    flags, pos, sep_seen = set(), [], False
    for a in args:
        if not sep_seen and a == "--":
            sep_seen = True
            continue
        if not sep_seen and a in _KNOWN_FLAGS:
            flags.add(a)
        else:
            if not sep_seen and a.startswith("-"):
                print(f"[onboard] warning: unknown flag {a!r} treated as path", file=sys.stderr)
            pos.append(a)
    return (
        pos[0] if pos else os.getcwd(),
        "--yes" in flags or "-y" in flags,
        "--force" in flags,
        "--reconfigure" in flags,
    )


def _wizard(target, force):
    """Run the interactive Q&A. Returns answers dict, or None to abort."""
    if is_customized(target) and not force:
        note("Already configured",
             ["PREFERENCES.md already has custom content.",
              "Pass --reconfigure to update it."])
        return None

    intro("agentic-stack setup")
    note("What this does", [
        "Fills .agent/memory/personal/PREFERENCES.md —",
        "the FIRST file your AI reads every session.",
        "Takes about 30 seconds.",
    ])

    a = {}
    a["name"]      = ask_text("What should I call you?",
                               hint="press Enter to skip")
    a["languages"] = ask_text("Primary language(s)?",
                               default="unspecified",
                               hint="e.g. TypeScript, Python, Rust")
    a["style"]     = ask_select("Explanation style?",
                                 ["concise", "detailed"])
    a["tests"]     = ask_select("Test strategy?",
                                 ["test-after", "tdd", "minimal"])
    a["commits"]   = ask_select("Commit message style?",
                                 ["conventional commits", "free-form", "emoji"])
    a["review"]    = ask_select("Code review depth?",
                                 ["critical issues only", "everything"])

    # ── Optional features (beta, opt-in) ───────────────────────────────
    note("Optional features", [
        f"{ORANGE}[BETA]{R}{MUTED} features — off by default, opt-in only.",
        "You can change this later with  agentic-stack <harness> --reconfigure.",
    ])
    a["feature_memory_search"] = ask_confirm(
        f"Enable FTS memory search  {ORANGE}[BETA]{R}?",
        default=False,
    )
    a["feature_tldraw"] = ask_confirm(
        f"Enable tldraw visual memory  {ORANGE}[BETA]{R}?",
        default=False,
    )
    return a


def main():
    target, yes, force, reconf = _parse_args()

    if _is_ci() and not yes:
        print(f"[onboard] non-interactive — skipping wizard (edit {REL} manually)")
        sys.exit(0)

    print_banner()

    if yes:
        path = write_prefs(target, render({}), force=True)
        # --yes defaults all optional beta features to off
        features_file = write_features(target, {
            "memory_search_fts": {"enabled": False, "beta": True},
            "tldraw": {"enabled": False, "beta": True},
        })
        print(f"{GREEN}◆{R}  {WHITE}{B}PREFERENCES.md{R} written with defaults")
        print(f"{MUTED}   {path}{R}")
        print(f"{MUTED}   {features_file} (all beta features off){R}\n")
        sys.exit(0)

    try:
        answers = _wizard(target, force=reconf)
        if answers is None:
            sys.exit(0)
        path = write_prefs(target, render(answers), force=reconf)
        features = {
            "memory_search_fts": {
                "enabled": bool(answers.get("feature_memory_search")),
                "beta": True,
            },
            "tldraw": {
                "enabled": bool(answers.get("feature_tldraw")),
                "beta": True,
            },
        }
        features_file = write_features(target, features)
        outro([
            f"PREFERENCES.md written",
            f"{path}",
            f"Features: {features_file}",
            "Edit either file any time — your AI re-reads them every session.",
            "Tip: git add .agent/memory/ to track your brain.",
            "Want Claude Code to score YOUR stack's deploys/migrations as",
            "high-stakes? Edit .agent/protocols/hook_patterns.json —",
            "add service names like 'vercel' or 'supabase' under high_stakes.",
        ])
    except KeyboardInterrupt:
        print(f"\n\n{MUTED}  Setup cancelled.{R}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
