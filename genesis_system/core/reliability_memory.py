"""In-memory, deterministic store for structured incident knowledge."""

from copy import deepcopy
import math
from numbers import Real


_FORBIDDEN_KEYS = frozenset({
    "battery_health", "battery_stress", "degradation_level", "health",
    "initial_health", "failure_event", "failure_type", "recovery_event",
    "failure_type_label", "label",
})


def _clean(value):
    """Return JSON-safe data while excluding simulator-only truth fields."""
    if isinstance(value, dict):
        return {
            str(key): _clean(item)
            for key, item in value.items()
            if str(key) not in _FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, Real) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return value.item() if hasattr(value, "item") else value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _incident_dict(incident):
    if hasattr(incident, "summary"):
        return incident.summary()
    return incident or {}


class ReliabilityMemory:
    """Store compact incident summaries; it does not make reliability decisions."""

    def __init__(self, entries=None):
        self._entries = {}
        for entry in entries or []:
            self.load_entry(entry)

    @property
    def entries(self):
        return [deepcopy(entry) for entry in self._entries.values()]

    def store_incident(self, incident, explanation=None):
        incident_data = _incident_dict(incident)
        if explanation is None and isinstance(incident_data.get("identity"), dict):
            explanation = incident_data
        explanation = explanation or {}
        identity = explanation.get("identity") or {}
        reliability_state = explanation.get("reliability_state") or {}
        engineering = explanation.get("engineering_signals") or {}
        inference = explanation.get("ml_inference") or {}
        diagnosis = inference.get("diagnosis")
        recommendation = explanation.get("recommendation") or {}
        action = explanation.get("human_action") or {}
        outcome = explanation.get("outcome") or {}

        incident_id = identity.get("incident_id") or incident_data.get("incident_id")
        if not incident_id:
            raise ValueError("incident_id is required to store reliability memory")

        identity_record = {
            key: identity.get(key, incident_data.get(key))
            for key in ("incident_id", "robot_id", "site_id", "incident_type")
        }
        identity_record["manufacturer"] = identity.get(
            "manufacturer", explanation.get("manufacturer", incident_data.get("manufacturer"))
        )
        identity_record["robot_type"] = identity.get(
            "robot_type", explanation.get("robot_type", incident_data.get("robot_type"))
        )

        status = identity.get("status", incident_data.get("status", "UNAVAILABLE"))
        current_state = reliability_state.get("current")
        lifecycle = {
            "start_time": identity.get("start_time_step", incident_data.get("start_time_step")),
            "end_time": identity.get("end_time_step", incident_data.get("end_time_step")),
            "status": status,
            "previous_state": reliability_state.get("previous"),
            "current_state": current_state,
            "final_state": current_state if status == "CLOSED" else None,
        }

        signals = [
            item.get("signal")
            for item in engineering.get("items", [])
            if item.get("signal")
        ]
        prediction = {
            "available": inference.get("prediction_available", False),
            "probability": inference.get("probability"),
            "predicted_risk": inference.get("predicted_risk"),
            "model_prediction": inference.get("model_prediction"),
        }
        diagnosis_record = deepcopy(diagnosis) if diagnosis else {
            "status": "UNAVAILABLE",
            "possible_failure_type": None,
            "probable_cause": None,
            "confidence": None,
            "confirmed": False,
        }
        recommendation_record = {
            "status": recommendation.get("status", "UNAVAILABLE"),
            "text": recommendation.get("text"),
            "reason": recommendation.get("reason"),
            "severity": recommendation.get("severity"),
            "priority": recommendation.get("priority"),
        }
        action_items = action.get("items") or []
        outcome_record = {
            "status": "pending" if outcome.get("status") == "OUTCOME_PENDING" else outcome.get("status", "UNAVAILABLE"),
            "resolved": outcome.get("resolved", False),
            "details": outcome.get("details"),
            "recovery_events": outcome.get("recovery_events", []),
        }
        observations = [
            item for item in explanation.get("observations", [])
            if item.get("field") not in _FORBIDDEN_KEYS
        ]
        temporal_evidence = [
            item for item in explanation.get("temporal_evidence", [])
            if item.get("field") not in _FORBIDDEN_KEYS
        ]
        entry = {
            "schema_version": 1,
            "entry_type": "incident",
            "identity": identity_record,
            "lifecycle": lifecycle,
            "characterization": {
                "engineering_signals": signals,
                "diagnosis": diagnosis_record,
                "ml_inference": prediction,
                "recommendation": recommendation_record,
                "human_action": {
                    "status": action.get("status", "PENDING"),
                    "items": action_items,
                },
                "outcome": outcome_record,
            },
            "evidence": {
                "observations": observations,
                "temporal_evidence": temporal_evidence,
                "observation_quality": explanation.get("observation_quality", {"overall": "UNAVAILABLE"}),
                "historical_comparison": explanation.get("historical_evidence", {"status": "UNAVAILABLE"}),
                "limitations": explanation.get("limitations", []),
            },
        }
        safe_entry = _clean(entry)
        self._entries[str(incident_id)] = safe_entry
        return deepcopy(safe_entry)

    def update_incident(self, incident, explanation=None):
        return self.store_incident(incident, explanation)

    def store_investigation(self, outcome):
        """Store an investigation outcome, preserving finding status explicitly."""
        data = _clean(deepcopy(_investigation_outcome_dict(outcome)))
        investigation_id = data.get("investigation_id")
        if not investigation_id:
            raise ValueError("investigation_id is required to store investigation memory")

        record = {
            "schema_version": 1,
            "entry_type": "investigation",
            "investigation": data,
        }
        key = f"investigation:{investigation_id}"
        self._entries[key] = record
        return deepcopy(record)

    def investigations(self):
        """Return stored investigation outcomes without changing their status."""
        return [
            deepcopy(entry)
            for key, entry in self._entries.items()
            if key.startswith("investigation:")
        ]

    def validated_findings(self):
        """Return only findings explicitly marked VALIDATED by an investigation."""
        findings = []
        for entry in self.investigations():
            for finding in entry.get("investigation", {}).get("findings", []):
                if finding.get("status") == "VALIDATED":
                    findings.append(deepcopy(finding))
        return findings

    def load_entry(self, entry):
        """Load one serialized memory entry while preserving its entry type."""
        safe_entry = _clean(deepcopy(entry))
        entry_type = safe_entry.get("entry_type")

        # Investigation entries have a different schema from incident entries.
        # They must round-trip through the same memory container without being
        # forced through incident identity validation.
        if entry_type == "investigation" or "investigation" in safe_entry:
            investigation = safe_entry.get("investigation") or {}
            investigation_id = investigation.get("investigation_id")
            if not investigation_id:
                raise ValueError("investigation memory entry is missing investigation.investigation_id")
            key = f"investigation:{investigation_id}"
            self._entries[key] = safe_entry
            return deepcopy(safe_entry)

        # Backward compatibility for older incident entries that predate the
        # explicit entry_type discriminator.
        incident_id = safe_entry.get("identity", {}).get("incident_id")
        if not incident_id:
            raise ValueError("memory entry is missing identity.incident_id")
        self._entries[str(incident_id)] = safe_entry
        return deepcopy(safe_entry)

    def get_by_id(self, incident_id):
        entry = self._entries.get(str(incident_id))
        return deepcopy(entry) if entry is not None else None

    def get_by_incident_id(self, incident_id):
        return self.get_by_id(incident_id)

    def _filter(self, path, value):
        return [
            deepcopy(entry) for entry in self._entries.values()
            if _path_value(entry, path) == value
        ]

    def by_robot_id(self, robot_id):
        return self._filter(("identity", "robot_id"), robot_id)

    def get_by_robot_id(self, robot_id):
        return self.by_robot_id(robot_id)

    def by_manufacturer(self, manufacturer):
        return self._filter(("identity", "manufacturer"), manufacturer)

    def by_robot_type(self, robot_type):
        return self._filter(("identity", "robot_type"), robot_type)

    def by_status(self, status):
        return self._filter(("lifecycle", "status"), status)

    def get_by_status(self, status):
        return self.by_status(status)

    def by_engineering_signal(self, signal):
        return [
            deepcopy(entry) for entry in self._entries.values()
            if signal in entry["characterization"].get("engineering_signals", [])
        ]

    def get_by_engineering_signal(self, signal):
        return self.by_engineering_signal(signal)

    def by_diagnosis(self, diagnosis):
        return [
            deepcopy(entry) for entry in self._entries.values()
            if entry["characterization"].get("diagnosis", {}).get("possible_failure_type") == diagnosis
        ]

    def get_by_diagnosis(self, diagnosis):
        return self.by_diagnosis(diagnosis)

    def find_similar(self, current_incident, exclude_incident_id=None):
        current = _clean(current_incident or {})
        identity = current.get("identity") or {}
        characterization = current.get("characterization") or {}
        current_engineering = current.get("engineering_signals") or {}
        signal_items = current_engineering.get("items", current_engineering.get("signals", []))
        signals = {
            item.get("signal") for item in signal_items
            if isinstance(item, dict) and item.get("signal")
        }
        if not signals:
            signals = set(characterization.get("engineering_signals", []))
        diagnosis = (current.get("ml_inference") or {}).get("diagnosis")
        if diagnosis is None:
            diagnosis = characterization.get("diagnosis") or {}
        diagnosis_type = diagnosis.get("possible_failure_type")
        if diagnosis_type in (None, ""):
            diagnosis_type = None
        current_state = (current.get("reliability_state") or {}).get("current")
        current_state = current_state or (current.get("lifecycle") or {}).get("final_state")
        incident_type = identity.get("incident_type")

        matches = []
        for entry in self._entries.values():
            entry_id = entry["identity"]["incident_id"]
            if exclude_incident_id is not None and str(entry_id) == str(exclude_incident_id):
                continue
            reasons = []
            prior_identity = entry["identity"]
            prior_characterization = entry["characterization"]
            if identity.get("robot_id") and identity.get("robot_id") == prior_identity.get("robot_id"):
                reasons.append("same_robot")
            if identity.get("manufacturer") and identity.get("manufacturer") == prior_identity.get("manufacturer"):
                reasons.append("same_manufacturer")
            if identity.get("robot_type") and identity.get("robot_type") == prior_identity.get("robot_type"):
                reasons.append("same_robot_type")
            common_signals = signals.intersection(prior_characterization.get("engineering_signals", []))
            if common_signals:
                reasons.append("same_engineering_signal")
            prior_diagnosis = prior_characterization.get("diagnosis") or {}
            if diagnosis_type and diagnosis_type == prior_diagnosis.get("possible_failure_type"):
                reasons.append("same_diagnosis")
            prior_state = entry["lifecycle"].get("final_state") or entry["lifecycle"].get("current_state")
            if current_state and current_state == prior_state:
                reasons.append("same_reliability_state")
            if incident_type and incident_type == prior_identity.get("incident_type"):
                reasons.append("same_incident_category")
            if reasons:
                matches.append({"incident_id": entry_id, "similarity_reasons": reasons})
        return matches

    def historical_context(self, current_incident, exclude_incident_id=None):
        matches = self.find_similar(current_incident, exclude_incident_id)
        incidents = []
        for match in matches:
            entry = self.get_by_id(match["incident_id"])
            characterization = entry["characterization"]
            incidents.append({
                "incident_id": match["incident_id"],
                "similarity_reasons": match["similarity_reasons"],
                "status": entry["lifecycle"]["status"],
                "engineering_signals": characterization["engineering_signals"],
                "diagnosis": characterization["diagnosis"],
                "recommendation": characterization["recommendation"],
                "human_action": characterization["human_action"],
                "outcome": characterization["outcome"],
            })
        return {
            "status": "AVAILABLE" if incidents else "UNAVAILABLE",
            "match_count": len(incidents),
            "incidents": incidents,
            "message": None if incidents else "historical memory unavailable",
        }


def _path_value(record, path):
    value = record
    for key in path:
        value = value.get(key, {}) if isinstance(value, dict) else {}
    return value

# Investigation knowledge is intentionally stored separately from incident
# characterization so a hypothesis is never silently promoted to truth.
def _investigation_outcome_dict(outcome):
    if hasattr(outcome, "to_dict"):
        return outcome.to_dict()
    return outcome or {}
