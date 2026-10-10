class DiagnosisEngine:

    def __init__(self, diagnosis_model):
        self.diagnosis_model = diagnosis_model
        from feature_contract import DIAGNOSIS_FEATURES

        self.feature_schema = tuple(DIAGNOSIS_FEATURES)
        trained_schema = getattr(diagnosis_model, "feature_names_in_", None)
        self.feature_order = tuple(trained_schema) if trained_schema is not None else self.feature_schema
        if set(self.feature_order) != set(self.feature_schema):
            raise ValueError("Diagnosis model feature schema does not match DIAGNOSIS_FEATURES")

    def diagnose(self, feature_record):

        failure_type = self.predict_failure_type(
            feature_record
        )

        evidence = self.collect_evidence(
            feature_record,
            failure_type
        )

        probable_cause = self.determine_probable_cause(
            feature_record,
            failure_type
        )

        confidence = self.calculate_confidence(
            feature_record,
            failure_type
        )

        return {
            "failure_type": failure_type,
            "confidence": confidence,
            "probable_cause": probable_cause,
            "evidence": evidence
        }

    # ========================================
    # FAILURE TYPE
    # ========================================

    def predict_failure_type(self, feature_record):

        import pandas as pd

        missing = [name for name in self.feature_order if name not in feature_record]
        if missing:
            raise ValueError(f"Missing deployable diagnosis features: {missing}")
        input_data = pd.DataFrame(
            [{name: feature_record[name] for name in self.feature_order}],
            columns=self.feature_order,
        )
        if input_data.isna().any(axis=None):
            raise ValueError("Diagnosis input contains missing deployable feature values")

        prediction = self.diagnosis_model.predict(
            input_data
        )[0]

        return prediction

    # ========================================
    # EVIDENCE
    # ========================================

    def collect_evidence(
        self,
        feature_record,
        failure_type
    ):

        evidence = []

        thermal_rise = feature_record.get(
            "thermal_rise",
            0
        )

        motor_temperature = feature_record.get(
            "motor_temperature",
            0
        )

        temperature_rate_5 = feature_record.get(
            "temperature_rate_5",
            0
        )

        battery_level = feature_record.get(
            "battery_level",
            100
        )

        battery_voltage = feature_record.get(
            "battery_voltage",
            48
        )

        battery_temperature = feature_record.get(
            "battery_temperature",
            0
        )

        voltage_drop = feature_record.get(
            "voltage_drop",
            0
        )

        battery_drop_rate_3 = feature_record.get(
            "battery_drop_rate_3",
            0
        )

        # ------------------------------------
        # THERMAL EVIDENCE
        # ------------------------------------

        if thermal_rise >= 35:

            evidence.append(
                "Critical thermal rise detected."
            )

        elif thermal_rise >= 20:

            evidence.append(
                "Abnormal thermal rise detected."
            )

        if motor_temperature >= 60:

            evidence.append(
                "Motor temperature is elevated."
            )

        if temperature_rate_5 >= 8:

            evidence.append(
                "Motor temperature has increased significantly over recent steps."
            )

        # ------------------------------------
        # BATTERY EVIDENCE
        # ------------------------------------

        if battery_level <= 20:

            evidence.append(
                "Battery level is critically low."
            )

        elif battery_level <= 35:

            evidence.append(
                "Battery level is significantly depleted."
            )

        if battery_voltage < 20:

            evidence.append(
                "Battery voltage is significantly reduced."
            )

        if voltage_drop >= 2:

            evidence.append(
                "Significant battery voltage drop detected."
            )

        if battery_temperature >= 45:

            evidence.append(
                "Battery temperature is elevated."
            )

        if battery_drop_rate_3 >= 5:

            evidence.append(
                "Battery level is declining rapidly."
            )

        # ------------------------------------
        # FAILURE-SPECIFIC FILTERING
        # ------------------------------------

        if failure_type == "thermal":

            thermal_evidence = [
                item for item in evidence
                if (
                    "thermal" in item.lower()
                    or "motor" in item.lower()
                )
            ]

            if thermal_evidence:

                return thermal_evidence

        elif failure_type == "battery":

            battery_evidence = [
                item for item in evidence
                if (
                    "battery" in item.lower()
                )
            ]

            if battery_evidence:

                return battery_evidence

        if not evidence:

            evidence.append(
                "No strong observable evidence identified."
            )

        return evidence

    # ========================================
    # PROBABLE CAUSE
    # ========================================

    def determine_probable_cause(
        self,
        feature_record,
        failure_type
    ):

        workload = feature_record.get(
            "workload",
            "unknown"
        )

        thermal_rise = feature_record.get(
            "thermal_rise",
            0
        )

        battery_level = feature_record.get(
            "battery_level",
            100
        )

        battery_temperature = feature_record.get(
            "battery_temperature",
            0
        )

        voltage_drop = feature_record.get(
            "voltage_drop",
            0
        )

        if failure_type == "thermal":

            if (
                workload == "high"
                and thermal_rise >= 20
            ):

                return (
                    "Possible workload-related "
                    "thermal stress."
                )

            if thermal_rise >= 20:

                return (
                    "Possible abnormal internal "
                    "heating."
                )

            return (
                "Possible thermal instability."
            )

        if failure_type == "battery":

            if (
                battery_temperature >= 45
                and battery_level <= 35
            ):

                return (
                    "Possible battery degradation "
                    "with thermal stress."
                )

            if voltage_drop >= 2:

                return (
                    "Possible battery voltage "
                    "instability."
                )

            if battery_level <= 20:

                return (
                    "Possible battery depletion."
                )

            return (
                "Possible battery degradation."
            )

        return (
            "Cause could not be determined."
        )

    # ========================================
    # CONFIDENCE
    # ========================================

    def calculate_confidence(
        self,
        feature_record,
        failure_type
    ):

        evidence = self.collect_evidence(
            feature_record,
            failure_type
        )

        confidence = 0.50

        confidence += (
            len(evidence) * 0.10
        )

        confidence = min(
            confidence,
            0.95
        )

        return round(
            confidence,
            2
        )
