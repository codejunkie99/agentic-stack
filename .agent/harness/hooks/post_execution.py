"""Runs after every action. Appends a structured entry to episodic memory."""
import json, datetime, os
from ._provenance import build_source

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
EPISODIC = os.path.join(ROOT, "memory/episodic/AGENT_LEARNINGS.jsonl")


def log_execution(skill_name, action, result, success, reflection="",
                  importance=5, confidence=0.5, evidence_ids=None):
    os.makedirs(os.path.dirname(EPISODIC), exist_ok=True)
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "skill": skill_name,
        "action": action[:200],
        "result": "success" if success else "failure",
        "detail": str(result)[:500],
        "pain_score": 2 if success else 7,
        "importance": importance,
        "reflection": reflection,
        "confidence": confidence,
        "source": build_source(skill_name),
        "evidence_ids": list(evidence_ids) if evidence_ids else [],
    }
    with open(EPISODIC, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry
