"""End-to-end demo of the yantrikdb memory backend [BETA].

Runs the happy path:
  1. Confirm the feature is enabled
  2. Sync .agent/memory/ into yantrikdb (incremental)
  3. Recall against the synced namespace with a sample query
  4. Reflect on a sample task and render the router-seed + state block

Run:
    # Enable via onboarding first:
    agentic-stack <harness> --reconfigure
    # Answer "yes" to "Enable YantrikDB memory backend [BETA]?"

    # Install the client:
    pip install 'yantrikdb-client[embed]>=0.2.1'

    # Point at your server (or rely on .features.json values):
    export YDB_URL=http://localhost:7438
    export YDB_TOKEN=ydb_...

    # Run the demo:
    python3 examples/yantrikdb_quickstart.py
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / ".agent" / "memory"))
sys.path.insert(0, str(ROOT / ".agent" / "tools"))


def main() -> int:
    from yantrikdb_sync import feature_config, run_sync, show_status

    cfg = feature_config()
    if not cfg:
        print("feature disabled. Run `agentic-stack <harness> --reconfigure` "
              "and opt into YantrikDB memory [BETA], then set YDB_URL/YDB_TOKEN "
              "or fill .features.json.")
        return 2

    print(f"yantrikdb server: {cfg['url']}")
    print(f"namespace:        {cfg['namespace']}\n")

    # 1. sync
    print("=== sync ===")
    summary = run_sync(full=False, dry_run=False)
    print(json.dumps(summary, indent=2))
    show_status()

    # 2. recall
    print("\n=== recall ===")
    try:
        from yantrikdb_recall import recall, _render_pretty
        q = "lessons about test strategy"
        items = recall(q, top_k=5)
        print(_render_pretty(q, items))
    except Exception as exc:
        print(f"recall error: {exc}")

    # 3. reflect
    print("\n=== reflect ===")
    try:
        from yantrikdb_reflect import reflect, render_block
        state = reflect("task: refactor authentication", top_k_per_type=3)
        print(render_block(state, include_router=True))
    except Exception as exc:
        print(f"reflect error: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
