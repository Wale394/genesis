import math
from numbers import Real

from observation_quality import AVAILABLE


class EvidenceEngine:

    @staticmethod
    def _display_value(value, precision=2):
        if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value)):
            return f"{float(value):.{precision}f}"
        return str(value)

    def collect_telemetry_evidence(self, feature_record):
        evidence = []

        motor_temperature = feature_record.get("motor_temperature")
        thermal_rise = feature_record.get("thermal_rise")
        temperature_change = feature_record.get("temperature_change")
        workload = feature_record.get("workload")
        battery_level = feature_record.get("battery_level")

        if motor_temperature is not None:
            evidence.append({
                "source": "telemetry",
                "field": "motor_temperature",
                "value": motor_temperature,
                "unit": "C",
                "evidence_type": "observation",
                "description": f"Motor temperature is {self._display_value(motor_temperature)}°C."
            })

        if thermal_rise is not None:
            evidence.append({
                "source": "telemetry",
                "field": "thermal_rise",
                "value": thermal_rise,
                "unit": "C",
                "evidence_type": "observation",
                "description": f"Thermal rise is {self._display_value(thermal_rise)}°C."
            })

        if temperature_change is not None:
            evidence.append({
                "source": "telemetry",
                "field": "temperature_change",
                "value": temperature_change,
                "unit": "C",
                "evidence_type": "observation",
                "description": f"Motor temperature changed by {self._display_value(temperature_change)}°C."
            })

        if workload is not None:
            evidence.append({
                "source": "telemetry",
                "field": "workload",
                "value": workload,
                "evidence_type": "observation",
                "description": f"Current workload is {workload}."
            })

        if battery_level is not None:
            evidence.append({
                "source": "telemetry",
                "field": "battery_level",
                "value": battery_level,
                "unit": "%",
                "evidence_type": "observation",
                "description": f"Battery level is {self._display_value(battery_level, 1)}%."
            })

        return evidence

    def build_evidence_summary(
        self,
        feature_record,
        risk_result=None,
        observation_quality=None,
    ):
        evidence = self.collect_telemetry_evidence(feature_record)

        if observation_quality is not None:
            field_groups = observation_quality.get("field_groups", {})
            for item in evidence:
                scope = field_groups.get(item["field"], {
                    "groups": [],
                    "status": observation_quality.get("status", "UNAVAILABLE"),
                })
                item["quality_scope"] = scope["groups"]
                item["quality_status"] = scope["status"]
                item["usable"] = scope["status"] == AVAILABLE

        summary = {
            "count": len(evidence),
            "items": evidence
        }
        if observation_quality is not None:
            prediction = (risk_result or {}).get("prediction")
            summary["observation_quality"] = observation_quality
            summary["evidence_scope"] = {
                field: {
                    "groups": details.get("groups", []),
                    "status": details.get("status"),
                    "usable": details.get("status") == AVAILABLE,
                }
                for field, details in (observation_quality.get("field_groups") or {}).items()
            }
            summary["inference_transparency"] = {
                "prediction_probability": (risk_result or {}).get("probability"),
                "predicted_risk": (risk_result or {}).get("fused_risk") or (
                    "failure" if prediction == 1 else
                    "no_failure" if prediction == 0 else "unavailable"
                ),
                "model_prediction": (risk_result or {}).get("model_prediction", prediction),
                "operational_prediction": prediction,
                "prediction_available": bool((risk_result or {}).get("prediction_available", prediction is not None)),
                "observation_quality": observation_quality.get("status"),
                "thermal_evidence_quality": observation_quality["groups"]["thermal"]["status"],
                "battery_evidence_quality": observation_quality["groups"]["battery"]["status"],
                "workload_evidence_quality": observation_quality["groups"]["workload"]["status"],
                "major_signal_group_limited": observation_quality["any_major_group_limited"],
            }
        return summary
