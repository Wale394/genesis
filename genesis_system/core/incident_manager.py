from incident import Incident


class IncidentManager:

    ACTIVE_STATUSES = {
        "OPEN",
        "ACTIVE",
        "FAILED",
        "RECOVERING"
    }

    def __init__(self, history):

        self.history = history

        self.next_incident_number = 1

    # --------------------------------
    # INCIDENT ID
    # --------------------------------

    def _generate_incident_id(self):

        incident_id = (
            f"INC{self.next_incident_number:03d}"
        )

        self.next_incident_number += 1

        return incident_id

    # --------------------------------
    # FIND ACTIVE INCIDENT
    # --------------------------------

    def get_active_incident(
        self,
        robot_id
    ):

        for incident in reversed(
            self.history.incidents
        ):

            if (
                incident.robot_id == robot_id
                and incident.status
                in self.ACTIVE_STATUSES
            ):

                return incident

        return None

    # --------------------------------
    # CREATE INCIDENT
    # --------------------------------

    def create_incident(
        self,
        robot_id,
        start_time_step,
        incident_type=None,
        site_id=None
    ):

        existing_incident = (
            self.get_active_incident(
                robot_id
            )
        )

        if existing_incident is not None:

            return existing_incident

        incident = Incident(

            incident_id=
                self._generate_incident_id(),

            robot_id=
                robot_id,

            start_time_step=
                start_time_step,

            incident_type=
                incident_type,

            site_id=
                site_id
        )

        self.history.store_incident(
            incident
        )

        return incident

    # --------------------------------
    # UPDATE INCIDENT
    # --------------------------------

    def update_incident(
        self,
        robot_id,
        time_step,
        observation=None,
        evidence=None,
        prediction=None,
        diagnosis=None,
        confidence=None,
        recommendation=None
    ):

        incident = (
            self.get_active_incident(
                robot_id
            )
        )

        if incident is None:

            incident = self.create_incident(
                robot_id=robot_id,
                start_time_step=time_step
            )

        if incident.status == "OPEN":

            incident.status = "ACTIVE"

        if observation is not None:

            incident.add_observation(
                time_step=time_step,
                data=observation
            )

        if evidence is not None:

            incident.add_evidence(
                evidence
            )

        if prediction is not None:

            incident.add_prediction(
                prediction
            )

        if diagnosis is not None:

            incident.set_diagnosis(
                diagnosis,
                confidence
            )

        if recommendation is not None:

            incident.add_recommendation(
                recommendation,
                time_step=time_step,
            )

        return incident

    # --------------------------------
    # ACTUAL FAILURE
    # --------------------------------

    def mark_failed(
        self,
        robot_id,
        time_step,
        outcome=None
    ):

        incident = (
            self.get_active_incident(
                robot_id
            )
        )

        if incident is None:

            incident = self.create_incident(
                robot_id=robot_id,
                start_time_step=time_step
            )

        # Don't repeatedly mark the same
        # incident as failed.

        if incident.status != "FAILED":

            incident.status = "FAILED"

            incident.add_observation(

                time_step=time_step,

                data={
                    "actual_failure":
                        True
                }
            )

        if outcome is not None:

            incident.set_outcome(
                outcome
            )

        return incident

    # --------------------------------
    # RECOVERY
    # --------------------------------

    def mark_recovering(
        self,
        robot_id,
        time_step
    ):

        incident = (
            self.get_active_incident(
                robot_id
            )
        )

        if incident is None:

            return None

        # Don't repeatedly add recovery
        # observations.

        if incident.status != "RECOVERING":

            incident.status = "RECOVERING"

            incident.add_observation(

                time_step=time_step,

                data={
                    "recovery_started":
                        True
                }
            )

        return incident

    # --------------------------------
    # CLOSE
    # --------------------------------

    def close_incident(
        self,
        robot_id,
        end_time_step,
        outcome=None
    ):

        incident = (
            self.get_active_incident(
                robot_id
            )
        )

        if incident is None:

            return None

        incident.close(

            end_time_step=
                end_time_step,

            outcome=
                outcome
        )

        return incident
