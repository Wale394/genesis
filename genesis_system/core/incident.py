class Incident:

    def __init__(
        self,
        incident_id,
        robot_id,
        start_time_step,
        incident_type=None,
        site_id=None
    ):
        self.incident_id = incident_id
        self.robot_id = robot_id
        self.site_id = site_id

        self.start_time_step = start_time_step
        self.end_time_step = None

        self.incident_type = incident_type

        # What actually happened
        self.observations = []

        # Data supporting the interpretation
        self.evidence = []

        # What Genesis believes
        self.predictions = []
        self.diagnosis = None
        self.confidence = None

        # What Genesis recommends
        self.recommendations = []
        self._recommendation_keys = set()

        # What the human/system actually did
        self.actions = []

        # What happened afterward
        self.outcome = None

        self.status = "OPEN"

    # ----------------------------------------
    # OBSERVATION
    # ----------------------------------------

    def add_observation(self, time_step, data):
        item = {
            "time_step": time_step,
            "data": data
        }
        if item not in self.observations:
            self.observations.append(item)

    # ----------------------------------------
    # EVIDENCE
    # ----------------------------------------

    def add_evidence(self, evidence):
        if evidence not in self.evidence:
            self.evidence.append(evidence)

    # ----------------------------------------
    # PREDICTION
    # ----------------------------------------

    def add_prediction(self, prediction):
        if prediction not in self.predictions:
            self.predictions.append(prediction)

    # ----------------------------------------
    # DIAGNOSIS / INFERENCE
    # ----------------------------------------

    def set_diagnosis(self, diagnosis, confidence=None):
        self.diagnosis = diagnosis
        self.confidence = confidence

    # ----------------------------------------
    # RECOMMENDATION
    # ----------------------------------------

    def add_recommendation(self, recommendation, time_step=None):
        key = (time_step, recommendation)
        if key not in self._recommendation_keys:
            self.recommendations.append(recommendation)
            self._recommendation_keys.add(key)

    # ----------------------------------------
    # HUMAN / SYSTEM ACTION
    # ----------------------------------------

    def add_action(self, action):
        self.actions.append(action)

    # ----------------------------------------
    # OUTCOME
    # ----------------------------------------

    def set_outcome(self, outcome):
        if outcome is None:
            return
        if isinstance(self.outcome, dict) and isinstance(outcome, dict):
            self.outcome.update(outcome)
        elif self.outcome is None:
            self.outcome = outcome
        elif self.outcome != outcome:
            self.outcome = {"previous_outcome": self.outcome, "resolution": outcome}

    # ----------------------------------------
    # CLOSE INCIDENT
    # ----------------------------------------

    def close(self, end_time_step, outcome=None):
        if self.status == "CLOSED":
            self.set_outcome(outcome)
            return False

        self.end_time_step = end_time_step

        if outcome is not None:
            self.set_outcome(outcome)

        self.status = "CLOSED"
        return True


    def add_timeline_event(self, event):
        if event not in self.evidence:
            self.evidence.append(event)
    # ----------------------------------------
    # SUMMARY
    # ----------------------------------------

    def summary(self):
        return {
            "incident_id": self.incident_id,
            "robot_id": self.robot_id,
            "site_id": self.site_id,
            "start_time_step": self.start_time_step,
            "end_time_step": self.end_time_step,
            "incident_type": self.incident_type,
            "status": self.status,
            "observations": self.observations,
            "evidence": self.evidence,
            "predictions": self.predictions,
            "diagnosis": self.diagnosis,
            "confidence": self.confidence,
            "recommendations": self.recommendations,
            "actions": self.actions,
            "outcome": self.outcome
        }
