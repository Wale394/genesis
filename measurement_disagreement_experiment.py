from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class Assessment(str, Enum):
    SUPPORTING = "SUPPORTING"
    MEASUREMENT_CONFLICT = "MEASUREMENT_CONFLICT"
    CONTEXTUAL_DIFFERENCE = "CONTEXTUAL_DIFFERENCE"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    INVALID_MEASUREMENT = "INVALID_MEASUREMENT"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


@dataclass(frozen=True)
class Measurement:
    sensor_id: str
    signal: str
    value: float
    timestamp: int
    location: str
    quality: str = "AVAILABLE"
    validity: str = "VALID"
    calibration: str = "VALID"
    freshness: str = "CURRENT"
    dependencies: tuple = field(default_factory=tuple)


def compare_measurements(a: Measurement, b: Measurement, tolerance: float = 3.0) -> dict:
    limitations: List[str] = []

    if a.signal != b.signal:
        return {"assessment": Assessment.INSUFFICIENT_CONTEXT.value, "reason": "different signals"}

    if a.location != b.location:
        return {
            "assessment": Assessment.CONTEXTUAL_DIFFERENCE.value,
            "reason": "measurements refer to different physical locations",
        }

    if a.freshness != "CURRENT" or b.freshness != "CURRENT":
        return {
            "assessment": Assessment.TEMPORAL_CONFLICT.value,
            "reason": "one or more measurements are not current",
        }

    if a.validity != "VALID" or b.validity != "VALID":
        return {
            "assessment": Assessment.INVALID_MEASUREMENT.value,
            "reason": "one or more measurements have invalid measurement validity",
        }

    if a.calibration != "VALID" or b.calibration != "VALID":
        return {
            "assessment": Assessment.INVALID_MEASUREMENT.value,
            "reason": "one or more measurements have unresolved calibration status",
        }

    if a.timestamp != b.timestamp:
        limitations.append("timestamps differ")

    delta = abs(a.value - b.value)
    if delta <= tolerance:
        return {
            "assessment": Assessment.SUPPORTING.value,
            "reason": "measurements agree within tolerance",
            "delta": delta,
            "limitations": limitations,
        }

    return {
        "assessment": Assessment.MEASUREMENT_CONFLICT.value,
        "reason": "current valid measurements disagree materially",
        "delta": delta,
        "limitations": limitations,
        "investigation_required": True,
        "investigation_target": "measurement_system_or_physical_asset",
    }
