"""Genesis Context Shift Stress Test v0.1.

Experimental layer only. It tests whether a signal deviation should be treated
as behavioral evidence when operating context is stable, changed, or unknown.
No reliability-state mutation is performed here.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ContextStatus(str, Enum):
    STABLE = "STABLE"
    CHANGED = "CHANGED"
    UNKNOWN = "UNKNOWN"


class Interpretation(str, Enum):
    NORMAL = "NORMAL"
    CONTEXTUAL_DEVIATION = "CONTEXTUAL_DEVIATION"
    BEHAVIORAL_DEVIATION = "BEHAVIORAL_DEVIATION"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


@dataclass(frozen=True)
class ContextDimension:
    name: str
    baseline: Any
    observed: Any
    material: bool = True

    @property
    def status(self) -> ContextStatus:
        if self.baseline is None or self.observed is None:
            return ContextStatus.UNKNOWN
        return ContextStatus.STABLE if self.baseline == self.observed else ContextStatus.CHANGED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "baseline": self.baseline,
            "observed": self.observed,
            "material": self.material,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class ContextShiftAssessment:
    signal: str
    observed_value: Any
    expected_value: Any
    deviation_detected: bool
    context_status: ContextStatus
    interpretation: Interpretation
    investigation_required: bool
    context_dimensions: List[ContextDimension] = field(default_factory=list)
    reason: str = ""
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "deviation_detected": self.deviation_detected,
            "context_status": self.context_status.value,
            "interpretation": self.interpretation.value,
            "investigation_required": self.investigation_required,
            "context_dimensions": [item.to_dict() for item in self.context_dimensions],
            "reason": self.reason,
            "limitations": list(self.limitations),
        }


class ContextShiftEvaluator:
    """Evaluate whether a signal deviation can be interpreted in context."""

    def assess(
        self,
        signal: str,
        observed_value: Any,
        expected_value: Any,
        context_dimensions: List[ContextDimension],
    ) -> ContextShiftAssessment:
        if not signal:
            raise ValueError("Signal cannot be empty.")

        dimensions = list(context_dimensions)
        deviation = observed_value != expected_value
        material = [item for item in dimensions if item.material]
        unknown = [item for item in material if item.status is ContextStatus.UNKNOWN]
        changed = [item for item in material if item.status is ContextStatus.CHANGED]

        if not deviation:
            return ContextShiftAssessment(
                signal=signal,
                observed_value=observed_value,
                expected_value=expected_value,
                deviation_detected=False,
                context_status=ContextStatus.STABLE if not unknown else ContextStatus.UNKNOWN,
                interpretation=Interpretation.NORMAL,
                investigation_required=False,
                context_dimensions=dimensions,
                reason="Observed signal is within the supplied expectation.",
            )

        if unknown:
            return ContextShiftAssessment(
                signal=signal,
                observed_value=observed_value,
                expected_value=expected_value,
                deviation_detected=True,
                context_status=ContextStatus.UNKNOWN,
                interpretation=Interpretation.INSUFFICIENT_CONTEXT,
                investigation_required=True,
                context_dimensions=dimensions,
                reason="A signal deviation was observed, but material operating context is unknown.",
                limitations=[
                    "The deviation must not be interpreted as abnormal behavior until the material context is resolved."
                ],
            )

        if changed:
            return ContextShiftAssessment(
                signal=signal,
                observed_value=observed_value,
                expected_value=expected_value,
                deviation_detected=True,
                context_status=ContextStatus.CHANGED,
                interpretation=Interpretation.CONTEXTUAL_DEVIATION,
                investigation_required=False,
                context_dimensions=dimensions,
                reason="The signal changed while one or more material operating-context dimensions also changed.",
                limitations=[
                    "Context change explains why the deviation cannot be treated as independent behavioral evidence by this experiment alone."
                ],
            )

        return ContextShiftAssessment(
            signal=signal,
            observed_value=observed_value,
            expected_value=expected_value,
            deviation_detected=True,
            context_status=ContextStatus.STABLE,
            interpretation=Interpretation.BEHAVIORAL_DEVIATION,
            investigation_required=False,
            context_dimensions=dimensions,
            reason="The signal deviated while all supplied material operating-context dimensions remained stable.",
        )
