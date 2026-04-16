"""Move a rejected candidate back to the staged pool.

Use this when a previous rejection was wrong, or when new evidence changes
the picture. Decision history and rejection_count survive the reopen — the
next reviewer sees the full churn log.
"""
import os, sys, argparse

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))

from review_state import mark_reopened

CANDIDATES = os.path.join(BASE, "memory/candidates")


def main():
    p = argparse.ArgumentParser(description="Reopen a rejected candidate.")
    p.add_argument("candidate_id")
    p.add_argument("--reviewer", default="host-agent")
    args = p.parse_args()

    try:
        cand = mark_reopened(args.candidate_id, args.reviewer, CANDIDATES)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"reopened {args.candidate_id} "
          f"(rejection_count={cand.get('rejection_count', 0)})")


if __name__ == "__main__":
    main()
