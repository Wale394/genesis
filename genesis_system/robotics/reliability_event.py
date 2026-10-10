class ReliabilityEvent:

    def __init__(
        self,
        robot_id,
        start_time_step,
        severity,
        diagnosis
    ):
        self.robot_id = robot_id
        self.start_time_step = start_time_step
        self.severity = severity
        self.diagnosis = diagnosis

        self.observations = []
        self.recovered = False
        self.recovery_time_step = None

    def add_observation(self, time_step, metrics):
        observation = {
            "time_step": time_step,
            "metrics": metrics
        }

        self.observations.append(observation)

    def mark_recovered(self, time_step):
        self.recovered = True
        self.recovery_time_step = time_step

    def get_duration(self):

        if not self.recovered:
            return None

        return self.recovery_time_step - self.start_time_step    

    def get_peak_thermal_rise(self):

        if not self.observations:
            return None

        return max(
            observation["metrics"]["thermal_rise"]
            for observation in self.observations
        )

    def get_peak_motor_temperature(self):

        if not self.observations:
            return None

        return max(
            observation["metrics"]["motor_temperature"]
            for observation in self.observations
        )

    def summary(self):

        return {
            "robot_id": self.robot_id,
            "start_time_step": self.start_time_step,
            "severity": self.severity,
            "diagnosis": self.diagnosis,
            "observations": len(self.observations),
            "peak_thermal_rise": self.get_peak_thermal_rise(),
            "peak_motor_temperature": self.get_peak_motor_temperature(),
            "recovered": self.recovered,
            "recovery_time_step": self.recovery_time_step,
            "duration": self.get_duration()
        }

    