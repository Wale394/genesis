"""Application-facing boundary for the Genesis reliability engine.

This module intentionally contains no reliability logic. It owns only session
state and converts Genesis' public result into interface-friendly views.
"""
from copy import deepcopy
from threading import RLock
import hashlib
import json

from genesis import Genesis
from demo_genesis_investigation import demo_telemetry_records
from genesis_system.adapters.ros2_telemetry_adapter import ROS2TelemetryAdapter


class GenesisController:
    """Own one live Genesis engine instance for an interface session."""

    def __init__(self):
        self._lock = RLock()
        self._engine = Genesis()
        self._latest = None
        self._event_log = []
        self._history = []
        self._decision_records = []

    def reset(self):
        with self._lock:
            self._engine = Genesis()
            self._latest = None
            self._event_log = []
            self._history = []
            self._decision_records = []
            return self.snapshot()

    def investigate(self, observation, *, adapter_provenance=None):
        with self._lock:
            result = self._engine.investigate(observation)
            if adapter_provenance is not None:
                result["adapter_provenance"] = deepcopy(adapter_provenance)
            # Preserve submitted telemetry at the interface boundary because the
            # current engine's processing.telemetry intentionally exposes only a
            # subset of the input fields. This capture is NOT engine-normalized
            # data and must never be presented as sensor-authenticated provenance.
            if isinstance(observation, dict):
                telemetry_fields = (
                    "motor_temperature", "ambient_temperature", "battery_level",
                    "battery_voltage", "battery_current", "battery_temperature",
                    "power_consumption", "voltage_drop", "workload", "time_step",
                    "robot_state", "state",
                )
                result["interface_capture"] = {
                    "source": "GenesisController.investigate input",
                    "status": "SUBMITTED_INPUT_NOT_ENGINE_NORMALIZED",
                    "telemetry": {key: deepcopy(observation[key]) for key in telemetry_fields if key in observation},
                }
            self._latest = result
            self._history.append(deepcopy(result))
            self._record_decision(observation, result)
            self._append_events(result)
            return deepcopy(result)

    def snapshot(self):
        with self._lock:
            return {
                "latest": deepcopy(self._latest),
                "events": deepcopy(self._event_log[-100:]),
                "history": deepcopy(self._history[-100:]),
                "decision_records": deepcopy(self._decision_records[-100:]),
            }

    def assets(self):
        """Summarize assets that have actually appeared in this session."""
        with self._lock:
            grouped = {}
            for result in self._history:
                robot = result.get("robot") or {}
                asset_id = robot.get("robot_id")
                if not asset_id:
                    continue
                item = grouped.setdefault(asset_id, {
                    "asset_id": asset_id,
                    "robot_type": robot.get("robot_type"),
                    "manufacturer": robot.get("manufacturer"),
                    "observations": 0,
                    "latest_state": None,
                    "latest_time_step": None,
                    "latest_result": None,
                })
                item["observations"] += 1
                item["latest_state"] = (result.get("reliability_state") or {}).get("current")
                item["latest_time_step"] = self._latest_time(result)
                item["latest_result"] = deepcopy(result)
            return list(grouped.values())

    def asset_detail(self, asset_id):
        """Return traceable session records for one asset ID."""
        with self._lock:
            matching = [deepcopy(r) for r in self._history
                        if (r.get("robot") or {}).get("robot_id") == asset_id]
            if not matching:
                return None
            incidents = [item for item in self.incidents()
                         if str(item.get("robot_id", "")) == str(asset_id)]
            return {
                "asset_id": asset_id,
                "observations": len(matching),
                "history": matching,
                "latest": matching[-1],
                "incidents": incidents,
                "source_scope": "current Genesis interface session",
            }

    def memory_entries(self):
        """Expose stored records from the live engine without inventing matches."""
        with self._lock:
            return deepcopy(self._engine._memory.entries)

    def incidents(self):
        """Expose actual incident-manager records from the live engine."""
        with self._lock:
            incidents = getattr(self._engine._history, "incidents", [])
            return [deepcopy(item.summary() if hasattr(item, "summary") else item) for item in incidents]

    @staticmethod
    def validate_observation(observation, require_identity=False):
        """Validate the interface input contract without interpreting sensor values.

        This checks payload shape and presence of at least one supported telemetry
        field. It deliberately does not infer units, authenticity, sensor health,
        physical condition, or causal meaning from submitted values.
        """
        if not isinstance(observation, dict):
            raise ValueError("observation must be an object")
        if require_identity and not observation.get("robot_id") and not observation.get("id"):
            raise ValueError("robot_id is required")
        telemetry_fields = (
            "motor_temperature", "ambient_temperature", "battery_level",
            "battery_voltage", "battery_current", "battery_temperature",
            "power_consumption", "voltage_drop", "workload", "robot_state", "state",
        )
        if not any(key in observation for key in telemetry_fields):
            raise ValueError("at least one telemetry field is required")
        return observation

    def investigate_ros2(self, payload):
        """Adapt a ROS 2 DiagnosticArray-like payload and submit it to Genesis.

        This endpoint accepts a JSON representation of a diagnostic message; it
        does not open a ROS connection or claim that the payload came from a live
        robot. Adapter metadata and limitations travel with the returned result.
        """
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        diagnostic_array = payload.get("diagnostic_array")
        if not isinstance(diagnostic_array, dict):
            raise ValueError("diagnostic_array must be an object")
        robot_id = payload.get("robot_id")
        if not isinstance(robot_id, str) or not robot_id.strip():
            raise ValueError("robot_id is required")
        field_units = payload.get("field_units") or {}
        key_mappings = payload.get("key_mappings") or {}
        if not isinstance(field_units, dict) or not isinstance(key_mappings, dict):
            raise ValueError("field_units and key_mappings must be objects")

        adapter = ROS2TelemetryAdapter(
            robot_id,
            manufacturer=payload.get("manufacturer"),
            robot_type=payload.get("robot_type"),
            field_units=field_units,
            key_mappings=key_mappings,
        )
        adapted = adapter.adapt(diagnostic_array, time_step=payload.get("time_step"))
        if not any(key != "time_step" for key in adapted["telemetry"]):
            details = "; ".join(adapted["limitations"]) or "no supported telemetry fields found"
            raise ValueError("ROS 2 payload contains no usable telemetry: " + details)

        observation = {
            "identity": deepcopy(adapted["identity"]),
            "telemetry": deepcopy(adapted["telemetry"]),
            "source": adapted["source"],
        }
        provenance = {
            "adapter": "ROS2TelemetryAdapter",
            "status": "ADAPTED_JSON_PAYLOAD_NOT_LIVE_ROS_CONNECTION",
            "source": adapted["source"],
            "source_metadata": deepcopy(adapted["source_metadata"]),
            "limitations": list(adapted["limitations"]),
            "adapted_observation": deepcopy(observation),
        }
        return self.investigate(observation, adapter_provenance=provenance)

    def submit_followup_observation(self, observation):
        """Submit a new observation; this does not itself validate a hypothesis."""
        self.validate_observation(observation, require_identity=True)
        return self.investigate(observation)

    def run_scenario(self, observations):
        """Process a supplied sequence through the real Genesis engine."""
        results = []
        for observation in observations:
            results.append(self.investigate(observation))
        return results

    def _record_decision(self, observation, result):
        """Record a replay-oriented audit envelope without claiming deterministic replay.

        Hashes cover the exact captured input and returned engine result. This is
        session-local provenance, not a signed or tamper-proof audit log.
        """
        sequence = len(self._decision_records) + 1
        captured_input = deepcopy(observation) if isinstance(observation, dict) else observation
        canonical_input = json.dumps(captured_input, sort_keys=True, separators=(",", ":"), default=str)
        canonical_result = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
        robot = result.get("robot") or {}
        state = result.get("reliability_state") or {}
        synthesis = result.get("evidence_synthesis") or {}
        recommendation = result.get("recommendation") or {}
        self._decision_records.append({
            "record_id": f"KDX-DEC-{sequence:05d}",
            "sequence": sequence,
            "robot_id": robot.get("robot_id"),
            "time_step": self._latest_time(result),
            "input_sha256": hashlib.sha256(canonical_input.encode("utf-8")).hexdigest(),
            "result_sha256": hashlib.sha256(canonical_result.encode("utf-8")).hexdigest(),
            "reliability_state": state.get("current"),
            "state_transition": deepcopy(state.get("transition")),
            "assessment": deepcopy(synthesis.get("assessment", synthesis.get("summary"))),
            "recommendation": deepcopy(recommendation.get("recommendation")),
            "evidence_lineage_id": (result.get("evidence_lineage") or {}).get("graph_id"),
            "engine_version": "not exposed by runtime",
            "rule_or_model_version": "not exposed by runtime",
            "record_scope": "current in-memory interface session; unsigned",
            "limitations": ["Hashes detect changes only if the record is retained and compared; this log is not tamper-proof.", "Replay is not guaranteed because runtime versioning and deterministic execution metadata are not exposed."],
        })

    def decision_records(self):
        with self._lock:
            return deepcopy(self._decision_records)

    def _append_events(self, result):
        robot = result.get("robot", {})
        state = result.get("reliability_state", {})
        transition = state.get("transition") or {}
        evidence = result.get("evidence_synthesis") or {}
        if transition.get("changed"):
            self._event_log.append({
                "type": "STATE_CHANGE",
                "robot_id": robot.get("robot_id"),
                "from": transition.get("from"),
                "to": transition.get("to"),
                "time_step": self._latest_time(result),
            })
        if evidence:
            self._event_log.append({
                "type": "EVIDENCE_UPDATE",
                "robot_id": robot.get("robot_id"),
                "state": state.get("current"),
                "time_step": self._latest_time(result),
                "quality": (result.get("observation_quality") or {}).get("status"),
            })
        recommendation = result.get("recommendation")
        if recommendation and recommendation.get("recommendation"):
            self._event_log.append({
                "type": "RECOMMENDATION",
                "robot_id": robot.get("robot_id"),
                "time_step": self._latest_time(result),
                "message": recommendation.get("recommendation"),
            })

    @staticmethod
    def _latest_time(result):
        telemetry = (result.get("processing") or {}).get("telemetry") or []
        if telemetry:
            return telemetry[-1].get("time_step")
        return None


# A deliberately conservative scenario: it demonstrates the real engine's
# transition/evidence behavior without pretending to be a physical failure.
def command_center_scenario():
    """Return the existing controlled R004 scenario used by Genesis itself.

    The telemetry is synthetic, but every observation is evaluated by the
    real public Genesis facade. The sequence deliberately crosses WATCH ->
    CRITICAL -> WATCH so the interface exposes an actual state transition.
    """
    return demo_telemetry_records()
