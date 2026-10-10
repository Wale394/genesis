"""Contracts for recording validated investigation outcomes."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from .evidence_contract import Evidence


class InvestigationFindingStatus(str, Enum):
    OBSERVED = "OBSERVED"
    HYPOTHESIS = "HYPOTHESIS"
    VALIDATED = "VALIDATED"
    REFUTED = "REFUTED"


@dataclass(frozen=True)
class InvestigationFinding:
    """A finding produced by an investigation, with explicit epistemic status."""

    finding_id: str
    statement: str
    status: InvestigationFindingStatus
    evidence_refs: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    source: str = "investigation"
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.finding_id:
            raise ValueError("finding_id is required.")
        if not self.statement:
            raise ValueError("finding statement cannot be empty.")
        if not self.source:
            raise ValueError("finding source cannot be empty.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "statement": self.statement,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
            "context": dict(self.context),
            "limitations": list(self.limitations),
            "source": self.source,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class InvestigationOutcome:
    """The result of an investigation cycle."""

    investigation_id: str
    status: str
    findings: List[InvestigationFinding] = field(default_factory=list)
    new_evidence: List[Evidence] = field(default_factory=list)
    new_evidence_refs: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.investigation_id:
            raise ValueError("investigation_id is required.")
        if not self.status:
            raise ValueError("investigation status is required.")

    @property
    def validated_findings(self) -> List[InvestigationFinding]:
        return [
            finding
            for finding in self.findings
            if finding.status is InvestigationFindingStatus.VALIDATED
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "status": self.status,
            "findings": [finding.to_dict() for finding in self.findings],
            "new_evidence": [item.to_dict() for item in self.new_evidence],
            "new_evidence_refs": list(self.new_evidence_refs),
            "next_actions": list(self.next_actions),
            "limitations": list(self.limitations),
        }
