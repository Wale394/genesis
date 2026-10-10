import random


DEFAULT_SIMULATION_CONFIG = {
    "thermal_failure_threshold": 80.0,
    "thermal_degradation_scale": 1.0,
    "thermal_observation_coupling": 8.0,
    "battery_degradation_rate_range": (0.002, 0.006),
    "battery_stress_scale": 1.0,
    "battery_failure_health_threshold": 0.70,
    "battery_failure_stress_threshold": 5.0,
    "battery_failure_level_threshold": 35.0,
    "battery_observation_coupling": 1.0,
    "telemetry_noise_scale": 1.0,
    "workload_schedule": ("low", "medium", "high", "medium"),
    "workload_interval": 20,
    "workload_mode": "synchronized",
    "thermal_failure_uses_observed_temperature": True,
}


class FleetSimulator:

    def __init__(self, number_of_robots=10, config=None):
        self.number_of_robots = number_of_robots
        self.config = dict(DEFAULT_SIMULATION_CONFIG)
        self.config.update(config or {})
        self.robots = []

    def create_fleet(self):

        manufacturers = [
            "Manufacturer_A",
            "Manufacturer_B",
            "Manufacturer_C"
        ]

        robot_types = [
            "AMR",
            "Robotic_Arm",
            "Humanoid"
        ]

        for number in range(
            1,
            self.number_of_robots + 1
        ):

            manufacturer = random.choice(manufacturers)
            robot_type = random.choice(robot_types)

            workload_mode = self.config["workload_mode"]
            if workload_mode == "sustained_high":
                initial_workload = "high"
            elif workload_mode == "sustained_low":
                initial_workload = "low"
            else:
                initial_workload = random.choice([
                    "low", "medium", "high"
                ])

            ambient_temperature = random.randint(20, 40)
            initial_health = random.choice([
                "healthy", "healthy", "degrading"
            ])

            robot = {
                "robot_id": f"R{number:03d}",
                "manufacturer": manufacturer,
                "robot_type": robot_type,
                "workload": initial_workload,
                "ambient_temperature": ambient_temperature,

                # Initial condition only.
                # The simulation updates the current health state over time.
                "initial_health": initial_health
            }

            self.robots.append(robot)

        return self.robots

    def simulate_temperature(
        self,
        robot,
        time_step
    ):

        ambient_temperature = robot[
            "ambient_temperature"
        ]

        workload = robot["workload"]
        health = robot.get(
            "initial_health",
            "healthy"
        )

        if workload == "low":

            workload_heat = 2

        elif workload == "medium":

            workload_heat = 5

        else:

            workload_heat = 8

        if health == "healthy":

            degradation_heat = (
                time_step * 0.05
            )

        elif health == "degrading":

            degradation_heat = (
                time_step * 0.4
            )

        else:

            degradation_heat = (
                time_step * 0.8
            )

        random_variation = random.uniform(
            -1,
            1
        )

        motor_temperature = (
            ambient_temperature
            + workload_heat
            + degradation_heat
            + random_variation
        )

        return round(
            motor_temperature,
            2
        )

    def simulate_temperature_series(
        self,
        robot,
        time_steps=100
    ):

        temperature_series = []

        degradation_level = 0.0

        battery_level = 100.0
        battery_health = 1.0
        battery_stress = 0.0

        battery_degradation_rate = random.uniform(
            *self.config["battery_degradation_rate_range"]
        )

        workload_cycle = list(self.config["workload_schedule"])
        workload_interval = self.config["workload_interval"]
        workload_mode = self.config["workload_mode"]
        workload_phase = (
            random.randrange(len(workload_cycle))
            if workload_mode == "asynchronous" and workload_cycle
            else 0
        )

        # --------------------------------
        # FAILURE STATE
        # --------------------------------

        failed = False

        failure_type = "none"

        # New:
        # True only on the exact timestep
        # where the robot actually fails.

        failure_event = False

        recovery_event = False
        recovery_delay = 5
        failure_time_step = None

        current_ambient_temperature = (
            robot["ambient_temperature"]
        )

        current_workload = robot["workload"]

        # --------------------------------
        # CHOOSE FAILURE MECHANISM
        # --------------------------------

        failure_mechanism = random.choices(
            [
                "none",
                "thermal",
                "battery"
            ],
            weights=[
                0.60,
                0.20,
                0.20
            ],
            k=1
        )[0]

        # --------------------------------
        # CHOOSE THERMAL DEGRADATION PATTERN
        # --------------------------------

        if failure_mechanism == "thermal":

            if robot.get("initial_health", "healthy") == "degrading":

                degradation_pattern = random.choice([
                    "gradual",
                    "sudden",
                    "intermittent"
                ])

            else:

                degradation_pattern = random.choice([
                    "gradual",
                    "sudden"
                ])

        else:

            degradation_pattern = "healthy"

        # --------------------------------
        # SIMULATION LOOP
        # --------------------------------

        for time_step in range(
            1,
            time_steps + 1
        ):

            # Reset the event flag every timestep.
            #
            # This is important because an actual
            # failure event should happen only once.

            failure_event = False
            recovery_event = False

            # --------------------------------
            # 1. THERMAL DEGRADATION
            # --------------------------------

            degradation_scale = self.config["thermal_degradation_scale"]
            if degradation_pattern == "healthy":

                # A healthy robot can accumulate small wear/noise,
                # but should not automatically become degraded.
                degradation_level += degradation_scale * random.uniform(
                    0.0,
                    0.01
                )

            elif degradation_pattern == "gradual":

                degradation_level += 0.08 * degradation_scale

            elif degradation_pattern == "sudden":

                if time_step < 40:

                    degradation_level += 0.03 * degradation_scale

                else:

                    degradation_level += 0.30 * degradation_scale

            elif degradation_pattern == "intermittent":

                if 25 <= time_step <= 35:

                    degradation_level += 0.25 * degradation_scale

                elif 60 <= time_step <= 70:

                    degradation_level += 0.30 * degradation_scale

                else:

                    degradation_level += 0.03 * degradation_scale

            degradation_level = max(
                0,
                degradation_level
            )

            # --------------------------------
            # 2. WORKLOAD CHANGES
            # --------------------------------

            # Change workload every 20 steps.

            if workload_mode in ("sustained_high", "sustained_low"):
                current_workload = (
                    "high" if workload_mode == "sustained_high" else "low"
                )
            elif workload_mode in ("synchronized", "asynchronous", "mixed"):
                if workload_interval > 0 and time_step % workload_interval == 0:
                    phase = workload_phase if workload_mode == "asynchronous" else 0
                    if workload_mode == "mixed":
                        current_workload = random.choice(workload_cycle)
                    else:
                        current_workload = workload_cycle[
                            ((time_step // workload_interval) + phase)
                            % len(workload_cycle)
                        ]

            # --------------------------------
            # 3. AMBIENT TEMPERATURE
            # --------------------------------

            ambient_change = random.uniform(
                -0.5,
                0.5
            )

            current_ambient_temperature += (
                ambient_change
            )

            current_ambient_temperature = max(
                18,
                min(
                    current_ambient_temperature,
                    42
                )
            )

            # --------------------------------
            # 4. BATTERY HEALTH
            # --------------------------------

            if failure_mechanism == "battery":

                battery_health -= (
                    battery_degradation_rate
                )

                battery_health = max(
                    battery_health,
                    0.55
                )

                battery_stress += self.config["battery_stress_scale"] * random.uniform(
                    0.05,
                    0.15
                )

            # --------------------------------
            # BATTERY STRESS FROM WORKLOAD
            # --------------------------------

            if current_workload == "low":

                stress_multiplier = 0.5

            elif current_workload == "medium":

                stress_multiplier = 1.0

            else:

                stress_multiplier = 1.5

            battery_stress += (
                self.config["battery_stress_scale"]
                * 0.05
                * stress_multiplier
            )

            # --------------------------------
            # DEGRADED BATTERY STRESS
            # --------------------------------

            if failure_mechanism == "battery":

                battery_stress += self.config["battery_stress_scale"] * (
                    (1 - battery_health)
                    * stress_multiplier
                )

            # --------------------------------
            # 5. BATTERY CONSUMPTION
            # --------------------------------

            if current_workload == "low":

                battery_drop = 0.8

            elif current_workload == "medium":

                battery_drop = 1.2

            else:

                battery_drop = 1.6

            # Degraded batteries consume
            # more energy.

            battery_drop = (
                battery_drop
                / battery_health
            )

            battery_level -= battery_drop

            battery_level = max(
                battery_level,
                0
            )

            # --------------------------------
            # 6. WORKLOAD HEAT
            # --------------------------------

            if current_workload == "low":

                workload_heat = 2

            elif current_workload == "medium":

                workload_heat = 5

            else:

                workload_heat = 8

            # --------------------------------
            # 7. DEGRADATION HEAT
            # --------------------------------

            internal_degradation_heat = degradation_level * 8
            degradation_heat = (
                degradation_level
                * self.config["thermal_observation_coupling"]
            )

            # --------------------------------
            # 8. COOLING
            # --------------------------------

            cooling = random.uniform(
                0,
                3
            )

            # --------------------------------
            # 9. TEMPORARY THERMAL DISTURBANCE
            # --------------------------------

            thermal_spike = 0

            if random.random() < 0.05:

                thermal_spike = random.uniform(
                    3 * self.config["telemetry_noise_scale"],
                    10 * self.config["telemetry_noise_scale"]
                )

            # --------------------------------
            # 10. SENSOR / ENVIRONMENT NOISE
            # --------------------------------

            random_variation = random.uniform(
                -1.5 * self.config["telemetry_noise_scale"],
                1.5 * self.config["telemetry_noise_scale"]
            )

            # --------------------------------
            # 11. FINAL MOTOR TEMPERATURE
            # --------------------------------

            motor_temperature = (
                current_ambient_temperature
                + workload_heat
                + degradation_heat
                + thermal_spike
                - cooling
                + random_variation
            )

            motor_temperature = round(
                motor_temperature,
                2
            )

            internal_motor_temperature = (
                current_ambient_temperature
                + workload_heat
                + internal_degradation_heat
            )
            failure_temperature = (
                motor_temperature
                if self.config["thermal_failure_uses_observed_temperature"]
                else internal_motor_temperature
            )

            # --------------------------------
            # 12. DETERMINE ACTUAL FAILURE
            # --------------------------------

            if not failed:

                # ----------------------------
                # THERMAL FAILURE
                # ----------------------------

                if (
                    failure_mechanism == "thermal"
                    and failure_temperature >= self.config["thermal_failure_threshold"]
                ):

                    failed = True

                    failure_type = "thermal"

                    # NEW:
                    # This timestep is the actual
                    # failure event.

                    failure_event = True
                    failure_time_step = time_step

                # ----------------------------
                # BATTERY FAILURE
                # ----------------------------

                elif (
                    failure_mechanism == "battery"
                    and battery_health <= self.config["battery_failure_health_threshold"]
                    and battery_stress >= self.config["battery_failure_stress_threshold"]
                    and battery_level <= self.config["battery_failure_level_threshold"]
                ):

                    failed = True

                    failure_type = "battery"

                    # NEW:
                    # This timestep is the actual
                    # failure event.

                    failure_event = True
                    failure_time_step = time_step

            # --------------------------------
            # RECOVERY / MAINTENANCE EVENT
            # --------------------------------

            if (
                failed
                and failure_time_step is not None
                and time_step >= failure_time_step + recovery_delay
            ):

                recovery_event = True
                failed = False

                # Simulate maintenance restoring the affected subsystem.
                if failure_type == "thermal":

                    degradation_level = min(
                        degradation_level,
                        0.5
                    )

                elif failure_type == "battery":

                    battery_health = max(
                        battery_health,
                        0.90
                    )

                    battery_stress = 0.5

                # The robot has returned to operation.
                failure_time_step = None

            # --------------------------------
            # 13. DYNAMIC HEALTH STATE
            # --------------------------------
            # Health is derived from the current simulated condition.
            # It is not a permanent robot attribute.

            if failed:
                current_health = "failed"
            elif (
                degradation_level >= 2.5
                or battery_health <= 0.70
            ):
                current_health = "critical"
            elif (
                degradation_level >= 0.8
                or battery_health <= 0.85
            ):
                current_health = "degrading"
            else:
                current_health = "healthy"

            # --------------------------------
            # 14. ROBOT STATE
            # --------------------------------

            robot_state = (
                "failed"
                if failed
                else "working"
            )

            # --------------------------------
            # 14.5. ELECTRICAL TELEMETRY
            # --------------------------------

            # Synthetic electrical measurements for simulation.
            # These are not real robot specifications.

            nominal_voltage = 48.0

            if current_workload == "low":
                base_current = 10.0
            elif current_workload == "medium":
                base_current = 20.0
            else:
                base_current = 30.0

            # Higher workload and battery degradation increase current demand.
            battery_current = (
                base_current
                * (1 + (1 - battery_health) * 0.5 * self.config["battery_observation_coupling"])
                + random.uniform(
                    -1.0 * self.config["telemetry_noise_scale"],
                    1.0 * self.config["telemetry_noise_scale"]
                )
            )

            battery_current = max(
                0.0,
                battery_current
            )

            # Simulated voltage drop from battery stress and degradation.
            voltage_drop = (
                battery_stress * 0.15 * self.config["battery_observation_coupling"]
                + (1 - battery_health) * 4.0 * self.config["battery_observation_coupling"]
                + random.uniform(
                    0.0,
                    0.5 * self.config["telemetry_noise_scale"]
                )
            )

            battery_voltage = (
                nominal_voltage
                - voltage_drop
            )

            battery_voltage = max(
                40.0,
                battery_voltage
            )

            # Battery temperature rises with current and degradation.
            battery_temperature = (
                current_ambient_temperature
                + (battery_current * 0.15)
                + ((1 - battery_health) * 10 * self.config["battery_observation_coupling"])
                + random.uniform(
                    -0.5 * self.config["telemetry_noise_scale"],
                    0.5 * self.config["telemetry_noise_scale"]
                )
            )

            battery_temperature = round(
                battery_temperature,
                2
            )

            # Electrical power = voltage × current.
            power_consumption = (
                battery_voltage
                * battery_current
            )

            battery_voltage = round(
                battery_voltage,
                2
            )

            battery_current = round(
                battery_current,
                2
            )

            voltage_drop = round(
                voltage_drop,
                2
            )

            power_consumption = round(
                power_consumption,
                2
            )

            # --------------------------------
            # 15. STORE TELEMETRY
            # --------------------------------

            temperature_series.append({

                "time_step":
                    time_step,

                "robot_id":
                    robot["robot_id"],

                "motor_temperature":
                    motor_temperature,

                "ambient_temperature":
                    round(
                        current_ambient_temperature,
                        2
                    ),

               "workload": 
                    self.workload_to_numeric(current_workload),

                "battery_level":
                    round(
                        battery_level,
                        2
                    ),

                "battery_voltage":
                    battery_voltage,

                "battery_current":
                    battery_current,

                "battery_temperature":
                    battery_temperature,

                "power_consumption":
                    power_consumption,

                "voltage_drop":
                    voltage_drop,

                "robot_state":
                    robot_state,

                # Dynamic current health, not the initial condition.
                "health":
                    current_health,

                "initial_health":
                    robot["initial_health"],

                "degradation_level":
                    round(
                        degradation_level,
                        2
                    ),

                "battery_health":
                    round(
                        battery_health,
                        3
                    ),

                "battery_stress":
                    round(
                        battery_stress,
                        3
                    ),

                # Persistent training label.
                #
                # Once failure occurs, this remains
                # thermal/battery for later records.

                "failure_type":
                    failure_type,

                # NEW:
                #
                # True ONLY at the exact timestep
                # where the failure first happens.

                "failure_event":
                    failure_event,

                "recovery_event":
                    recovery_event

            })

        return temperature_series

    def workload_to_numeric(self, workload):
        mapping = {
            "low": 25.0,
            "medium": 55.0,
            "high": 85.0
        }

        if workload not in mapping:
            raise ValueError(
                f"Unknown workload level: {workload}"
            )

        return mapping[workload]
