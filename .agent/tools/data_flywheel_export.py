#!/usr/bin/env python3
"""Export approved local runs into data-flywheel artifacts.

This creates the harness for future retrieval, evals, prompt shrinking, and
optional open-weight fine-tuning. It does not train a model, call an API, or
send telemetry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso(value: Any) -> str | None:
    parsed = parse_time(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def safe_num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return None if n != n else n


def slug(value: Any, fallback: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    out: list[str] = []
    last_sep = False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            last_sep = False
        elif not last_sep:
            out.append("_")
            last_sep = True
    cleaned = "".join(out).strip("_")
    return cleaned[:80] or fallback


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def unique_strings(values: list[Any]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quality = {"missing": False, "malformed_lines": 0}
    if not path.exists():
        quality["missing"] = True
        return [], quality

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                quality["malformed_lines"] += 1
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
            else:
                quality["malformed_lines"] += 1
    return records, quality


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def review_status(record: dict[str, Any]) -> str:
    review = record.get("human_review") if isinstance(record.get("human_review"), dict) else {}
    return str(record.get("human_review_status") or review.get("status") or "unknown")


def redaction_passed(record: dict[str, Any]) -> bool:
    return str(record.get("redaction_status") or "needs_review") == "passed"


def is_human_approved(record: dict[str, Any]) -> bool:
    return review_status(record) in {"accepted", "edited"}


def is_trainable(record: dict[str, Any]) -> bool:
    requested = record.get("trainable", True)
    if requested is False:
        return False
    if not is_human_approved(record) or not redaction_passed(record):
        return False
    if record.get("raw_input_stored") is True:
        return False
    return bool(record.get("input_redacted") and record.get("output_approved"))


def normalized_run(record: dict[str, Any], idx: int, project: str) -> dict[str, Any]:
    created_at = iso(record.get("created_at") or record.get("timestamp")) or now_iso()
    domain = slug(record.get("domain"), "general")
    workflow = slug(record.get("workflow"), "general")
    run_id = str(record.get("id") or f"run_{sha256(f'{created_at}|{domain}|{workflow}|{idx}')[:16]}")
    return {
        **record,
        "id": run_id,
        "created_at": created_at,
        "project": str(record.get("project") or project),
        "domain": domain,
        "workflow": workflow,
        "skill": str(record.get("skill") or record.get("agent_skill") or "data-flywheel"),
        "harness": str(record.get("harness") or record.get("host") or "unknown"),
        "human_review_status": review_status(record),
        "redaction_status": str(record.get("redaction_status") or "needs_review"),
        "pii_level": str(record.get("pii_level") or "unknown"),
        "raw_input_stored": bool(record.get("raw_input_stored") is True),
        "trainable": is_trainable(record),
    }


def trace_record(run: dict[str, Any]) -> dict[str, Any]:
    trace_id = str(run.get("trace_id") or f"trace_{sha256(run['id'])[:16]}")
    input_redacted = str(run.get("input_redacted") or "")
    human_review = run.get("human_review") if isinstance(run.get("human_review"), dict) else {}
    human_review.setdefault("status", run["human_review_status"])
    return {
        "id": trace_id,
        "created_at": run["created_at"],
        "project": run["project"],
        "domain": run["domain"],
        "workflow": run["workflow"],
        "skill": run["skill"],
        "host": run["harness"],
        "model_used": str(run.get("model_used") or "unknown"),
        "input_summary": str(run.get("input_summary") or ""),
        "input_hash": str(run.get("input_hash") or f"sha256:{sha256(input_redacted)}"),
        "raw_input_stored": False,
        "pii_level": run["pii_level"],
        "redaction_status": run["redaction_status"],
        "context_tokens_before": safe_num(run.get("context_tokens_before")),
        "context_tokens_after": safe_num(run.get("context_tokens_after")),
        "output_summary": str(run.get("output_summary") or ""),
        "human_review": human_review,
        "eval_tags": [str(x) for x in as_list(run.get("eval_tags"))],
        "failure_modes": [str(x) for x in as_list(run.get("failure_modes"))],
        "trainable": bool(run["trainable"]),
        "target_use": [str(x) for x in as_list(run.get("target_use") or ["retrieval", "eval"])],
        "model_target": run.get("model_target") if isinstance(run.get("model_target"), dict) else {
            "family": "open_weight_model_agnostic",
            "size_class": "unknown",
            "method": "unknown",
        },
        "source_run_id_hash": f"sha256:{sha256(run['id'])}",
    }


def training_example(run: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any] | None:
    if not run["trainable"]:
        return None
    return {
        "instruction": str(run.get("instruction") or "Complete this approved workflow using the provided context card."),
        "context": str(run.get("context") or f"Use the {run['domain']}_{run['workflow']} context card."),
        "input": str(run.get("input_redacted") or ""),
        "output": str(run.get("output_approved") or ""),
        "metadata": {
            "domain": run["domain"],
            "workflow": run["workflow"],
            "source_trace_ids": [trace["id"]],
            "split": str(run.get("split") or "train"),
            "pii_level": run["pii_level"],
            "trainable": True,
            "project": run["project"],
            "harness": run["harness"],
        },
    }


def eval_case(run: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any] | None:
    if not is_human_approved(run) or not redaction_passed(run):
        return None
    return {
        "id": str(run.get("eval_id") or f"eval_{sha256(trace['id'])[:16]}"),
        "domain": run["domain"],
        "workflow": run["workflow"],
        "input_redacted": str(run.get("input_redacted") or ""),
        "expected_behavior": unique_strings(as_list(run.get("expected_behavior")) or [run.get("output_summary") or "Match the human-approved output intent."]),
        "forbidden_behavior": unique_strings(as_list(run.get("forbidden_behavior")) + as_list(run.get("failure_modes"))),
        "rubric": unique_strings(as_list(run.get("rubric")) or [
            "Use only redacted/supplied facts.",
            "Separate facts from assumptions.",
            "Do not invent missing details.",
            "Respect the workflow's human approval gates.",
        ]),
        "tags": unique_strings(as_list(run.get("eval_tags")) + [run["domain"], run["workflow"]]),
        "source_trace_ids": [trace["id"]],
    }


def grouped_runs(runs: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for run in runs:
        groups.setdefault((run["domain"], run["workflow"]), []).append(run)
    return groups


def context_card(domain: str, workflow: str, runs: list[dict[str, Any]], eval_refs: list[str]) -> dict[str, Any]:
    stable_rules = unique_strings([rule for run in runs for rule in as_list(run.get("stable_rules"))])
    tool_contracts = unique_strings([contract for run in runs for contract in as_list(run.get("tool_contracts"))])
    approval_gates = unique_strings([gate for run in runs for gate in as_list(run.get("human_approval_required_for"))])
    if not approval_gates:
        approval_gates = ["client-facing messages", "compliance-sensitive outputs", "PII-bearing outputs"]
    after_values = [safe_num(run.get("context_tokens_after")) for run in runs]
    after_clean = [v for v in after_values if v is not None]
    token_budget = int(sum(after_clean) / len(after_clean)) if after_clean else 1000
    return {
        "id": f"context_{domain}_{workflow}_v1",
        "domain": domain,
        "workflow": workflow,
        "goal": str(runs[0].get("goal") or f"Make {workflow} reusable for {domain} workflows."),
        "stable_rules": stable_rules or ["Use only supplied facts.", "Ask for missing required fields.", "Keep human approval gates explicit."],
        "tool_contracts": tool_contracts,
        "human_approval_required_for": approval_gates,
        "source_trace_count": len(runs),
        "token_budget": token_budget,
        "eval_refs": eval_refs,
        "version": "v1",
    }


def context_card_md(card: dict[str, Any]) -> str:
    def bullets(values: list[Any]) -> str:
        return "\n".join(f"- {value}" for value in values) if values else "- none yet"

    return f"""# {card['domain']} / {card['workflow']} Context Card

ID: `{card['id']}`
Version: `{card['version']}`
Token budget: `{card['token_budget']}`
Source traces: `{card['source_trace_count']}`

## Goal

{card['goal']}

## Stable Rules

{bullets(card['stable_rules'])}

## Tool Contracts

{bullets(card['tool_contracts'])}

## Human Approval Required For

{bullets(card['human_approval_required_for'])}

## Eval References

{bullets(card['eval_refs'])}
"""


def workflow_metrics(runs: list[dict[str, Any]], eval_count: int) -> dict[str, Any]:
    accepted = sum(1 for run in runs if run["human_review_status"] == "accepted")
    edited = sum(1 for run in runs if run["human_review_status"] == "edited")
    rejected = sum(1 for run in runs if run["human_review_status"] == "rejected")
    trainable = sum(1 for run in runs if run["trainable"])
    total = len(runs)
    acceptance_rate = round((accepted + edited) / total, 3) if total else 0
    return {
        "traces": total,
        "accepted": accepted,
        "edited": edited,
        "rejected": rejected,
        "trainable": trainable,
        "eval_cases": eval_count,
        "acceptance_rate": acceptance_rate,
        "slm_candidate": trainable >= 500 and acceptance_rate >= 0.8,
        "reason": "High-volume, high-acceptance, redacted workflow." if trainable >= 500 and acceptance_rate >= 0.8 else "Keep collecting approved, redacted examples before considering adapter work.",
    }


def build_metrics(runs: list[dict[str, Any]], eval_cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    accepted = sum(1 for run in runs if run["human_review_status"] == "accepted")
    edited = sum(1 for run in runs if run["human_review_status"] == "edited")
    trainable = sum(1 for run in runs if run["trainable"])
    redacted = sum(1 for run in runs if redaction_passed(run))
    before_values = [safe_num(run.get("context_tokens_before")) for run in runs]
    after_values = [safe_num(run.get("context_tokens_after")) for run in runs]
    before_clean = [v for v in before_values if v is not None]
    after_clean = [v for v in after_values if v is not None]
    avg_before = round(sum(before_clean) / len(before_clean), 2) if before_clean else None
    avg_after = round(sum(after_clean) / len(after_clean), 2) if after_clean else None
    reduction = round((avg_before - avg_after) / avg_before * 100, 2) if avg_before and avg_after is not None else None
    eval_by_workflow: dict[tuple[str, str], int] = {}
    for case in eval_cases:
        key = (str(case.get("domain")), str(case.get("workflow")))
        eval_by_workflow[key] = eval_by_workflow.get(key, 0) + 1
    return {
        "generated_at": now_iso(),
        "privacy_model": "local_only_redacted_by_default",
        "total_traces": total,
        "accepted_traces": accepted + edited,
        "trainable_traces": trainable,
        "redaction_pass_rate": round(redacted / total, 3) if total else 0,
        "avg_context_tokens_before": avg_before,
        "avg_context_tokens_after": avg_after,
        "context_reduction_pct": reduction,
        "thresholds": {
            "context_card": "10-25 approved runs",
            "eval_set": "25-100 approved runs",
            "measurement": "100-300 approved runs",
            "narrow_adapter_candidate": "500-1500 high-quality examples",
            "workflow_family_corpus": "2000-10000+ clean examples",
        },
        "workflows": {
            f"{domain}/{workflow}": workflow_metrics(group, eval_by_workflow.get((domain, workflow), 0))
            for (domain, workflow), group in sorted(grouped_runs(runs).items())
        },
    }


def export(args: argparse.Namespace) -> Path:
    agent_root = Path(args.agent_root).resolve()
    flywheel_dir = agent_root / "flywheel"
    input_path = Path(args.approved_runs) if args.approved_runs else flywheel_dir / "approved-runs.jsonl"
    out_dir = Path(args.out) if args.out else flywheel_dir / "exports" / args.date

    raw_runs, input_quality = read_jsonl(input_path)
    runs = [normalized_run(record, idx, args.project) for idx, record in enumerate(raw_runs)]
    traces = [trace_record(run) for run in runs]
    trace_by_run = {run["id"]: trace for run, trace in zip(runs, traces)}
    training_examples = [example for run in runs if (example := training_example(run, trace_by_run[run["id"]]))]
    eval_cases = [case for run in runs if (case := eval_case(run, trace_by_run[run["id"]]))]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "trace-records.jsonl", traces)
    write_jsonl(out_dir / "training-examples.jsonl", training_examples)
    write_jsonl(out_dir / "eval-cases.jsonl", eval_cases)

    eval_refs: dict[tuple[str, str], list[str]] = {}
    for case in eval_cases:
        key = (str(case["domain"]), str(case["workflow"]))
        eval_refs.setdefault(key, []).append(f"eval-cases.jsonl#{case['id']}")

    cards = []
    for (domain, workflow), group in sorted(grouped_runs(runs).items()):
        card = context_card(domain, workflow, group, eval_refs.get((domain, workflow), []))
        cards.append(card)
        write_json(out_dir / "context-cards" / domain / f"{workflow}.json", card)
        write_text(out_dir / "context-cards" / domain / f"{workflow}.md", context_card_md(card))

    metrics = build_metrics(runs, eval_cases)
    metrics["input_quality"] = input_quality
    write_json(out_dir / "context-cards.json", cards)
    write_json(out_dir / "flywheel-metrics.json", metrics)
    write_text(
        out_dir / "README.md",
        f"""# Data Flywheel Export

Generated: {metrics['generated_at']}

Artifacts:

- `trace-records.jsonl`
- `training-examples.jsonl`
- `eval-cases.jsonl`
- `context-cards/`
- `flywheel-metrics.json`

This export is local-only. Review redaction status and human approval before
moving any artifact outside `.agent/flywheel/`.
""",
    )
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Export approved runs into local data-flywheel artifacts.")
    parser.add_argument("--agent-root", default=".agent")
    parser.add_argument("--approved-runs", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--project", default=Path.cwd().name)
    args = parser.parse_args()
    out_dir = export(args)
    print(f"agentic-stack data flywheel export: {out_dir}")
    print(f"metrics={out_dir / 'flywheel-metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
