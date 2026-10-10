class EvidenceTimeline:

    def __init__(self):
        self.events = []

    def add_event(
        self,
        time_step,
        event_type,
        description,
        source="telemetry",
        data=None
    ):
        event = {
            "time_step": time_step,
            "event_type": event_type,
            "description": description,
            "source": source,
            "data": data or {}
        }

        self.events.append(event)
        self.events.sort(key=lambda event: event["time_step"])

        return event

    def add_observation(
        self,
        time_step,
        description,
        data=None
    ):
        return self.add_event(
            time_step=time_step,
            event_type="observation",
            description=description,
            source="telemetry",
            data=data
        )

    def add_prediction(
        self,
        time_step,
        probability,
        prediction
    ):
        if probability is None or prediction is None:
            description = "Failure prediction unavailable; evidence is insufficient."
        else:
            description = f"Failure probability {probability:.2f}"
        return self.add_event(
            time_step=time_step,
            event_type="prediction",
            description=description,
            source="prediction_engine",
            data={
                "probability": probability,
                "prediction": prediction
            }
        )

    def add_fused_inference(self, time_step, fusion_result):
        final = fusion_result.get("final", {})
        engineering = fusion_result.get("engineering", {})
        return self.add_event(
            time_step=time_step,
            event_type="reliability_inference",
            description=(
                f"Reliability fusion assessed risk as {final.get('risk')} "
                f"with operational prediction {final.get('prediction')}."
            ),
            source="reliability_fusion",
            data={
                "risk": final.get("risk"),
                "prediction": final.get("prediction"),
                "confidence_limited": final.get("confidence_limited"),
                "engineering_severity": engineering.get("severity"),
            },
        )

    def add_observation_quality(self, time_step, quality):
        group_status = {
            name: item["status"]
            for name, item in quality.get("groups", {}).items()
        }
        limited = quality.get("any_major_group_limited", False)
        return self.add_event(
            time_step=time_step,
            event_type="observation_quality",
            description=(
                f"Telemetry evidence quality is {quality.get('status')}; "
                f"signal groups: {group_status}."
            ),
            source="observation_quality",
            data={
                "status": quality.get("status"),
                "groups": group_status,
                "major_signal_group_limited": limited,
                "prediction_ready": quality.get("prediction_ready"),
                "details": quality,
            },
        )

    def add_state_change(
        self,
        time_step,
        state
    ):
        return self.add_event(
            time_step=time_step,
            event_type="state_change",
            description=(
                f"Reliability state changed to {state}."
            ),
            source="reliability_state",
            data={
                "state": state
            }
        )

    def add_outcome(self, time_step, outcome):
        return self.add_event(
            time_step=time_step,
            event_type="outcome",
            description=(
                f"Incident resolved; final state is {outcome.get('final_state')}."
            ),
            source="decision_pipeline",
            data=outcome,
        )

    def add_failure(
        self,
        time_step,
        failure_type
    ):
        return self.add_event(
            time_step=time_step,
            event_type="failure",
            description=(
                f"Actual {failure_type} failure detected."
            ),
            source="simulator",
            data={
                "failure_type": failure_type,
                "ground_truth": True
            }
        )

    def add_recovery(
        self,
        time_step
    ):
        return self.add_event(
            time_step=time_step,
            event_type="recovery",
            description=(
                "Recovery or maintenance event detected."
            ),
            source="simulator",
            data={
                "ground_truth": True
            }
        )

    def add_diagnosis(
        self,
        time_step,
        diagnosis,
        confidence=None
    ):
        data = {
            "diagnosis": diagnosis
        }

        if confidence is not None:
            data["confidence"] = confidence

        return self.add_event(
            time_step=time_step,
            event_type="diagnosis",
            description=(
                f"Genesis diagnosis: {diagnosis}."
            ),
            source="diagnosis_engine",
            data=data
        )

    def add_recommendation(
        self,
        time_step,
        recommendation
    ):
        return self.add_event(
            time_step=time_step,
            event_type="recommendation",
            description=recommendation,
            source="recommendation_engine",
            data={
                "recommendation": recommendation
            }
        )

    def get_events(self):
        return list(self.events)

    def get_events_between(
        self,
        start_time,
        end_time
    ):
        return [
            event
            for event in self.events
            if start_time <= event["time_step"] <= end_time
        ]

    def build_timeline(self):
        return {
            "event_count": len(self.events),
            "events": self.get_events()
        }

    def summary(self):
        lines = []

        for event in self.events:
            lines.append(
                f"t={event['time_step']} | "
                f"{event['event_type']} | "
                f"{event['description']}"
            )

        return "\n".join(lines)
