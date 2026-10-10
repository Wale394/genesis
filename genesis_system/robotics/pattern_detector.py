class PatternDetector:

    def __init__(self, history):
        self.history = history

    def count_diagnoses(self):

        diagnosis_counts = {}

        for event in self.history.reliability_events:

            diagnosis = event.diagnosis

            if diagnosis not in diagnosis_counts:
                diagnosis_counts[diagnosis] = 0

            diagnosis_counts[diagnosis] += 1

        return diagnosis_counts

    def analyze_diagnosis_patterns(self):

        patterns = {}

        for event in self.history.reliability_events:

            diagnosis = event.diagnosis

            if diagnosis not in patterns:
                patterns[diagnosis] = {
                    "occurrences": 0,
                    "robots": set(),
                    "severities": [],
                    "durations": []
                }

            patterns[diagnosis]["occurrences"] += 1
            patterns[diagnosis]["robots"].add(event.robot_id)
            patterns[diagnosis]["severities"].append(event.severity)

            if event.get_duration() is not None:
                patterns[diagnosis]["durations"].append(
                    event.get_duration()
                )

        return patterns

    def detect_recurrence(self, diagnosis, minimum_gap=3):

        matching_events = []

        for event in self.history.reliability_events:

            if event.diagnosis == diagnosis:
                matching_events.append(event)

        if len(matching_events) < 2:
            return False

        matching_events.sort(
            key=lambda event: event.start_time_step
        )

        for index in range(len(matching_events) - 1):

            current_event = matching_events[index]
            next_event = matching_events[index + 1]

            gap = (
                next_event.start_time_step
                - current_event.start_time_step
            )

            if gap >= minimum_gap:
                return True

        return False

    def analyze_recurrence(self, minimum_gap=3):

        recurrence_results = {}

        diagnoses = set()

        for event in self.history.reliability_events:
            diagnoses.add(event.diagnosis)

        for diagnosis in diagnoses:

            recurring = self.detect_recurrence(
                diagnosis,
                minimum_gap
            )

            recurrence_results[diagnosis] = recurring

        return recurrence_results

    def calculate_recurrence_metrics(self, diagnosis):

        matching_events = []

        for event in self.history.reliability_events:

            if event.diagnosis == diagnosis:
                matching_events.append(event)

        if len(matching_events) < 2:

            return {
                "occurrences": len(matching_events),
                "start_times": [],
                "gaps": [],
                "average_gap": None,
                "minimum_gap": None,
                "maximum_gap": None
            }

        matching_events.sort(
            key=lambda event: event.start_time_step
        )

        start_times = [
            event.start_time_step
            for event in matching_events
        ]

        gaps = []

        for index in range(len(start_times) - 1):

            gap = (
                start_times[index + 1]
                - start_times[index]
            )

            gaps.append(gap)

        average_gap = sum(gaps) / len(gaps)

        return {
            "occurrences": len(matching_events),
            "start_times": start_times,
            "gaps": gaps,
            "average_gap": average_gap,
            "minimum_gap": min(gaps),
            "maximum_gap": max(gaps)
        }

    def analyze_event_conditions(self, diagnosis):

        matching_events = []

        for event in self.history.reliability_events:

            if event.diagnosis == diagnosis:
                matching_events.append(event)

        if not matching_events:
            return None

        working_observations = 0
        idle_observations = 0

        thermal_rises = []
        motor_temperatures = []
        ambient_temperatures = []

        for event in matching_events:

            for observation in event.observations:

                metrics = observation["metrics"]

                thermal_rises.append(
                    metrics["thermal_rise"]
                )

                motor_temperatures.append(
                    metrics["motor_temperature"]
                )

                ambient_temperatures.append(
                    metrics["ambient_temperature"]
                )

                if metrics["robot_state"] == "working":
                    working_observations += 1

                elif metrics["robot_state"] == "idle":
                    idle_observations += 1

        return {
            "occurrences": len(matching_events),
            "working_observations": working_observations,
            "idle_observations": idle_observations,
            "average_thermal_rise": (
                sum(thermal_rises) / len(thermal_rises)
            ),
            "average_motor_temperature": (
                sum(motor_temperatures)
                / len(motor_temperatures)
            ),
            "average_ambient_temperature": (
                sum(ambient_temperatures)
                / len(ambient_temperatures)
            )
        }

    def analyze_event_level_conditions(self, diagnosis):

        matching_events = []

        for event in self.history.reliability_events:

            if event.diagnosis == diagnosis:
                matching_events.append(event)

        if not matching_events:
            return None

        working_events = 0
        idle_events = 0

        event_thermal_rises = []
        event_motor_temperatures = []
        event_ambient_temperatures = []

        for event in matching_events:

            working_found = False
            idle_found = False

            thermal_rises = []
            motor_temperatures = []
            ambient_temperatures = []

            for observation in event.observations:

                metrics = observation["metrics"]

                thermal_rises.append(
                    metrics["thermal_rise"]
                )

                motor_temperatures.append(
                    metrics["motor_temperature"]
                )

                ambient_temperatures.append(
                    metrics["ambient_temperature"]
                )

                if metrics["robot_state"] == "working":
                    working_found = True

                elif metrics["robot_state"] == "idle":
                    idle_found = True

            if working_found:
                working_events += 1

            if idle_found:
                idle_events += 1

            event_thermal_rises.append(
                max(thermal_rises)
            )

            event_motor_temperatures.append(
                max(motor_temperatures)
            )

            event_ambient_temperatures.append(
                max(ambient_temperatures)
            )

        return {
            "events": len(matching_events),
            "working_events": working_events,
            "idle_events": idle_events,
            "average_peak_thermal_rise": (
                sum(event_thermal_rises)
                / len(event_thermal_rises)
            ),
            "average_peak_motor_temperature": (
                sum(event_motor_temperatures)
                / len(event_motor_temperatures)
            ),
            "average_peak_ambient_temperature": (
                sum(event_ambient_temperatures)
                / len(event_ambient_temperatures)
            )
        }

