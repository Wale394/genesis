import robot_profile
from reliability_event import ReliabilityEvent

class Analyzer:
    def __init__(self, history):
        self.history = history


    def check_temperature(self):
        print("Analyzer is running...")


        for entry in self.history.records:
            motor_temp = entry["telemetry"]["motor_temperature"]
            if motor_temp > 60:
                print(f"Warning: Motor temperature {motor_temp}°C exceeds safe limit for robot {entry['identity']['robot_id']}.")


    def check_temperature_trend(self):
        if len(self.history.records) < 5:
            print("Not enough data to analyze temperature trend.")
            return
        

        record1 = self.history.records[-5]
        record2 = self.history.records[-4]
        record3 = self.history.records[-3]
        record4 = self.history.records[-2]
        record5 = self.history.records[-1]

        total_change = record5["telemetry"]["motor_temperature"] - record1["telemetry"]["motor_temperature"]

        change1 = record2["telemetry"]["motor_temperature"] - record1["telemetry"]["motor_temperature"]
        change2 = record3["telemetry"]["motor_temperature"] - record2["telemetry"]["motor_temperature"]
        change3 = record4["telemetry"]["motor_temperature"] - record3["telemetry"]["motor_temperature"]
        change4 = record5["telemetry"]["motor_temperature"] - record4["telemetry"]["motor_temperature"]

        if change1 > 0 and change2 > 0 and change3 > 0 and change4 > 0 and total_change > 5:
            print("Warning: Motor temperature has continuously increased over the last 5 updates.")

    def check_temperature_change(self):

        if len(self.history.records) < 2:
            print("Not enough data to analyze temperature change.")
            return

        for step in range(len(self.history.records) - 1):

            previous_record = self.history.records[step]
            current_record = self.history.records[step + 1]

            previous_temp = (
                previous_record["telemetry"]["motor_temperature"]
            )

            current_temp = (
                current_record["telemetry"]["motor_temperature"]
            )

            temperature_change = current_temp - previous_temp

            if temperature_change > 6:

                print(
                    f"Warning: Critical motor temperature increase "
                    f"of {temperature_change}°C between updates "
                    f"{step + 1} and {step + 2}."
                )

            elif temperature_change >= 3:

                print(
                    f"Warning: Significant motor temperature increase "
                    f"of {temperature_change}°C between updates "
                    f"{step + 1} and {step + 2}."
                )

            elif temperature_change >= 1:

                print(
                    f"Notice: Moderate motor temperature increase "
                    f"of {temperature_change}°C between updates "
                    f"{step + 1} and {step + 2}."
                )

            elif temperature_change < -6:

                print(
                    f"Warning: Significant motor temperature decrease "
                    f"of {abs(temperature_change)}°C between updates "
                    f"{step + 1} and {step + 2}."
                )

            elif temperature_change <= -1:

                print(
                    f"Notice: Moderate motor temperature decrease "
                    f"of {abs(temperature_change)}°C between updates "
                    f"{step + 1} and {step + 2}."
                )

            else:

                print(
                    f"Motor temperature change of "
                    f"{temperature_change}°C between updates "
                    f"{step + 1} and {step + 2} "
                    f"is within normal range."
                )


    def check_temperature_context(self, robot_profile):
        for entry in self.history.records:
            motor_temp = entry["telemetry"]["motor_temperature"]
            robot_id = entry["identity"]["robot_id"]
            robot_state = entry["telemetry"]["robot_state"]

            if robot_state == "working":
                if motor_temp > robot_profile.critical_working_temp:
                    print(
                        f"Critical Warning: Motor temperature {motor_temp}°C "
                        f"exceeds critical working limit for robot {robot_id}."
                    )
                elif motor_temp > robot_profile.abnormal_working_temp:
                    print(
                        f"Warning: Motor temperature {motor_temp}°C "
                        f"exceeds abnormal working limit for robot {robot_id}."
                    )
                elif motor_temp > robot_profile.normal_working_temp:
                    print(
                        f"Notice: Motor temperature {motor_temp}°C "
                        f"is above normal working limit for robot {robot_id}."
                    )

            elif robot_state == "idle":
                if motor_temp > robot_profile.critical_idle_temp:
                    print(
                        f"Critical Warning: Motor temperature {motor_temp}°C "
                        f"exceeds critical idle limit for robot {robot_id}."
                    )
                elif motor_temp > robot_profile.abnormal_idle_temp:
                    print(
                        f"Warning: Motor temperature {motor_temp}°C "
                        f"exceeds abnormal idle limit for robot {robot_id}."
                    )
                elif motor_temp > robot_profile.normal_idle_temp:
                    print(
                        f"Notice: Motor temperature {motor_temp}°C "
                        f"is above normal idle limit for robot {robot_id}."
                    )


    def check_ambient_temperature(self, robot_profile):

            for entry in self.history.records:

                ambient_temp = entry["telemetry"]["ambient_temperature"]
                robot_id = entry["identity"]["robot_id"]
                robot_state = entry["telemetry"]["robot_state"]

                if robot_state == "working":

                    if ambient_temp > robot_profile.critical_ambient_temp:
                        print(
                            f"Critical Warning: Ambient temperature {ambient_temp}°C "
                            f"exceeds critical ambient limit for robot {robot_id}."
                        )

                elif ambient_temp > robot_profile.abnormal_ambient_temp:
                        print(
                            f"Warning: Ambient temperature {ambient_temp}°C "
                            f"exceeds abnormal ambient limit for robot {robot_id}."
                        )

                elif ambient_temp > robot_profile.normal_ambient_temp:
                        print(
                            f"Notice: Ambient temperature {ambient_temp}°C "
                            f"is above normal ambient limit for robot {robot_id}."
                        )


    def check_thermal_rise(self):

        for entry in self.history.records:

            motor_temp = entry["telemetry"]["motor_temperature"]
            ambient_temp = entry["telemetry"]["ambient_temperature"]
            robot_id = entry["identity"]["robot_id"]

            thermal_rise = motor_temp - ambient_temp

            print(
                f"Robot {robot_id}: "
                f"Thermal rise = {thermal_rise}°C "
                f"(Motor: {motor_temp}°C, Ambient: {ambient_temp}°C)"
            )


    def check_relative_thermal_change(self):

        if len(self.history.records) < 2:
           print("Not enough data to analyze relative thermal change.")
           return

        for step in range(len(self.history.records) - 1):

           previous_record = self.history.records[step]
           current_record = self.history.records[step + 1]

           previous_motor_temp = previous_record["telemetry"]["motor_temperature"]
           current_motor_temp = current_record["telemetry"]["motor_temperature"]

           previous_ambient_temp = previous_record["telemetry"]["ambient_temperature"]
           current_ambient_temp = current_record["telemetry"]["ambient_temperature"]

           motor_change = current_motor_temp - previous_motor_temp
           ambient_change = current_ambient_temp - previous_ambient_temp

           relative_thermal_change = motor_change - ambient_change

           robot_id = current_record["identity"]["robot_id"]

           print(
              f"Robot {robot_id}: "
              f"Relative thermal change = {relative_thermal_change}°C "
              f"(Motor change: {motor_change}°C, "
              f"Ambient change: {ambient_change}°C)"
           )


    def check_thermal_rise_context(self,robot_profile):


        for entry in self.history.records:

            motor_temp = entry["telemetry"]["motor_temperature"]
            ambient_temp = entry["telemetry"]["ambient_temperature"]
            robot_id = entry["identity"]["robot_id"]   
            robot_state = entry["telemetry"]["robot_state"] 

            thermal_rise = motor_temp - ambient_temp

            if robot_state == "working" :
                if thermal_rise > robot_profile.critical_thermal_rise:
                    print(f"Critical warning: Thermal rise {thermal_rise}°C"
                          f" exceeds critical thermal_rise for {robot_id}.")
                 
                elif thermal_rise > robot_profile.abnormal_thermal_rise:
                    print(f"Warning: Thermal rise {thermal_rise}°C"
                          f" exceeds abnormal thermal_rise for {robot_id}. ")

                elif thermal_rise > robot_profile.normal_thermal_rise:
                    print(f"Notice: Thermalrise {thermal_rise} °C"
                          f" is above normal thermal rise for  {robot_id}. ")

                else :
                    print(f" Thermal rise {thermal_rise} °C"
                          f" is normal for {robot_id}.")


    def calculate_thermal_metrics(self, previous_record, current_record):

        previous_motor_temp = previous_record["telemetry"]["motor_temperature"]
        current_motor_temp = current_record["telemetry"]["motor_temperature"]

        previous_ambient_temp = previous_record["telemetry"]["ambient_temperature"]
        current_ambient_temp = current_record["telemetry"]["ambient_temperature"]

        motor_change = current_motor_temp - previous_motor_temp
        ambient_change = current_ambient_temp - previous_ambient_temp

        thermal_rise = current_motor_temp - current_ambient_temp
        relative_thermal_change = motor_change - ambient_change

        return {
            "thermal_rise": thermal_rise,
            "motor_change": motor_change,
            "ambient_change": ambient_change,
            "relative_thermal_change": relative_thermal_change
        }


    def detect_thermal_anomaly(self, thermal_rise, robot_profile):

        return thermal_rise > robot_profile.abnormal_thermal_rise


    def determine_severity(self, thermal_rise, robot_profile):

        if thermal_rise >= robot_profile.critical_thermal_rise:
            return "CRITICAL"

        elif thermal_rise >= robot_profile.abnormal_thermal_rise:
            return "WARNING"

        else:
            return "NORMAL"


    def diagnose_thermal_cause(
        self,
        robot_state,
        relative_thermal_change
    ):

        if relative_thermal_change <= 0:
            return "Possible environmental heating"

        elif robot_state == "working":
            return "Possible workload-related heating"

        elif robot_state == "idle":
            return "Possible abnormal internal heating"

        else:
            return "Unknown thermal behavior"


    def analyze_thermal_behavior(self, robot_profile):

        if len(self.history.records) < 2:
            print("Not enough data to analyze thermal behavior.")
            return

        thermal_anomaly_count = 0
        active_event = None

        for step in range(len(self.history.records) - 1):

            previous_record = self.history.records[step]
            current_record = self.history.records[step + 1]

            metrics = self.calculate_thermal_metrics(
                previous_record,
                current_record
            )

            thermal_rise = metrics["thermal_rise"]
            relative_thermal_change = metrics["relative_thermal_change"]

            robot_id = current_record["identity"]["robot_id"]
            current_time_step = current_record["telemetry"]["time_step"]
            robot_state = current_record["telemetry"]["robot_state"]

            anomaly_detected = self.detect_thermal_anomaly(
                thermal_rise,
                robot_profile
            )

            if anomaly_detected:

                thermal_anomaly_count += 1

                print(
                    f"Thermal anomaly count: "
                    f"{thermal_anomaly_count}"
                )

                # Create event after 3 consecutive anomalies
                if thermal_anomaly_count == 3:

                    severity = self.determine_severity(
                        thermal_rise,
                        robot_profile
                    )

                    diagnosis = self.diagnose_thermal_cause(
                        robot_state,
                        relative_thermal_change
                    )

                    active_event = ReliabilityEvent(
                        robot_id=robot_id,
                        start_time_step=current_time_step - 2,
                        severity=severity,
                        diagnosis=diagnosis
                    )

                    # Add the three observations that caused the event
                    for observation_record in self.history.records[
                        step - 1 : step + 2
                    ]:

                        observation_time = (
                            observation_record["telemetry"]["time_step"]
                        )

                        observation_motor_temp = (
                            observation_record["telemetry"]["motor_temperature"]
                        )

                        observation_ambient_temp = (
                            observation_record["telemetry"]["ambient_temperature"]
                        )

                        observation_metrics = {
                            "thermal_rise": (
                                observation_motor_temp
                                - observation_ambient_temp
                            ),
                            "motor_temperature": observation_motor_temp,
                            "ambient_temperature": observation_ambient_temp,
                            "robot_state": observation_record[
                                "telemetry"
                            ]["robot_state"]
                        }

                        active_event.add_observation(
                            observation_time,
                            observation_metrics
                        )

                    self.history.store_event(active_event)

                    print("\nStored Reliability Event:")
                    print(active_event.summary())

                # If event already exists, keep collecting evidence
                elif thermal_anomaly_count > 3 and active_event is not None:

                    observation_metrics = {
                        "thermal_rise": thermal_rise,
                        "motor_temperature": current_record[
                            "telemetry"
                        ]["motor_temperature"],
                        "ambient_temperature": current_record[
                            "telemetry"
                        ]["ambient_temperature"],
                        "robot_state": robot_state
                    }

                    active_event.add_observation(
                        current_time_step,
                        observation_metrics
                    )

                    print(
                        f"Event observation added at "
                        f"time step {current_time_step}."
                    )

            else:

                if thermal_anomaly_count > 0 and active_event is not None:

                    active_event.mark_recovered(
                        current_time_step
                    )

                    print(
                        f"Thermal condition recovered for "
                        f"robot {robot_id}."
                    )

                    print(
                        f"Recovery time step: "
                        f"{current_time_step}"
                    )

                    print(
                        f"Event duration: "
                        f"{active_event.get_duration()} time steps"
                    )

                    print(
                        f"Total observations: "
                        f"{len(active_event.observations)}"
                    )

                    active_event = None

                thermal_anomaly_count = 0