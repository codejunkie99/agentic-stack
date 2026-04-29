"""
Structured handoff artifacts for sequential and orchestrated deck workflows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DeckRequest:
    audience: str = ""
    objective: str = ""
    recommendation: str = ""
    deck_length: str = ""
    template_name: str | None = None
    source_materials: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SlideSpec:
    slide_number: int
    title: str
    kind: str = "content"
    story_role: str = ""
    relationship: str = ""
    evidence_type: str = ""
    layout_family: str = ""
    primary_reference: str = ""
    detail: bool = True
    pattern: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeckPlan:
    deck_title: str = ""
    subtitle: str = ""
    date: str = ""
    reference_files: list[str] = field(default_factory=list)
    slide_specs: list[SlideSpec] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["slide_specs"] = [slide.to_dict() for slide in self.slide_specs]
        return payload


@dataclass
class WorkerAssignment:
    stage: str
    owner: str
    specialty: str
    slide_numbers: list[int] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SlideArtifact:
    slide_number: int
    artifact_path: str
    layout_key: str = ""
    media_paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QAFinding:
    slide_number: int
    severity: str
    message: str
    source: str = "programmatic"
    suggested_fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FixBatch:
    blocking_findings: list[QAFinding] = field(default_factory=list)
    advisory_findings: list[QAFinding] = field(default_factory=list)
    affected_slides: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocking_findings": [finding.to_dict() for finding in self.blocking_findings],
            "advisory_findings": [finding.to_dict() for finding in self.advisory_findings],
            "affected_slides": list(self.affected_slides),
        }
