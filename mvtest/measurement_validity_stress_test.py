"""Stress-test contract for calibration and measurement validity.

This is intentionally an experiment, not a production calibration subsystem.
It tests whether Genesis can keep semantic correctness separate from the
current trustworthiness of a measurement and propagate that limitation only
to evidence that depends on the affected measurement.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable


class MeasurementValidity(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class MeasurementAssessment:
    signal: str
    validity: MeasurementValidity
    usable_as_measurement_evidence: bool
    reasons: tuple[str, ...]


def assess_measurement_validity(
    signal: str,
    *,
    semantic_verified: bool,
    calibration: Dict[str, Any] | None,
) -> MeasurementAssessment:
    reasons = []

    if not semantic_verified:
        reasons.append("semantic meaning is not verified")

    calibration = dict(calibration or {})
    status = calibration.get("status")

    if status is None:
        validity = MeasurementValidity.UNKNOWN
        reasons.append("calibration status is unknown")
    else:
        try:
            validity = MeasurementValidity(str(status).upper())
        except ValueError:
            validity = MeasurementValidity.UNKNOWN
            reasons.append("calibration status is invalid")

    if validity is MeasurementValidity.EXPIRED:
        reasons.append("calibration validity period has expired")
    elif validity is MeasurementValidity.FAILED:
        reasons.append("calibration or sensor verification has failed")
    elif validity is MeasurementValidity.UNKNOWN:
        if "calibration status is unknown" not in reasons:
            reasons.append("calibration validity cannot be established")

    usable = semantic_verified and validity in {
        MeasurementValidity.VALID,
        MeasurementValidity.NOT_APPLICABLE,
    }

    return MeasurementAssessment(
        signal=signal,
        validity=validity,
        usable_as_measurement_evidence=usable,
        reasons=tuple(reasons),
    )


def assess_evidence_dependencies(
    evidence_dependencies: Dict[str, Iterable[str]],
    measurement_assessments: Dict[str, MeasurementAssessment],
):
    """Propagate measurement validity only to dependent evidence."""
    result = {}
    for evidence_name, dependencies in evidence_dependencies.items():
        dependencies = tuple(dependencies)
        affected = [
            signal for signal in dependencies
            if not measurement_assessments[signal].usable_as_measurement_evidence
        ]
        result[evidence_name] = {
            "usable": not affected,
            "affected_by": affected,
        }
    return result
