"""Reject a staged candidate. Moves to rejected/ with a decision log entry.

The candidate is not deleted. Its decision history, including the reject
reason, is preserved. If the same pattern recurs and gets re-staged by
auto_dream, rejection_count will show the history — so the reviewer sees
churn instead of treating it as a fresh item.
"""
import os, sys, argparse

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))

from review_state import mark_rejected

CANDIDATES = os.path.join(BASE, "memory/candidates")


def main():
    p = argparse.ArgumentParser(description="Reject a staged candidate.")
    p.add_argument("candidate_id")
    p.add_argument("--reason", required=True,
                   help="Why it's being rejected. Required.")
    p.add_argument("--reviewer", default="host-agent")
    args = p.parse_args()

    try:
        rejected = mark_rejected(args.candidate_id, args.reviewer,
                                 args.reason, CANDIDATES)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"rejected {args.candidate_id} "
          f"(rejection_count={rejected.get('rejection_count', 1)})")


if __name__ == "__main__":
    main()
