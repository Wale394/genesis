"""Conservative trust assessment for incoming Genesis observations.

This module does not authenticate devices or provide cryptographic integrity.
It records what Genesis can currently establish and explicitly marks unknown
security properties instead of assuming trust.
"""

from collections.abc import Mapping
from numbers import Real
import math


TRUSTED = "TRUSTED"
DEGRADED = "DEGRADED"
UNTRUSTED = "UNTRUSTED"
UNKNOWN = "UNKNOWN"


class ObservationSecurity:
    """Build a security/provenance assessment without changing inference."""

    def assess(
        self,
        feature_record,
        *,
        source_metadata=None,
        previous_time_step=None,
        source_time_step=None,
    ):
        metadata = dict(source_metadata or {}) if isinstance(source_metadata, Mapping) else {}
        robot_id = feature_record.get("robot_id")

        source_id = metadata.get("source_id") or metadata.get("source")
        source_type = metadata.get("source_type") or metadata.get("adapter")
        provenance_status = "AVAILABLE" if metadata else "MINIMAL"

        authentication = self._normalize_status(metadata.get("authentication"), UNKNOWN)
        integrity = self._normalize_status(metadata.get("integrity"), UNKNOWN)
        authorization = self._normalize_status(metadata.get("authorization"), UNKNOWN)

        freshness, freshness_reasons = self._freshness(
            previous_time_step=previous_time_step,
            source_time_step=source_time_step,
            metadata=metadata,
        )

        if authentication == UNTRUSTED or integrity == UNTRUSTED or authorization == UNTRUSTED or freshness == UNTRUSTED:
            overall = UNTRUSTED
        elif authentication == TRUSTED and integrity == TRUSTED and authorization == TRUSTED and freshness == TRUSTED:
            overall = TRUSTED
        else:
            overall = DEGRADED

        limitations = list(freshness_reasons)
        if authentication == UNKNOWN:
            limitations.append("Source authentication has not been established by the current runtime.")
        if integrity == UNKNOWN:
            limitations.append("Telemetry integrity has not been cryptographically verified by the current runtime.")
        if authorization == UNKNOWN:
            limitations.append("Source authorization has not been established by the current runtime.")
        if not metadata:
            limitations.append("No explicit source metadata was supplied with the observation.")

        return {
            "status": overall,
            "source": {
                "source_id": source_id,
                "source_type": source_type,
                "robot_id": robot_id,
                "provenance_status": provenance_status,
            },
            "authentication": authentication,
            "integrity": integrity,
            "authorization": authorization,
            "freshness": freshness,
            "limitations": limitations,
            "inference_impact": "DESCRIPTIVE_ONLY",
        }

    @staticmethod
    def _normalize_status(value, default):
        if value is None:
            return default
        normalized = str(value).strip().upper()
        aliases = {
            "VERIFIED": TRUSTED,
            "VALID": TRUSTED,
            "TRUE": TRUSTED,
            "OK": TRUSTED,
            "INVALID": UNTRUSTED,
            "FALSE": UNTRUSTED,
            "FAILED": UNTRUSTED,
        }
        return aliases.get(normalized, normalized if normalized in {TRUSTED, DEGRADED, UNTRUSTED, UNKNOWN} else default)

    @staticmethod
    def _freshness(*, previous_time_step, source_time_step, metadata):
        if source_time_step is None:
            if metadata.get("source_timestamp") is not None or metadata.get("timestamp") is not None:
                return DEGRADED, ["Source timestamp is present, but runtime ordering is not established from it yet."]
            return UNKNOWN, ["Observation freshness cannot be established without source timing information."]

        if isinstance(source_time_step, bool) or not isinstance(source_time_step, Real):
            return UNTRUSTED, ["Source time step is not numeric."]
        if not math.isfinite(float(source_time_step)):
            return UNTRUSTED, ["Source time step is not finite."]
        if previous_time_step is not None and source_time_step <= previous_time_step:
            return UNTRUSTED, ["Source observation is not newer than the previous observation."]
        return TRUSTED, []
