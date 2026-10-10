"""Controlled retrieval of historical reliability findings.

Retrieval is advisory evidence only. It never converts historical memory into
current truth and never returns hypotheses as validated findings.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .reliability_memory import ReliabilityMemory
from .memory_provenance import assess_memory_reuse


@dataclass(frozen=True)
class MemoryQuery:
    """Explicit retrieval context used to search historical findings."""

    robot_type: Optional[str] = None
    manufacturer: Optional[str] = None
    signals: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    statement: Optional[str] = None


@dataclass(frozen=True)
class MemoryMatch:
    """A historical finding with explicit relevance and epistemic status."""

    finding_id: str
    investigation_id: str
    statement: str
    status: str
    similarity_reasons: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    provenance_status: str = "MISSING"
    reuse_stance: str = "CAUTION"
    reuse_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "investigation_id": self.investigation_id,
            "statement": self.statement,
            "status": self.status,
            "similarity_reasons": list(self.similarity_reasons),
            "context": dict(self.context),
            "evidence_refs": list(self.evidence_refs),
            "limitations": list(self.limitations),
            "provenance": dict(self.provenance),
            "provenance_status": self.provenance_status,
            "reuse_stance": self.reuse_stance,
            "reuse_reasons": list(self.reuse_reasons),
        }


class ReliabilityMemoryRetriever:
    """Retrieve historical findings without promoting them to current truth."""

    def __init__(self, memory: ReliabilityMemory):
        self.memory = memory

    def retrieve(self, query: MemoryQuery) -> Dict[str, Any]:
        matches: List[MemoryMatch] = []
        unresolved = []
        validated = []
        refuted = []

        for entry in self.memory.investigations():
            investigation = entry.get("investigation", {})
            investigation_id = investigation.get("investigation_id")
            findings = investigation.get("findings", [])
            for finding in findings:
                reasons = self._similarity_reasons(query, finding)
                if not reasons:
                    continue
                status = finding.get("status", "UNKNOWN")
                provenance = finding.get("provenance") or {}
                reuse = assess_memory_reuse(status, provenance)
                match = MemoryMatch(
                    finding_id=finding.get("finding_id", ""),
                    investigation_id=investigation_id or "",
                    statement=finding.get("statement", ""),
                    status=status,
                    similarity_reasons=reasons,
                    context=finding.get("context", {}),
                    evidence_refs=finding.get("evidence_refs", []),
                    limitations=finding.get("limitations", []),
                    provenance=provenance,
                    provenance_status=reuse["provenance_status"],
                    reuse_stance=reuse["reuse_stance"],
                    reuse_reasons=reuse["reasons"],
                )
                matches.append(match)
                if status == "VALIDATED":
                    validated.append(match)
                elif status == "REFUTED":
                    refuted.append(match)
                elif status in {"OBSERVED", "HYPOTHESIS"}:
                    unresolved.append(match)

        conflicts = self._conflicts(validated, refuted)
        status = "AVAILABLE" if matches else "UNAVAILABLE"
        if conflicts:
            status = "CONFLICTING"

        return {
            "status": status,
            "match_count": len(matches),
            "validated_count": len(validated),
            "refuted_count": len(refuted),
            "unresolved_count": len(unresolved),
            "conflicts": conflicts,
            "findings": [match.to_dict() for match in matches],
            "validated_findings": [match.to_dict() for match in validated],
            "refuted_findings": [match.to_dict() for match in refuted],
            "unresolved_findings": [match.to_dict() for match in unresolved],
            "limitations": self._limitations(matches, conflicts),
        }

    @staticmethod
    def _similarity_reasons(query: MemoryQuery, finding: Dict[str, Any]) -> List[str]:
        context = finding.get("context") or {}
        reasons: List[str] = []

        # Only explicit, structured relationships create retrieval relevance.
        for key, label in (("robot_type", "same_robot_type"), ("manufacturer", "same_manufacturer")):
            value = getattr(query, key)
            if value is not None and context.get(key) == value:
                reasons.append(label)

        query_signals = set(query.signals)
        finding_signals = set(context.get("signals", []))
        if query_signals.intersection(finding_signals):
            reasons.append("shared_signal_context")

        for key, value in query.context.items():
            if context.get(key) == value:
                reasons.append(f"same_context:{key}")

        # Statement text is intentionally not used for semantic similarity in v0.1.
        # Avoiding text similarity prevents an unvalidated semantic match from
        # becoming an apparently strong historical relationship.
        return reasons

    @staticmethod
    def _conflicts(validated: List[MemoryMatch], refuted: List[MemoryMatch]) -> List[Dict[str, Any]]:
        conflicts = []
        for positive in validated:
            for negative in refuted:
                if positive.context == negative.context and positive.context:
                    conflicts.append({
                        "validated_finding_id": positive.finding_id,
                        "refuted_finding_id": negative.finding_id,
                        "reason": "Validated and refuted historical findings share the same explicit context.",
                    })
        return conflicts

    @staticmethod
    def _limitations(matches: List[MemoryMatch], conflicts: List[Dict[str, Any]]) -> List[str]:
        limitations = []
        if any(match.status in {"OBSERVED", "HYPOTHESIS"} for match in matches):
            limitations.append("Historical hypotheses and observations are retained as context, not validated truth.")
        if conflicts:
            limitations.append("Historical memory contains conflicting findings; retrieval must not resolve the conflict by voting.")
        if matches:
            limitations.append("Historical relevance does not establish causality or current-state equivalence.")
        return limitations
