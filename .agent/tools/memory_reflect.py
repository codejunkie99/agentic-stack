"""Reflection utility. Call from any skill after significant events."""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "harness"))
from hooks.post_execution import log_execution
from hooks.on_failure import on_failure


def reflect(skill_name, action, outcome, success=True, importance=5,
            reflection="", error=None, confidence=None, evidence_ids=None):
    if success:
        return log_execution(skill_name, action, outcome, True,
                             reflection=reflection, importance=importance,
                             confidence=0.5 if confidence is None else confidence,
                             evidence_ids=evidence_ids)
    return on_failure(skill_name, action, error or outcome,
                      context=reflection,
                      confidence=0.9 if confidence is None else confidence,
                      evidence_ids=evidence_ids)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("skill")
    p.add_argument("action")
    p.add_argument("outcome")
    p.add_argument("--fail", action="store_true")
    p.add_argument("--importance", type=int, default=5)
    p.add_argument("--note", default="")
    p.add_argument("--confidence", type=float, default=None)
    p.add_argument("--evidence", nargs="*", default=None,
                   help="Space-separated episode/lesson IDs this entry builds on.")
    args = p.parse_args()
    print(reflect(args.skill, args.action, args.outcome,
                  success=not args.fail, importance=args.importance,
                  reflection=args.note, confidence=args.confidence,
                  evidence_ids=args.evidence))
