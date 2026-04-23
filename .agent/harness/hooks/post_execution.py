"""Runs after every action. Appends a structured entry to episodic memory."""
import datetime, os
from ._provenance import build_source
from ._episodic_io import append_jsonl

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
EPISODIC = os.path.join(ROOT, "memory/episodic/AGENT_LEARNINGS.jsonl")


def log_execution(skill_name, action, result, success, reflection="",
                  importance=5, confidence=0.5, evidence_ids=None,
                  pain_score=None):
    """Log a structured episodic entry.

    pain_score: override the default (2 for success, 7 for failure). Pass
    a higher value (e.g. 5) for high-importance successful operations so
    recurring patterns cross the dream-cycle promotion threshold (7.0).
    """
    if pain_score is None:
        pain_score = 2 if success else 7
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "skill": skill_name,
        "action": action[:200],
        "result": "success" if success else "failure",
        "detail": str(result)[:500],
        "pain_score": pain_score,
        "importance": importance,
        "reflection": reflection,
        "confidence": confidence,
        "source": build_source(skill_name),
        "evidence_ids": list(evidence_ids) if evidence_ids else [],
    }
    return append_jsonl(EPISODIC, entry)
