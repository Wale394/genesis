"""JSON-serializable configuration for the read-only Genesis Field Agent."""

from dataclasses import asdict, dataclass, field
import json
from typing import Optional
from telemetry_sampling_context import validate_sampling_context


@dataclass
class GenesisFieldAgentConfig:
    session_id: str
    robot_id: str
    manufacturer: Optional[str] = None
    robot_type: Optional[str] = None
    telemetry_mapping: dict = field(default_factory=dict)
    field_units: dict = field(default_factory=dict)
    output_path: Optional[str] = None
    genesis_analysis_enabled: bool = False
    sampling_context: Optional[dict] = None

    def __post_init__(self):
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(self.robot_id, str) or not self.robot_id.strip():
            raise ValueError("robot_id must be a non-empty string")
        for name in ("telemetry_mapping", "field_units"):
            value = getattr(self, name)
            if not isinstance(value, dict):
                raise ValueError(f"{name} must be an object")
        if not isinstance(self.genesis_analysis_enabled, bool):
            raise ValueError("genesis_analysis_enabled must be a boolean")
        self.sampling_context = validate_sampling_context(self.sampling_context)
        # Fail at configuration time if a caller supplies non-JSON data.
        try:
            json.dumps(self.to_dict(), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"configuration must be JSON serializable: {exc}") from exc

    def to_dict(self):
        """Return a JSON-serializable configuration mapping."""
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("configuration must be an object")
        allowed = {
            "session_id", "robot_id", "manufacturer", "robot_type",
            "telemetry_mapping", "field_units", "output_path",
            "genesis_analysis_enabled", "sampling_context",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError("unsupported configuration field(s): " + ", ".join(sorted(unknown)))
        return cls(**value)

