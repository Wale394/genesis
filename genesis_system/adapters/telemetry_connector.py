"""Transport-independent contract for robot telemetry connectors.

Connectors acquire data from a transport (ROS 2, vendor SDK/API, MQTT, files,
recorded playback, etc.). They do not infer reliability or issue robot commands.
The packet-to-Genesis conversion only forwards fields currently supported by
Genesis and reports any fields it cannot yet analyze.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
import math
from numbers import Real
from typing import Any


GENESIS_TELEMETRY_FIELDS = frozenset({
    "motor_temperature", "ambient_temperature", "battery_level",
    "battery_voltage", "battery_current", "battery_temperature",
    "power_consumption", "voltage_drop", "workload", "robot_state",
})


class ConnectorStatus(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class SignalDescriptor:
    """Describes a signal a connector can expose; units are source-declared."""

    name: str
    data_type: str = "number"
    unit: str | None = None
    description: str = ""

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("signal name is required")
        if self.data_type not in {"number", "string", "boolean", "object"}:
            raise ValueError("data_type must be number, string, boolean, or object")
        if self.unit is not None and not isinstance(self.unit, str):
            raise ValueError("signal unit must be a string or None")

    def to_dict(self):
        return {
            "name": self.name,
            "data_type": self.data_type,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass(frozen=True)
class TelemetryPacket:
    """One observation delivered by any connector, before reliability analysis.

    ``signals`` contains source signal names. ``field_mappings`` at conversion
    time maps those names to Genesis' currently supported canonical fields.
    Adapters must normalize numeric units before constructing a packet; this
    contract records units and never guesses or converts them.
    """

    robot_id: str
    source: str
    timestamp: Any
    signals: Mapping[str, Any]
    manufacturer: str | None = None
    robot_type: str | None = None
    sequence_number: int | float | None = None
    units: Mapping[str, str] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    quality: str = "AVAILABLE"

    def __post_init__(self):
        if not isinstance(self.robot_id, str) or not self.robot_id.strip():
            raise ValueError("robot_id is required")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source is required")
        if not isinstance(self.signals, Mapping) or not self.signals:
            raise ValueError("signals must be a non-empty mapping")
        if any(not isinstance(key, str) or not key.strip() for key in self.signals):
            raise ValueError("signal names must be non-empty strings")
        if not isinstance(self.units, Mapping):
            raise ValueError("units must be a mapping")
        if not isinstance(self.provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        if isinstance(self.sequence_number, bool) or (
            self.sequence_number is not None and
            (not isinstance(self.sequence_number, Real) or not math.isfinite(float(self.sequence_number)))
        ):
            raise ValueError("sequence_number must be a finite number or None")
        if not isinstance(self.quality, str) or not self.quality.strip():
            raise ValueError("quality must be a non-empty string")
        if not isinstance(self.limitations, (list, tuple)) or any(not isinstance(x, str) for x in self.limitations):
            raise ValueError("limitations must be a sequence of strings")

    def to_genesis_record(self, *, field_mappings=None, connector_id=None):
        """Convert this packet into the existing Genesis ``identity/telemetry`` envelope.

        Unknown/unmapped signals are preserved in provenance and named in
        limitations; they are not passed to the current analysis engine as if
        they were understood. A source timestamp is used as ``time_step`` only
        when it is already a finite numeric value.
        """
        mappings = dict(field_mappings or {name: name for name in GENESIS_TELEMETRY_FIELDS})
        invalid_targets = set(mappings.values()) - GENESIS_TELEMETRY_FIELDS
        if invalid_targets:
            raise ValueError("unsupported Genesis target fields: " + ", ".join(sorted(invalid_targets)))

        telemetry = {}
        unmapped = []
        used_units = {}
        for source_name, value in self.signals.items():
            target = mappings.get(source_name)
            if target is None:
                unmapped.append(source_name)
                continue
            if target in telemetry and telemetry[target] != value:
                raise ValueError(f"conflicting source signals map to Genesis field {target!r}")
            telemetry[target] = value
            if source_name in self.units:
                used_units[target] = self.units[source_name]

        limitations = list(self.limitations)
        if unmapped:
            limitations.append("Signals not mapped to the current Genesis model: " + ", ".join(sorted(unmapped)) + ".")
        if not telemetry:
            raise ValueError("packet contains no signals supported by the current Genesis model")

        timestamp = self.timestamp
        if isinstance(timestamp, bool):
            timestamp_step = None
        elif isinstance(timestamp, Real) and math.isfinite(float(timestamp)):
            timestamp_step = float(timestamp)
        else:
            timestamp_step = None
            if timestamp is None:
                limitations.append("Source timestamp unavailable; Genesis may assign an ingestion-order time step.")
            else:
                limitations.append("Source timestamp preserved but not numeric; Genesis may assign an ingestion-order time step.")

        if timestamp_step is not None:
            telemetry["time_step"] = timestamp_step

        source_metadata = {
            "source": self.source,
            "connector_id": connector_id or self.source,
            "timestamp": timestamp,
            "sequence_number": self.sequence_number,
            "units": used_units,
            "quality": self.quality,
            "provenance": dict(self.provenance),
            "unmapped_signals": sorted(unmapped),
        }
        return {
            "identity": {
                "robot_id": self.robot_id,
                "manufacturer": self.manufacturer,
                "robot_type": self.robot_type,
            },
            "telemetry": telemetry,
            "source": self.source,
            "source_metadata": source_metadata,
            "limitations": limitations,
        }


class TelemetryConnector(ABC):
    """Common lifecycle and read contract for live or recorded telemetry sources.

    Implementations must be read-only with respect to the robot. ``read`` returns
    one packet, or ``None`` when no packet is available before its timeout.
    This interface intentionally does not include command or control methods.
    """

    @abstractmethod
    def connect(self) -> None:
        """Open the data source or raise an informative exception."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the data source and release its resources."""

    @abstractmethod
    def get_status(self) -> ConnectorStatus:
        """Return current connection state without claiming source authenticity."""

    @abstractmethod
    def discover_signals(self) -> tuple[SignalDescriptor, ...]:
        """Describe the signals exposed by this source."""

    @abstractmethod
    def read(self, timeout: float | None = None) -> TelemetryPacket | None:
        """Read one observation; return None when no observation is available."""


class RecordedTelemetryConnector(TelemetryConnector):
    """Deterministic in-memory connector for examples, tests, and playback."""

    def __init__(self, packets, *, signal_descriptors=None, connector_id="recorded-file"):
        self._packets = tuple(packets)
        if not self._packets or any(not isinstance(packet, TelemetryPacket) for packet in self._packets):
            raise ValueError("packets must contain at least one TelemetryPacket")
        self.connector_id = connector_id
        self._index = 0
        self._status = ConnectorStatus.DISCONNECTED
        if signal_descriptors is None:
            names = sorted({name for packet in self._packets for name in packet.signals})
            units = {name: unit for packet in self._packets for name, unit in packet.units.items()}
            signal_descriptors = [SignalDescriptor(name=name, unit=units.get(name)) for name in names]
        self._signals = tuple(signal_descriptors)
        if any(not isinstance(item, SignalDescriptor) for item in self._signals):
            raise ValueError("signal_descriptors must contain SignalDescriptor values")

    def connect(self):
        self._status = ConnectorStatus.CONNECTED

    def disconnect(self):
        self._status = ConnectorStatus.DISCONNECTED

    def get_status(self):
        return self._status

    def discover_signals(self):
        return self._signals

    def read(self, timeout=None):
        if self._status not in {ConnectorStatus.CONNECTED, ConnectorStatus.DEGRADED}:
            raise RuntimeError("connector is not connected")
        if self._index >= len(self._packets):
            return None
        packet = self._packets[self._index]
        self._index += 1
        return packet

def investigate_packet(packet, genesis, *, field_mappings=None, connector_id=None, sampling_context=None):
    """Convert one connector packet and pass it to the existing Genesis facade.

    Returns ``(genesis_record, investigation_result)`` so callers can retain
    the exact normalized input alongside the engine result. The helper does not
    create a Genesis instance or change its analysis behavior.
    """
    if not isinstance(packet, TelemetryPacket):
        raise TypeError("packet must be a TelemetryPacket")
    investigate = getattr(genesis, "investigate", None)
    if not callable(investigate):
        raise TypeError("genesis must provide an investigate(record, ...) method")
    record = packet.to_genesis_record(
        field_mappings=field_mappings,
        connector_id=connector_id,
    )
    result = investigate(record, sampling_context=sampling_context)
    return record, result

