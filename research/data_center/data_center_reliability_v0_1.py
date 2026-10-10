"""Research-only data-center reliability signals for Genesis.

This module does not control infrastructure, make shutdown decisions, or perform
cybersecurity analysis. It converts observations into evidence candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Dict, List, Optional


@dataclass
class DataCenterObservation:
    timestamp: Any
    rack_id: str
    inlet_temp_c: Optional[float] = None
    outlet_temp_c: Optional[float] = None
    power_kw: Optional[float] = None
    ups_load_pct: Optional[float] = None
    ups_battery_pct: Optional[float] = None
    humidity_pct: Optional[float] = None
    cooling_setpoint_c: Optional[float] = None


class DataCenterReliabilityResearch:
    """Deterministic, research-only evidence extraction."""

    def __init__(self) -> None:
        self.history: Dict[str, List[DataCenterObservation]] = {}

    def observe(self, observation: DataCenterObservation) -> List[Dict[str, Any]]:
        history = self.history.setdefault(observation.rack_id, [])
        previous = history[-1] if history else None
        evidence = self._signals(observation, previous)
        history.append(observation)
        return evidence

    def _signals(
        self,
        current: DataCenterObservation,
        previous: Optional[DataCenterObservation],
    ) -> List[Dict[str, Any]]:
        evidence: List[Dict[str, Any]] = []

        def add(signal: str, detail: str, fields: List[str]) -> None:
            evidence.append({
                "type": "ENGINEERING_SIGNAL",
                "domain": "data_center",
                "signal": signal,
                "detail": detail,
                "fields": fields,
            })

        if self._valid(current.inlet_temp_c) and current.inlet_temp_c >= 30:
            add(
                "elevated_rack_inlet_temperature",
                f"Rack inlet temperature is {current.inlet_temp_c:.1f} C.",
                ["inlet_temp_c"],
            )

        if (
            self._valid(current.outlet_temp_c)
            and self._valid(current.inlet_temp_c)
            and current.outlet_temp_c - current.inlet_temp_c >= 15
        ):
            add(
                "high_rack_thermal_delta",
                f"Outlet-inlet temperature delta is {current.outlet_temp_c - current.inlet_temp_c:.1f} C.",
                ["outlet_temp_c", "inlet_temp_c"],
            )

        if self._valid(current.ups_load_pct) and current.ups_load_pct >= 90:
            add(
                "high_ups_load",
                f"UPS load is {current.ups_load_pct:.1f}%.",
                ["ups_load_pct"],
            )

        if self._valid(current.ups_battery_pct) and current.ups_battery_pct <= 30:
            add(
                "low_ups_battery",
                f"UPS battery is {current.ups_battery_pct:.1f}%.",
                ["ups_battery_pct"],
            )

        if (
            previous
            and self._valid(current.power_kw)
            and self._valid(previous.power_kw)
            and previous.power_kw > 0
        ):
            change_pct = ((current.power_kw - previous.power_kw) / previous.power_kw) * 100
            if abs(change_pct) >= 15:
                add(
                    "rapid_power_change",
                    f"Power changed by {change_pct:+.1f}% from the previous observation.",
                    ["power_kw"],
                )

        if self._valid(current.humidity_pct) and not 20 <= current.humidity_pct <= 80:
            add(
                "environmental_humidity_out_of_range",
                f"Humidity is {current.humidity_pct:.1f}%.",
                ["humidity_pct"],
            )

        return evidence

    @staticmethod
    def _valid(value: Optional[float]) -> bool:
        return value is not None and isfinite(value)
