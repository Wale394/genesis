"""Compatibility import for the connector-independent telemetry contract."""
from genesis_system.adapters.telemetry_connector import (
    ConnectorStatus,
    GENESIS_TELEMETRY_FIELDS,
    RecordedTelemetryConnector,
    SignalDescriptor,
    TelemetryConnector,
    TelemetryPacket,
    investigate_packet,
)

__all__ = [
    "ConnectorStatus",
    "GENESIS_TELEMETRY_FIELDS",
    "RecordedTelemetryConnector",
    "SignalDescriptor",
    "TelemetryConnector",
    "TelemetryPacket",
    "investigate_packet",
]
