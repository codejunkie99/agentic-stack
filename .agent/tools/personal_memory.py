#!/usr/bin/env python3
"""Read-only personal profile and relevant-memory tool for coding agents."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from harness_manager.workspaces.personal_memory import profile


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read the personal profile available to this agent run.")
    parser.add_argument("query", nargs="?", default="", help="Optional intent to find relevant profile memory")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    print(json.dumps(profile(root, args.query, args.limit), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
