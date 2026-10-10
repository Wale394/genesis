from incident_manager import IncidentManager
from comparison_engine import ComparisonEngine
from baseline_engine import BaselineEngine
from observation_quality import ObservationQuality
from reliability_fusion import ReliabilityFusion
from incident_explanation import IncidentExplanation
from reliability_memory import ReliabilityMemory
from fleet_baseline import FleetBaseline
from evidence_synthesis import EvidenceSynthesis
from telemetry_pattern_engine import TelemetryPatternEngine

class DecisionPipeline:

    def __init__(
        self,
        prediction_engine,
        diagnosis_engine,
        recommendation_engine,
        reliability_state,
        incident_manager,
        evidence_engine,
        comparison_engine,
        baseline_engine,
        fusion_engine=None,
        reliability_memory=None,
        fleet_baseline=None,
    ):
        self.prediction_engine = prediction_engine
        self.diagnosis_engine = diagnosis_engine
        self.recommendation_engine = recommendation_engine
        self.reliability_state = reliability_state
        self.incident_manager = incident_manager
        self.evidence_engine = evidence_engine
        self.comparison_engine = comparison_engine
        self.baseline_engine = baseline_engine
        self.observation_quality = ObservationQuality()
        self.reliability_fusion = fusion_engine or ReliabilityFusion()
        self.reliability_memory = reliability_memory or ReliabilityMemory()
        self.fleet_baseline = fleet_baseline or FleetBaseline()
        self.evidence_synthesis = EvidenceSynthesis()
        self.telemetry_pattern_engine = TelemetryPatternEngine()

    def evaluate(
        self,
        feature_record,
        previous_state=None,
        historical_records=None,
        fleet_records=None,
        previous_fleet_records=None,
        sampling_analysis=None,
        observation_security=None,
    ):

        if historical_records is None:
            historical_records = []

        robot_id = feature_record.get("robot_id")
        time_step = feature_record.get("time_step")

        # --------------------------------
        # 1. OBSERVATION
        # --------------------------------

        actual_failure = feature_record.get(
            "failure_event",
            False
        )

        recovery_event = feature_record.get(
            "recovery_event",
            False
        )

        # Descriptive telemetry patterns are computed from this robot's own
        # chronological observations and remain separate from inference and
        # state-transition inputs.
        pattern_history = [
            record for record in historical_records
            if record.get("robot_id") in (None, robot_id)
        ]
        telemetry_patterns = self.telemetry_pattern_engine.analyze(
            pattern_history + [feature_record]
        )

        # --------------------------------
        # 2. PREDICTION
        # --------------------------------

        observation_quality = self.observation_quality.assess(
            feature_record, historical_records
        )
        fleet_context = self.fleet_baseline.compare(
            feature_record,
            peer_records=fleet_records,
            observation_quality=observation_quality,
            previous_peer_records=previous_fleet_records,
        )
        model_result = None
        unavailable_reason = None
        if self.prediction_engine is None:
            unavailable_reason = "No fitted model artifact available for this demonstration."
        elif observation_quality["prediction_ready"]:
            model_result = self.prediction_engine.predict(feature_record)
            ml_probability = model_result["probability"]
            ml_prediction = model_result["prediction"]
        else:
            ml_probability = None
            ml_prediction = None
            unavailable_reason = "required telemetry or temporal history is unavailable"
        if model_result is None:
            ml_probability = None
            ml_prediction = None

        fusion_result = self.reliability_fusion.evaluate(
            feature_record=feature_record,
            ml_probability=ml_probability,
            ml_prediction=ml_prediction,
            observation_quality=observation_quality,
            historical_records=historical_records,
        )
        risk_result = {
            "probability": ml_probability,
            "prediction": fusion_result["final"]["prediction"],
            "model_prediction": ml_prediction,
            "prediction_available": model_result is not None,
            "unavailable_reason": unavailable_reason,
            "engineering": fusion_result["engineering"],
            "fused_risk": fusion_result["final"]["risk"],
            "confidence_limited": fusion_result["final"]["confidence_limited"],
            "fusion": fusion_result,
            "observation_quality": observation_quality,
        }

        evidence_result = self.evidence_engine.build_evidence_summary(
            feature_record,
            risk_result=risk_result,
            observation_quality=observation_quality,
        )

        comparison_result = self.comparison_engine.compare_to_history(
            feature_record,
            historical_records
        )

        baseline_result = self.baseline_engine.build_baseline(
            historical_records
        )
        baseline_visibility = self._baseline_visibility(
            historical_records, baseline_result
        )

        # --------------------------------
        # 3. INITIAL RELIABILITY STATE
        # --------------------------------

        state = self.reliability_state.transition_from_fusion(
            fusion_result,
            previous_state=previous_state,
            observation_quality=observation_quality,
            actual_failure=actual_failure,
            recovery_event=recovery_event,
        )

        diagnosis_result = None
        recommendation_result = None
        incident = None

        # --------------------------------
        # 4. INTELLIGENCE
        # --------------------------------

        if (
            risk_result["prediction"] == 1
            and observation_quality["prediction_ready"]
            and self.diagnosis_engine is not None
        ):
            diagnosis_result = self.diagnosis_engine.diagnose(feature_record)

        # RecommendationEngine is the single owner of the operational action.
        recommendation_result = self.recommendation_engine.recommend(
            risk_result,
            diagnosis_result,
            state,
            observation_quality=observation_quality,
        )

        engineering_signals = fusion_result["engineering"].get("signals", [])
        active_incident = self.incident_manager.get_active_incident(robot_id)
        abnormal_states = {
            self.reliability_state.WATCH,
            self.reliability_state.WARNING,
            self.reliability_state.CRITICAL,
            self.reliability_state.FAILED,
            self.reliability_state.RECOVERING,
        }
        should_track = (
            actual_failure
            or active_incident is not None
            or bool(engineering_signals)
            or (
                state in abnormal_states
                and observation_quality["prediction_ready"]
                and risk_result["prediction_available"]
            )
        )
        incident = None
        if should_track:
            incident = self.incident_manager.update_incident(
                robot_id=robot_id,
                time_step=time_step,
                observation={
                    key: feature_record.get(key)
                    for key in (
                        "motor_temperature", "thermal_rise", "battery_level",
                        "workload", "robot_state",
                    )
                },
                evidence={
                    "time_step": time_step,
                    "type": "fused_reliability_decision",
                    "engineering": fusion_result["engineering"],
                    "observation_quality": observation_quality,
                },
                prediction={
                    "time_step": time_step,
                    "probability": risk_result["probability"],
                    "model_prediction": risk_result["model_prediction"],
                    "operational_prediction": risk_result["prediction"],
                    "fused_risk": risk_result["fused_risk"],
                },
                diagnosis=(
                    diagnosis_result.get("probable_cause")
                    if diagnosis_result is not None else None
                ),
                confidence=(
                    diagnosis_result.get("confidence")
                    if diagnosis_result is not None else None
                ),
                recommendation=recommendation_result.get("recommendation"),
            )
            if (
                diagnosis_result is not None
                and incident.incident_type is None
            ):
                incident.incident_type = diagnosis_result.get("failure_type")

        if actual_failure:
            incident = self.incident_manager.mark_failed(
                robot_id=robot_id,
                time_step=time_step,
                outcome={
                    "failure_type": feature_record.get("failure_type"),
                    "robot_state": feature_record.get("robot_state"),
                },
            )
        elif state == self.reliability_state.RECOVERING:
            incident = self.incident_manager.mark_recovering(
                robot_id=robot_id,
                time_step=time_step,
            ) or incident

        resolving_incident = bool(
            state == self.reliability_state.HEALTHY
            and previous_state == self.reliability_state.RECOVERING
            and incident is not None
        )
        resolution_outcome = None
        if resolving_incident:
            resolution_outcome = {
                "resolved": True,
                "final_state": state,
                "resolution_time_step": time_step,
                "recommendation": recommendation_result.get("recommendation"),
            }

        # --------------------------------
        # 10. EVIDENCE TIMELINE
        # --------------------------------

        timeline = self.build_evidence_timeline(
            historical_records,
            feature_record,
            risk_result,
            evidence_result,
            diagnosis_result,
            recommendation_result,
            state,
            observation_quality,
            fusion_result=fusion_result,
            state_changed=(state != previous_state),
        )

        if resolving_incident:
            timeline.add_outcome(time_step, resolution_outcome)

        if incident is not None:

            for event in timeline.get_events():
                incident.add_timeline_event(event)

        if resolving_incident:
            incident = self.incident_manager.close_incident(
                robot_id=robot_id,
                end_time_step=time_step,
                outcome=resolution_outcome,
            ) or incident

        result = {
            "robot_id": robot_id,
            "time_step": time_step,
            "risk": risk_result,
            "observation_quality": observation_quality,
            "state": state,
            "previous_state": previous_state,
            "state_transition": {
                "from": previous_state,
                "to": state,
                "changed": state != previous_state,
            },
            "diagnosis": diagnosis_result,
            "recommendation": recommendation_result,
            "incident":
                incident.summary()
                if incident is not None
                else None,
            "evidence": evidence_result,
            "timeline": timeline.build_timeline(),
            "comparison": comparison_result,
            "baseline": baseline_result,
            "baseline_visibility": baseline_visibility,
            "fleet_context": fleet_context,
            "actual_failure": actual_failure,
            "recovery_event": recovery_event,
            "observation_security": observation_security or {},
        }
        incident_data = incident.summary() if incident is not None else {}
        diagnosis_for_memory = None
        if diagnosis_result is not None:
            diagnosis_for_memory = {
                "possible_failure_type": diagnosis_result.get("failure_type"),
                "probable_cause": diagnosis_result.get("probable_cause"),
                "confidence": diagnosis_result.get("confidence"),
                "confirmed": False,
            }
        memory_query = {
            "identity": {
                "incident_id": incident_data.get("incident_id"),
                "robot_id": robot_id,
                "manufacturer": feature_record.get("manufacturer"),
                "robot_type": feature_record.get("robot_type"),
                "incident_type": incident_data.get("incident_type"),
                "status": incident_data.get("status"),
            },
            "reliability_state": {"current": state, "previous": previous_state},
            "engineering_signals": fusion_result["engineering"],
            "ml_inference": {"diagnosis": diagnosis_for_memory},
        }
        memory_context = self.reliability_memory.historical_context(
            memory_query,
            exclude_incident_id=(incident.incident_id if incident is not None else None),
        )
        synthesis = self.evidence_synthesis.synthesize(
            feature_record=feature_record,
            observation_quality=observation_quality,
            risk_result=risk_result,
            diagnosis=diagnosis_result,
            recommendation=recommendation_result,
            incident=incident,
            comparison=comparison_result,
            baseline=baseline_result,
            baseline_visibility=baseline_visibility,
            fleet_context=fleet_context,
            historical_memory=memory_context,
            timeline=result["timeline"],
            telemetry_patterns=telemetry_patterns,
            sampling_analysis=sampling_analysis,
            observation_security=observation_security,
            historical_records=historical_records,
        )
        result["evidence_synthesis"] = synthesis
        result["telemetry_patterns"] = telemetry_patterns
        result["sampling_analysis"] = sampling_analysis or {}
        result["explanation"] = IncidentExplanation.build(
            result,
            feature_record,
            incident=incident,
            historical_memory=memory_context,
            fleet_context=fleet_context,
            evidence_synthesis=synthesis,
        )
        if incident is not None:
            self.reliability_memory.update_incident(
                incident,
                result["explanation"],
            )
        self.fleet_baseline.add_observation(feature_record, observation_quality)
        return result

    def _baseline_visibility(self, historical_records, baseline_result):
        """Describe the existing baseline result without changing eligibility."""
        records = historical_records or []
        required = getattr(self.baseline_engine, "minimum_records", 10)
        used = baseline_result.get("records_used", 0)
        if baseline_result.get("status") == "baseline_available":
            status = "AVAILABLE"
            reason = "Baseline is calculated from eligible historical observations."
        else:
            eligibility_known = any(
                "baseline_eligibility" in record or "health" in record
                for record in records
                if isinstance(record, dict)
            )
            if records and not eligibility_known:
                status = "ELIGIBILITY_UNKNOWN"
                reason = "No explicit eligibility decisions were supplied."
            else:
                status = "INSUFFICIENT"
                reason = (
                    f"{used} eligible record(s) are available; {required} are required."
                )
        return {
            "status": status,
            "reason": reason,
            "eligible_records": used,
            "required_records": required,
            "observed_records": len(records),
        }
                    

    
    def evaluate_timeline(self, feature_records):
        results = []
        previous_state = None
        historical_records = []

        for record in feature_records:

            result = self.evaluate(
                record,
                previous_state,
                historical_records
            )

            results.append(result)

            historical_records.append(record)

            previous_state = result["state"]

        return results


    def build_evidence_timeline(
        self,
        historical_records,
        current_record,
        risk_result,
        evidence_result,
        diagnosis_result,
        recommendation_result,
        state,
        observation_quality=None,
        fusion_result=None,
        state_changed=True,
    ):
        from evidence_timeline import EvidenceTimeline

        timeline = EvidenceTimeline()

        time_step = current_record["time_step"]

        # --------------------------------
        # 1. TELEMETRY OBSERVATIONS
        # --------------------------------

        motor_temperature = current_record.get(
            "motor_temperature"
        )

        thermal_rise = current_record.get(
            "thermal_rise"
        )

        battery_level = current_record.get(
            "battery_level"
        )

        workload = current_record.get(
            "workload"
        )

        if motor_temperature is not None:

            timeline.add_observation(
                time_step,
                (
                    f"Motor temperature: "
                    f"{motor_temperature}°C."
                ),
                {
                    "motor_temperature":
                        motor_temperature
                }
            )

        if thermal_rise is not None:

            timeline.add_observation(
                time_step,
                (
                    f"Thermal rise: "
                    f"{thermal_rise}°C."
                ),
                {
                    "thermal_rise":
                        thermal_rise
                }
            )

        if battery_level is not None:

            timeline.add_observation(
                time_step,
                (
                    f"Battery level: "
                    f"{battery_level}%."
                ),
                {
                    "battery_level":
                        battery_level
                }
            )

        if workload is not None:

            timeline.add_observation(
                time_step,
                f"Workload: {workload}.",
                {
                    "workload": workload
                }
            )

        # --------------------------------
        # 2. PREDICTION
        # --------------------------------

        probability = risk_result.get(
            "probability",
            0.0
        )

        prediction = risk_result.get("model_prediction")

        if observation_quality is not None:
            timeline.add_observation_quality(time_step, observation_quality)

        timeline.add_prediction(
            time_step,
            probability,
            prediction
        )

        if fusion_result is not None:
            timeline.add_fused_inference(time_step, fusion_result)

        # --------------------------------
        # 3. DIAGNOSIS
        # --------------------------------

        diagnosis = (
            diagnosis_result.get("failure_type")
            if diagnosis_result is not None
            else None
        )

        confidence = (
            diagnosis_result.get("confidence")
            if diagnosis_result is not None
            else None
        )

        if diagnosis and diagnosis != "none":

            timeline.add_diagnosis(
                time_step,
                diagnosis,
                confidence
            )

        # --------------------------------
        # 4. STATE
        # --------------------------------

        if state_changed:
            timeline.add_state_change(time_step, state)

        # --------------------------------
        # 5. ACTUAL FAILURE
        # --------------------------------

        if current_record.get(
            "failure_event",
            False
        ):

            failure_type = current_record.get(
                "failure_type"
            )

            # The simulator's failure event is ground truth.
            # Never substitute Genesis diagnosis for it.
            if not failure_type or failure_type == "none":
                failure_type = "unknown"

            timeline.add_failure(
                time_step,
                failure_type
            )

        # --------------------------------
        # 6. RECOVERY
        # --------------------------------

        if current_record.get(
            "recovery_event",
            False
        ):

            timeline.add_recovery(
                time_step
            )

        # --------------------------------
        # 7. RECOMMENDATION
        # --------------------------------

        recommendation = (
            recommendation_result.get("recommendation")
            if recommendation_result is not None
            else None
        )

        if recommendation:

            timeline.add_recommendation(
                time_step,
                recommendation
            )

        return timeline
