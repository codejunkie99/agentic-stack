"""Deterministic, auditable model routing for agent runs.

The native app only selects a policy. Agents and the workspace service call
this module to turn that policy into an available model and effort level.
"""
from __future__ import annotations

import re

ROUTING_POLICIES = {"fixed", "auto:cost", "auto:balanced", "auto:intelligence"}

_COMPLEX = re.compile(
    r"\b(?:architect|architecture|audit|debug|investigate|migrat|refactor|research|security|"
    r"system design|root cause|multi[- ]step|production|release|deploy|entire app|end[- ]to[- ]end)\b",
    re.IGNORECASE,
)
_QUICK = re.compile(
    r"\b(?:quick(?:ly)?|brief|short|rename|format|typo|explain|summari[sz]e|find|locate|list|one[- ]line)\b",
    re.IGNORECASE,
)


def routing_policy(value):
    if value is None or value == "":
        return "fixed"
    if not isinstance(value, str) or value not in ROUTING_POLICIES:
        raise ValueError("Choose Fixed, Auto Cost, Auto Balance, or Auto Intelligence routing.")
    return value


def _tier(model, runner):
    value = model.lower()
    if runner == "claude-code":
        if "haiku" in value:
            return "fast"
        if "sonnet" in value:
            return "balanced"
        if any(token in value for token in ("fable", "opus", "best")):
            return "deep"
        return "balanced"
    if any(token in value for token in ("luna", "spark", "mini", "flash")):
        return "fast"
    if any(token in value for token in ("astra", "sol", "pro", "max")):
        return "deep"
    return "balanced"


def describe_model(model, runner):
    """Return display metadata without claiming unavailable provider details."""
    tier = _tier(model, runner)
    text_only = runner == "codex" and "spark" in model.lower()
    capabilities = ["text", "tools", "files"] + ([] if text_only else ["image"])
    summaries = {
        "fast": "Fast for scoped work and short feedback loops",
        "balanced": "Balanced for everyday coding and tool use",
        "deep": "Deep reasoning for complex, multi-step work",
    }
    return {"tier": tier, "capabilities": capabilities, "summary": summaries[tier]}


def enrich_choice(choice):
    result = dict(choice)
    result.update(describe_model(str(choice.get("id", "")), str(choice.get("runner", "codex"))))
    return result


def _signals(task, attachments):
    task = task.strip()
    media = sorted({str(item.get("kind") or "file") for item in attachments if isinstance(item, dict)})
    score = 0
    reasons = []
    if _COMPLEX.search(task):
        score += 3
        reasons.append("complex task language")
    if len(task) > 900:
        score += 2
        reasons.append("large instruction")
    elif len(task) > 350:
        score += 1
    if task.count("\n") >= 8:
        score += 1
    if media:
        score += 1
        reasons.append("attached " + ", ".join(media))
    if _QUICK.search(task) and score < 3:
        score -= 1
        reasons.append("scoped request")
    complexity = "deep" if score >= 3 else "fast" if score <= -1 else "balanced"
    return complexity, reasons, score


def _supports_attachments(choice, attachments):
    if not attachments:
        return True
    kinds = {str(item.get("kind") or "file") for item in attachments if isinstance(item, dict)}
    capabilities = choice.get("capabilities", [])
    if "image" in kinds and "image" not in capabilities:
        return False
    if kinds - {"image"} and "files" not in capabilities:
        return False
    return True


def _effort(choice, complexity, policy):
    levels = [value for value in choice.get("efforts", []) if isinstance(value, str)]
    if not levels:
        return ""
    if policy == "auto:cost":
        order = ["low", "medium", "high", "xhigh", "max"]
    elif policy == "auto:intelligence" or complexity == "deep":
        order = ["xhigh", "high", "max", "medium", "low"]
    elif complexity == "fast":
        order = ["low", "medium", "high", "xhigh", "max"]
    else:
        order = ["medium", "high", "low", "xhigh", "max"]
    return next((level for level in order if level in levels), "")


def recommend(runner, task, policy, choices, attachments=()):
    """Recommend one model from the live runner catalog.

    Routing never changes runner, permissions, or project. The response is
    intentionally small enough to store on the run as an audit record.
    """
    policy = routing_policy(policy)
    if runner not in {"codex", "claude-code"}:
        raise ValueError("Choose Codex or Claude Code as the runner.")
    available = [enrich_choice(row) for row in choices
                 if isinstance(row, dict) and row.get("runner") == runner and row.get("id")]
    complexity, signals, score = _signals(task, attachments)
    if policy == "fixed":
        return {"policy": policy, "model": "", "effort": "", "complexity": complexity,
                "reason": "Fixed selection; the router did not choose a model.",
                "confidence": 1.0, "signals": signals, "fallback": False, "candidateCount": len(available)}
    if not available:
        return {"policy": policy, "model": "", "effort": "", "complexity": complexity,
                "reason": "No live catalog was available; using the runner default.",
                "confidence": 0.0, "signals": signals, "fallback": True, "candidateCount": 0}

    desired = {"auto:cost": "fast", "auto:balanced": complexity,
               "auto:intelligence": "deep"}[policy]
    base = {"fast": {"fast": 90, "balanced": 55, "deep": 20},
            "balanced": {"fast": 55, "balanced": 90, "deep": 65},
            "deep": {"fast": 20, "balanced": 65, "deep": 90}}[desired]
    compatible = [row for row in available if _supports_attachments(row, attachments)]
    fallback = bool(attachments) and not compatible
    candidates = compatible or available
    ranked = sorted(enumerate(candidates), key=lambda pair: (-base[pair[1]["tier"]], pair[0]))
    choice = ranked[0][1]
    reason = {
        "auto:cost": "Cost mode selected a fast available model",
        "auto:balanced": "Balance mode matched the model to a " + complexity + " request",
        "auto:intelligence": "Intelligence mode selected a deep-reasoning model",
    }[policy]
    if signals:
        reason += " (" + "; ".join(signals[:3]) + ")"
    confidence = 0.9 if choice["tier"] == desired else 0.68
    if abs(score) >= 3 and policy == "auto:balanced":
        confidence = min(0.96, confidence + 0.04)
    if fallback:
        confidence = min(confidence, 0.45)
        reason += "; no catalog model declared every requested media capability"
    return {"policy": policy, "model": choice["id"],
            "effort": _effort(choice, complexity, policy),
            "complexity": complexity, "reason": reason + ".",
            "confidence": confidence, "signals": signals, "fallback": fallback,
            "candidateCount": len(candidates)}
