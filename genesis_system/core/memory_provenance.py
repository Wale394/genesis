"""Provenance and reuse rules for historical reliability memory."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MemorySourceType(str, Enum):
    INVESTIGATION = "investigation"
    MACHINE = "machine"
    HUMAN = "human"
    COMBINED = "combined"
    UNKNOWN = "unknown"


class ProvenanceStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


class MemoryReuseStance(str, Enum):
    SUPPORT = "SUPPORT"
    CAUTION = "CAUTION"
    EXCLUDE = "EXCLUDE"


@dataclass(frozen=True)
class MemoryProvenance:
    """Traceability information attached to a historical finding."""

    source: str
    source_type: MemorySourceType = MemorySourceType.INVESTIGATION
    evidence_refs: List[str] = field(default_factory=list)
    validation_refs: List[str] = field(default_factory=list)
    contributor_refs: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("Memory provenance source cannot be empty.")

    def status(self) -> ProvenanceStatus:
        if not self.source:
            return ProvenanceStatus.MISSING
        if self.evidence_refs and self.validation_refs:
            return ProvenanceStatus.COMPLETE
        return ProvenanceStatus.PARTIAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_type": self.source_type.value,
            "evidence_refs": list(self.evidence_refs),
            "validation_refs": list(self.validation_refs),
            "contributor_refs": list(self.contributor_refs),
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
            "limitations": list(self.limitations),
            "status": self.status().value,
        }


def assess_memory_reuse(status: str, provenance: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return an explicit, non-numeric reuse stance for a historical finding."""
    provenance = provenance or {}
    evidence_refs = provenance.get("evidence_refs") or []
    validation_refs = provenance.get("validation_refs") or []
    source = provenance.get("source")

    if status == "REFUTED":
        return {
            "provenance_status": "PARTIAL" if provenance else "MISSING",
            "reuse_stance": MemoryReuseStance.EXCLUDE.value,
            "reasons": ["Finding was explicitly refuted."],
        }

    if status in {"OBSERVED", "HYPOTHESIS"}:
        return {
            "provenance_status": "COMPLETE" if source and evidence_refs else ("PARTIAL" if provenance else "MISSING"),
            "reuse_stance": MemoryReuseStance.CAUTION.value,
            "reasons": ["Finding is not a validated conclusion."],
        }

    if status != "VALIDATED":
        return {
            "provenance_status": "PARTIAL" if provenance else "MISSING",
            "reuse_stance": MemoryReuseStance.CAUTION.value,
            "reasons": ["Finding status is not recognized as validated."],
        }

    if source and evidence_refs and validation_refs:
        return {
            "provenance_status": ProvenanceStatus.COMPLETE.value,
            "reuse_stance": MemoryReuseStance.SUPPORT.value,
            "reasons": ["Validated finding has traceable source, evidence, and validation references."],
        }

    return {
        "provenance_status": ProvenanceStatus.PARTIAL.value if provenance else ProvenanceStatus.MISSING.value,
        "reuse_stance": MemoryReuseStance.CAUTION.value,
        "reasons": ["Validated finding lacks complete provenance for strong reuse."],
    }
