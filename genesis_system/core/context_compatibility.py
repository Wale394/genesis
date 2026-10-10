"""Context compatibility assessment for historical reliability findings.

Compatibility is a relevance assessment, not a truth or causality assessment.
Material unknowns remain UNKNOWN and require investigation rather than being
silently treated as compatible.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ContextRelationship(str, Enum):
    SAME = "SAME"
    DIFFERENT = "DIFFERENT"
    UNKNOWN = "UNKNOWN"


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    PARTIALLY_COMPATIBLE = "PARTIALLY_COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ContextComparison:
    """Comparison of one explicit context dimension."""

    dimension: str
    historical_value: Any
    current_value: Any
    relationship: ContextRelationship
    material: bool = True
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.dimension:
            raise ValueError("Context comparison dimension cannot be empty.")
        if not self.reason:
            object.__setattr__(
                self,
                "reason",
                f"Context dimension '{self.dimension}' is {self.relationship.value.lower()}.",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "historical_value": self.historical_value,
            "current_value": self.current_value,
            "relationship": self.relationship.value,
            "material": self.material,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CompatibilityAssessment:
    """Explicit compatibility result between a historical and current case."""

    status: CompatibilityStatus
    historical_finding_id: str
    current_case_id: str
    comparisons: List[ContextComparison] = field(default_factory=list)
    investigation_required: bool = False
    reason: str = ""
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "historical_finding_id": self.historical_finding_id,
            "current_case_id": self.current_case_id,
            "comparisons": [comparison.to_dict() for comparison in self.comparisons],
            "investigation_required": self.investigation_required,
            "reason": self.reason,
            "limitations": list(self.limitations),
        }


class ContextCompatibilityEvaluator:
    """Evaluate historical/current context using explicit, non-numeric rules."""

    def assess(
        self,
        historical_finding_id: str,
        current_case_id: str,
        comparisons: List[ContextComparison],
    ) -> CompatibilityAssessment:
        items = list(comparisons)
        if not historical_finding_id:
            raise ValueError("Historical finding id cannot be empty.")
        if not current_case_id:
            raise ValueError("Current case id cannot be empty.")
        if not items:
            return CompatibilityAssessment(
                status=CompatibilityStatus.UNKNOWN,
                historical_finding_id=historical_finding_id,
                current_case_id=current_case_id,
                comparisons=[],
                investigation_required=True,
                reason="No context comparisons are available.",
                limitations=["Context compatibility cannot be assessed without explicit comparisons."],
            )

        material_unknown = [
            item for item in items
            if item.material and item.relationship is ContextRelationship.UNKNOWN
        ]
        material_different = [
            item for item in items
            if item.material and item.relationship is ContextRelationship.DIFFERENT
        ]
        material_same = [
            item for item in items
            if item.material and item.relationship is ContextRelationship.SAME
        ]

        if material_unknown:
            return CompatibilityAssessment(
                status=CompatibilityStatus.UNKNOWN,
                historical_finding_id=historical_finding_id,
                current_case_id=current_case_id,
                comparisons=items,
                investigation_required=True,
                reason="One or more material context dimensions are unknown.",
                limitations=[
                    f"Material context is unknown: {', '.join(item.dimension for item in material_unknown)}."
                ],
            )

        if material_different and material_same:
            return CompatibilityAssessment(
                status=CompatibilityStatus.PARTIALLY_COMPATIBLE,
                historical_finding_id=historical_finding_id,
                current_case_id=current_case_id,
                comparisons=items,
                investigation_required=True,
                reason="Relevant context matches in some dimensions but differs in at least one material dimension.",
                limitations=[
                    f"Material context differs: {', '.join(item.dimension for item in material_different)}."
                ],
            )

        if material_different:
            return CompatibilityAssessment(
                status=CompatibilityStatus.INCOMPATIBLE,
                historical_finding_id=historical_finding_id,
                current_case_id=current_case_id,
                comparisons=items,
                investigation_required=False,
                reason="Material context differs and no matching material context was established.",
                limitations=[
                    f"Material context differs: {', '.join(item.dimension for item in material_different)}."
                ],
            )

        return CompatibilityAssessment(
            status=CompatibilityStatus.COMPATIBLE,
            historical_finding_id=historical_finding_id,
            current_case_id=current_case_id,
            comparisons=items,
            investigation_required=False,
            reason="All compared material context dimensions are compatible.",
        )
