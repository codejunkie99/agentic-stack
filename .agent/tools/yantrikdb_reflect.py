#!/usr/bin/env python3
"""
YantrikDB Reflect [BETA] — structured meta-state for agent context injection.

Runs the yantrikdb `reflect()` composition — parallel type-filtered
recalls over self-model, rules, hypotheses, constraints, goals, narrative
arcs, and recent learning signals — and renders a compact text block
ready to drop into an agent's system prompt or working context.

Key design choice: this tool emits the yantrikdb-upstream-validated
**memory-router seed prompt** as the first block of output, followed by
the reflected state. Background on why:

    yantrikdb's own research (Apr 2026) showed that retrieval-time
    teaching at small-LLM scale (Qwen 3.6) goes from 27% HURT to 93%
    RESCUE when the agent's system prompt explicitly frames stored items
    as scoped procedure controllers rather than advisory context.

    The 73-word router prompt is replicated verbatim below so agent
    harnesses on top of agentic-stack see the same rescue pattern if they
    use yantrikdb_reflect output as part of their system prompt.

    Reference: https://github.com/yantrikos/yantrikdb-client/blob/main/docs/
               (router-prompt design notes)

Usage:
  python3 yantrikdb_reflect.py "<question>"          # pretty, suited for CLI
  python3 yantrikdb_reflect.py "<question>" --bare   # just the router + state
  python3 yantrikdb_reflect.py "<question>" --json   # structured output

  # as a subprocess for agent context injection:
  CONTEXT=$(python3 yantrikdb_reflect.py "task: refactor login flow" --bare)

BETA + opt-in. Requires yantrikdb-client>=0.2.1 and the yantrikdb_memory
feature enabled.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
FEATURES_PATH = MEMORY_DIR / ".features.json"

# Verbatim from yantrikdb-client router-prompt design. Do not edit without
# coordinating with the upstream yantrikdb research notes — this specific
# wording has been empirically validated vs alternatives.
MEMORY_ROUTER_SEED = """\
You have persistent memory in yantrikdb. Stored items are either procedures or rules.

First decide whether a stored procedure applies to the current problem or subtask.
If one applies, use that procedure only, from start to finish, and keep its conventions consistent. Do not mix it with other procedures, native methods, or shortcuts for the same task.
If no stored procedure applies, ignore stored procedures and reason normally.

Rules are local modifiers or exceptions: apply them when their condition is met, then continue normally.

If applicable stored items conflict, report the conflict instead of blending them.
"""


def _feature_config() -> dict:
    try:
        data = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    entry = data.get("yantrikdb_memory") or {}
    if not entry.get("enabled"):
        return {}
    cfg = dict(entry)
    if not cfg.get("url"):
        cfg["url"] = os.environ.get("YDB_URL", "http://localhost:7438")
    if not cfg.get("token"):
        cfg["token"] = os.environ.get("YDB_TOKEN", "")
    if not cfg.get("namespace"):
        repo_root = MEMORY_DIR.parent.parent
        digest = hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:12]
        cfg["namespace"] = f"agentic-stack/{repo_root.name}/{digest}"
    return cfg


def reflect(question: str, top_k_per_type: int = 3) -> dict:
    """Run yantrikdb reflect and return a structured dict.

    Raises RuntimeError if feature disabled or SDK missing, so the caller
    can decide whether to fall back (e.g. to the existing memory_reflect.py)
    or skip the block entirely.
    """
    cfg = _feature_config()
    if not cfg:
        raise RuntimeError(
            "yantrikdb_memory feature disabled. Enable in .features.json "
            "or via onboarding wizard."
        )
    try:
        from yantrikdb import connect
    except ImportError as exc:
        raise RuntimeError(
            "yantrikdb-client not installed. pip install 'yantrikdb-client>=0.2.1'"
        ) from exc

    client = connect(cfg["url"], token=cfg["token"])
    try:
        r = client.reflect(
            question,
            namespace=cfg["namespace"],
            top_k_per_type=top_k_per_type,
            include_conflicts=False,  # v0.2.1 default; conflicts pollute prompts
        )
    finally:
        client.close()

    def _serialize(mems):
        return [
            {
                "rid": m.rid,
                "text": m.text[:240] + ("…" if len(m.text) > 240 else ""),
                "certainty": round(getattr(m, "certainty", 1.0), 2),
                "importance": round(m.importance, 2),
                "source": (m.metadata or {}).get("source_path", ""),
            }
            for m in mems
        ]

    return {
        "question": question,
        "self_model": _serialize(r.self_model),
        "rules": _serialize(r.rules),
        "hypotheses": _serialize(r.hypotheses),
        "constraints": _serialize(r.constraints),
        "goals": _serialize(r.goals),
        "arcs": _serialize(r.arcs),
        "recent_signals": _serialize(r.recent_signals),
    }


def render_block(state: dict, *, include_router: bool = True) -> str:
    """Compact text block ready for agent system-prompt injection.

    Router seed prompt (if included) goes first because it frames how the
    agent should treat the subsequent content.
    """
    blocks = []
    if include_router:
        blocks.append(MEMORY_ROUTER_SEED.rstrip())
        blocks.append("")
    blocks.append(f"# Reflection on: {state['question']}")

    def _section(name: str, items: list, fmt):
        if not items:
            return
        blocks.append(f"\n## {name}")
        for it in items:
            blocks.append(f"- {fmt(it)}")

    _section("Self-model", state["self_model"],
             lambda x: f"{x['text']}  (certainty={x['certainty']})")
    _section("Rules / procedures", state["rules"],
             lambda x: f"{x['text']}  (importance={x['importance']})")
    _section("Open hypotheses", state["hypotheses"],
             lambda x: f"{x['text']}  (certainty={x['certainty']})")
    _section("Constraints", state["constraints"],
             lambda x: f"{x['text']}  (priority={x['importance']})")
    _section("Active goals", state["goals"], lambda x: x["text"])
    _section("Open narrative arcs", state["arcs"], lambda x: x["text"])
    _section("Recent learning signals", state["recent_signals"],
             lambda x: x["text"])
    return "\n".join(blocks)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("question", help="Current question/task to reflect around")
    p.add_argument("--top-k", type=int, default=3,
                   help="Max items per memory-type block (default 3)")
    p.add_argument("--bare", action="store_true",
                   help="Emit router + reflection only (no CLI scaffolding).")
    p.add_argument("--no-router", action="store_true",
                   help="Skip the memory-router seed prompt block.")
    p.add_argument("--json", action="store_true",
                   help="Machine-readable JSON output.")
    args = p.parse_args()

    try:
        state = reflect(args.question, top_k_per_type=args.top_k)
    except RuntimeError as exc:
        print(f"yantrikdb_reflect: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(state, indent=2, default=str))
        return 0

    block = render_block(state, include_router=not args.no_router)
    if args.bare:
        print(block)
    else:
        print("─" * 60)
        print(block)
        print("─" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
