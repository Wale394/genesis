class RobotProfile:
    def __init__(
            self,
            robot_id, 
            normal_working_temperature,
            abnormal_working_temperature,
            critical_working_temperature,
            normal_idle_temperature,
            abnormal_idle_temperature,
            critical_idle_temperature,
            normal_ambient_temperature,
            abnormal_ambient_temperature,
            critical_ambient_temperature,normal_thermal_rise,
            abnormal_thermal_rise,
            critical_thermal_rise
            ):
        self.robot_id = robot_id
        self.normal_working_temp = normal_working_temperature
        self.abnormal_working_temp = abnormal_working_temperature
        self.critical_working_temp = critical_working_temperature
        self.normal_idle_temp = normal_idle_temperature
        self.abnormal_idle_temp = abnormal_idle_temperature
        self.critical_idle_temp = critical_idle_temperature
        self.normal_ambient_temp = normal_ambient_temperature
        self.abnormal_ambient_temp = abnormal_ambient_temperature
        self.critical_ambient_temp = critical_ambient_temperature
        self.normal_thermal_rise = normal_thermal_rise
        self.abnormal_thermal_rise = abnormal_thermal_rise
        self.critical_thermal_rise = critical_thermal_rise
