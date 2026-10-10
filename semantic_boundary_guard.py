"""Stress-test contract for semantic provenance at domain-adapter boundaries."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable


class SemanticStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


@dataclass(frozen=True)
class SignalSemanticAssessment:
    signal: str
    status: SemanticStatus
    usable_as_physical_evidence: bool
    reasons: tuple[str, ...]


def assess_signal_semantics(signal: str, provenance: Dict[str, Any] | None) -> SignalSemanticAssessment:
    p = dict(provenance or {})
    source_field = p.get("source_field")
    physical_quantity = p.get("physical_quantity")
    unit = p.get("unit")
    transform = p.get("transform")
    canonical_field = p.get("canonical_field")

    expected_quantities = {
        "motor_temperature": "temperature",
        "ambient_temperature": "temperature",
        "battery_temperature": "temperature",
        "battery_voltage": "voltage",
        "battery_current": "current",
        "battery_level": "percentage",
        "power_consumption": "power",
        "voltage_drop": "voltage",
        "workload": "percentage",
        "robot_state": "state",
    }

    reasons = []
    if canonical_field != signal:
        reasons.append("canonical field mapping is missing or conflicting")
    if not source_field:
        reasons.append("source field is unknown")
    if not physical_quantity:
        reasons.append("physical quantity is unknown")
    elif expected_quantities.get(signal) and physical_quantity != expected_quantities[signal]:
        reasons.append("physical quantity conflicts with canonical signal")
    if not unit and physical_quantity not in {"state", "count", "boolean"}:
        reasons.append("unit is unknown")
    if transform is None:
        reasons.append("normalization transform is unspecified")

    if reasons:
        status = SemanticStatus.UNKNOWN if len(reasons) >= 3 else SemanticStatus.PARTIAL
        return SignalSemanticAssessment(signal, status, False, tuple(reasons))

    return SignalSemanticAssessment(signal, SemanticStatus.VERIFIED, True, ())


def assess_observation_semantics(signals: Iterable[str], provenance: Dict[str, Any] | None):
    per_signal = provenance.get("signals", {}) if provenance else {}
    return {
        signal: assess_signal_semantics(signal, per_signal.get(signal))
        for signal in signals
    }
