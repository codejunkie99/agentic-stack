#!/usr/bin/env python3
"""
Capability-aware orchestration helpers for deckster-slide-generator.

This module does not call any vendor-specific sub-agent API. It produces the
execution plan and worker boundaries that a server-side wrapper can map onto
its own sub-agent runtime.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from contracts import DeckPlan, SlideSpec, WorkerAssignment
from runtime_capabilities import detect_runtime_capabilities


SPECIALTY_BY_EVIDENCE = {
    "chart": "charts",
    "framework": "frameworks",
    "table": "frameworks",
    "process": "process",
    "timeline": "process",
    "image": "layouts",
}

SPECIALTY_BY_LAYOUT = {
    "green_left_arrow": "layouts",
    "green_one_third": "layouts",
    "green_highlight": "layouts",
    "arrow_half": "layouts",
    "green_half": "layouts",
    "green_two_third": "layouts",
}

REFERENCE_BY_SPECIALTY = {
    "charts": ["references/charts/index.md"],
    "frameworks": ["references/frameworks/index.md"],
    "process": ["references/process/index.md"],
    "layouts": ["references/layouts/index.md"],
}


def _coerce_slide_specs(payload) -> list[SlideSpec]:
    slides = []
    for index, item in enumerate(payload or [], start=1):
        if isinstance(item, SlideSpec):
            slides.append(item)
            continue
        slides.append(
            SlideSpec(
                slide_number=item.get("slide_number", index),
                title=item.get("title", ""),
                kind=item.get("kind", "content"),
                story_role=item.get("story_role", ""),
                relationship=item.get("relationship", ""),
                evidence_type=item.get("evidence_type", ""),
                layout_family=item.get("layout_family", ""),
                primary_reference=item.get("primary_reference", ""),
                detail=bool(item.get("detail", True)),
                pattern=item.get("pattern", {}) or {},
                metadata=item.get("metadata", {}) or {},
            )
        )
    return slides


def _specialty_for_slide(slide: SlideSpec) -> str:
    if slide.kind != "content":
        return "structural"
    if slide.evidence_type in SPECIALTY_BY_EVIDENCE:
        return SPECIALTY_BY_EVIDENCE[slide.evidence_type]
    if slide.layout_family in SPECIALTY_BY_LAYOUT:
        return SPECIALTY_BY_LAYOUT[slide.layout_family]
    if slide.primary_reference:
        if "/charts/" in slide.primary_reference:
            return "charts"
        if "/frameworks/" in slide.primary_reference:
            return "frameworks"
        if "/process/" in slide.primary_reference:
            return "process"
    return "layouts"


def build_worker_assignments(slides, capabilities=None) -> list[WorkerAssignment]:
    capabilities = capabilities or detect_runtime_capabilities()
    slide_specs = _coerce_slide_specs(slides)
    if not capabilities.supports_subagents:
        return []

    buckets: dict[tuple[str, str], list[SlideSpec]] = defaultdict(list)
    for slide in slide_specs:
        specialty = _specialty_for_slide(slide)
        buckets[("build", specialty)].append(slide)
        if slide.kind == "content":
            buckets[("qa", "qa-inspector")].append(slide)

    assignments = [
        WorkerAssignment(
            stage="plan",
            owner="parent",
            specialty="planner",
            references=["references/runtime/plan.md"],
            notes=[
                "Parent planner locks audience, recommendation, slide count, and section rhythm before fan-out.",
                "Only slide-level enrichment may fan out after the storyline is locked.",
            ],
        )
    ]

    for (stage, specialty), grouped in sorted(buckets.items()):
        references = REFERENCE_BY_SPECIALTY.get(specialty, [])
        if stage == "qa":
            references = ["references/runtime/qa.md"]
        assignments.append(
            WorkerAssignment(
                stage=stage,
                owner="worker",
                specialty=specialty,
                slide_numbers=[slide.slide_number for slide in grouped],
                references=references,
                notes=[
                    "Workers operate on isolated inputs only.",
                    "Final assembly and blocking decisions stay with the parent reducer.",
                ],
            )
        )

    assignments.extend(
        [
            WorkerAssignment(
                stage="build-reducer",
                owner="parent",
                specialty="assembly",
                references=["references/runtime/build.md", "references/runtime/orchestration.md"],
                notes=[
                    "Own slide numbering, relationship rewrites, media copy, and final PPTX packaging.",
                ],
            ),
            WorkerAssignment(
                stage="qa-reducer",
                owner="parent",
                specialty="qa-reducer",
                references=["references/runtime/qa.md", "references/runtime/orchestration.md"],
                notes=[
                    "Own cross-deck consistency checks, fix batching, and the final QA checkpoint.",
                ],
            ),
        ]
    )
    return assignments


def build_execution_plan(deck_plan, capabilities=None) -> dict:
    capabilities = capabilities or detect_runtime_capabilities()
    if isinstance(deck_plan, DeckPlan):
        plan = deck_plan
    else:
        payload = deck_plan or {}
        plan = DeckPlan(
            deck_title=payload.get("deck_title", ""),
            subtitle=payload.get("subtitle", ""),
            date=payload.get("date", ""),
            reference_files=list(payload.get("reference_files", [])),
            slide_specs=_coerce_slide_specs(payload.get("slide_specs", [])),
            unresolved_questions=list(payload.get("unresolved_questions", [])),
        )

    sequential_stage_notes = [
        "Use one agent for all phases.",
        "Stop for user approval after planning and after QA.",
    ]
    orchestrated_stage_notes = [
        "Parent planner still owns storyline and user checkpoints.",
        "Fan out slide-level enrichment, isolated build workers, and per-slide QA inspectors.",
    ]

    return {
        "workflow_mode": capabilities.workflow_mode,
        "supports_subagents": capabilities.supports_subagents,
        "summary": {
            "slides": len(plan.slide_specs),
            "reference_files": len(plan.reference_files),
            "unresolved_questions": len(plan.unresolved_questions),
        },
        "stage_notes": orchestrated_stage_notes if capabilities.supports_subagents else sequential_stage_notes,
        "worker_assignments": [assignment.to_dict() for assignment in build_worker_assignments(plan.slide_specs, capabilities=capabilities)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path, help="JSON file containing a DeckPlan-like payload.")
    args = parser.parse_args()

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    plan = build_execution_plan(payload)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
