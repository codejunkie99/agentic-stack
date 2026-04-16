"""List candidate lessons by status + priority.

Host-agent workflow: run this, pick the top N, review each with graduate.py
or reject.py. Priority = cluster_size * canonical_salience * age_factor, so
recurring + salient + aging items get attention first.
"""
import os, sys, json, argparse

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))

from review_state import list_candidates, candidate_priority

CANDIDATES = os.path.join(BASE, "memory/candidates")


def main():
    p = argparse.ArgumentParser(description="List candidate lessons.")
    p.add_argument("--status", default="staged",
                   choices=["staged", "rejected", "graduated"])
    p.add_argument("--sort", default="priority",
                   choices=["priority", "age"])
    p.add_argument("--limit", type=int, default=0,
                   help="Max to return; 0 = no limit.")
    p.add_argument("--format", default="human", choices=["human", "json"])
    args = p.parse_args()

    items = list_candidates(CANDIDATES, status=args.status, sort_by=args.sort)
    if args.limit:
        items = items[:args.limit]

    if args.format == "json":
        print(json.dumps(
            [{**c, "priority": round(candidate_priority(c), 3)} for c in items],
            indent=2))
        return

    if not items:
        print(f"No candidates with status={args.status}.")
        return

    print(f"=== {len(items)} candidate(s) — status={args.status} ===\n")
    for c in items:
        prio = candidate_priority(c)
        print(f"# {c.get('id')}  (priority={prio:.2f})")
        print(f"  claim:      {c.get('claim', '')}")
        print(f"  cluster:    {c.get('cluster_size', '?')} episode(s)")
        print(f"  salience:   {c.get('canonical_salience', 0):.2f}")
        print(f"  conditions: {c.get('conditions', [])}")
        print(f"  evidence:   {len(c.get('evidence_ids', []))} episode(s)")
        print(f"  rejections: {c.get('rejection_count', 0)}")
        print(f"  staged:     {c.get('staged_at', '?')}")
        dec = c.get("decisions", [])
        if dec:
            last = dec[-1]
            print(f"  last:       {last.get('action')} by "
                  f"{last.get('reviewer')} @ {last.get('ts', '')[:19]}")
        print()


if __name__ == "__main__":
    main()
