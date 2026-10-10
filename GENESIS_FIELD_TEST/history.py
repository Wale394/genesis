class History:

    def __init__(self):
        self.records = []
        self.reliability_events = []
        self.incidents = []

    # ----------------------------------------
    # TELEMETRY
    # ----------------------------------------

    def store(self, record):
        self.records.append(record)

    # ----------------------------------------
    # RELIABILITY EVENTS
    # ----------------------------------------

    def store_event(self, event):
        self.reliability_events.append(event)

    # ----------------------------------------
    # INCIDENTS
    # ----------------------------------------

    def store_incident(self, incident):
        self.incidents.append(incident)

    # ----------------------------------------
    # RETRIEVAL
    # ----------------------------------------

    def get_incident(self, incident_id):

        for incident in self.incidents:

            if incident.incident_id == incident_id:
                return incident

        return None

    def get_robot_incidents(self, robot_id):

        return [
            incident
            for incident in self.incidents
            if incident.robot_id == robot_id
        ]