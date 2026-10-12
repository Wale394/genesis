"""Small deterministic adversarial checks for Genesis evidence boundaries.

Findings below are deliberately test/report metadata, not production rules.
Any model probabilities in A-C come from explicit test doubles only.
"""

import csv
from pathlib import Path
import unittest

from demo_genesis_investigation import demo_historical_incidents
from evidence_synthesis import (
    ENGINEERING_SIGNAL,
    FLEET_COMPARISON,
    HISTORICAL_COMPARISON,
    ML_INFERENCE,
)
from genesis import Genesis
from recommendation_engine import RecommendationEngine
from reliability_state import ReliabilityState
from telemetry_features import TelemetryFeatureBuilder

from test_genesis_scenarios import (
    DeterministicZeroRiskTestModel,
    battery_telemetry,
    build_test_pipeline,
    healthy_telemetry,
    peer_record,
)


# Machine-readable summary of the assertions and findings expected from this
# milestone. Runtime values are verified by the tests and included in unittest
# diagnostics when an assertion fails.
ADVERSARIAL_FINDINGS = [
    {"scenario": "A", "expected_behavior": "critical engineering takes existing fusion precedence while low ML remains visible", "observed_behavior": "critical motor signal overrides low test-double ML; both source evidences remain distinct", "classification": "TEST", "severity": "high", "production_bug": False, "future_ml_data_work": False},
    {"scenario": "B", "expected_behavior": "high ML remains ML inference and is not presented as observed engineering evidence", "observed_behavior": "0.80 test-double risk produces WARNING; engineering evidence remains empty", "classification": "TEST", "severity": "medium", "production_bug": False, "future_ml_data_work": False},
    {"scenario": "C", "expected_behavior": "degraded evidence prevents an unsupported healthy conclusion", "observed_behavior": "low test-double probability is retained while degraded thermal quality limits state to WATCH", "classification": "TEST", "severity": "high", "production_bug": False, "future_ml_data_work": False},
    {"scenario": "D", "expected_behavior": "similar history is contextual and current signals remain authoritative", "observed_behavior": "thermal incident matches by explicit memory context; current battery signal and generic current recommendation remain", "classification": "TEST", "severity": "medium", "production_bug": False, "future_ml_data_work": False},
    {"scenario": "E", "expected_behavior": "peer-normal context and own-history deviation remain separate", "observed_behavior": "fleet temperature is NORMAL while ComparisonEngine reports positive deviation from own history", "classification": "TEST", "severity": "medium", "production_bug": False, "future_ml_data_work": False},
    {"scenario": "F", "expected_behavior": "peer outlier context does not itself decide state or lifecycle", "observed_behavior": "fleet status changes from OUTLIER to NORMAL with peer set; state, engineering signals, and incident status do not change", "classification": "TEST", "severity": "medium", "production_bug": False, "future_ml_data_work": False},
    {"scenario": "G", "expected_behavior": "record boundary perturbations without claiming model behavior when no artifact is fitted", "observed_behavior": "perturbation matrix returns no ML probability because no fitted model is available", "classification": "TEST", "severity": "medium", "production_bug": False, "future_ml_data_work": True},
    {"scenario": "H", "expected_behavior": "measure available observed signal lead time to a recorded failure", "observed_behavior": "R006 thermal failure occurs at t=52; the test records the first engineering signal and only asserts measured lead when it precedes failure", "classification": "TEST", "severity": "medium", "production_bug": False, "future_ml_data_work": True},
]
OBSERVED_PERTURBATIONS = []


class FixedPredictionTestDouble:
    """Controlled inference for architecture tests; never a fitted model."""

    def __init__(self, probability, prediction):
        self.probability = probability
        self.prediction = prediction

    def predict(self, _feature_record):
        return {"probability": self.probability, "prediction": self.prediction}


def run_pipeline(records, predictor):
    builder = TelemetryFeatureBuilder()
    pipeline = build_test_pipeline(predictor)
    output = []
    history = []
    previous_state = None
    for record in records:
        feature = builder.build({
            "identity": {key: record.get(key) for key in ("robot_id", "manufacturer", "robot_type")},
            "telemetry": {key: value for key, value in record.items() if key not in ("robot_id", "manufacturer", "robot_type")},
        })
        result = pipeline.evaluate(feature, previous_state, history)
        output.append(result)
        history.append(feature)
        previous_state = result["state"]
    return output


def rapidly_rising_thermal_records():
    records = healthy_telemetry(count=8)
    temps = [42.0, 43.0, 45.0, 48.0, 52.0, 56.0, 59.0, 61.0]
    for record, temperature in zip(records, temps):
        record["motor_temperature"] = temperature
        record["ambient_temperature"] = 25.0
    return records


class GenesisAdversarialTests(unittest.TestCase):
    def test_a_low_ml_plus_critical_engineering_preserves_both_and_uses_fusion(self):
        result = run_pipeline(
            rapidly_rising_thermal_records(), FixedPredictionTestDouble(0.05, 0)
        )[-1]
        signals = {item["signal"] for item in result["risk"]["engineering"]["signals"]}
        self.assertIn("critical_motor_temperature", signals)
        self.assertEqual(result["risk"]["probability"], 0.05)
        self.assertEqual(result["risk"]["model_prediction"], 0)
        self.assertEqual(result["risk"]["prediction"], 1)
        self.assertEqual(result["state"], ReliabilityState.CRITICAL)
        self.assertIsNone(result["diagnosis"])
        synth = result["evidence_synthesis"]
        self.assertTrue(any(e["evidence_type"] == ENGINEERING_SIGNAL for e in synth["engineering_evidence"]))
        self.assertTrue(any(e["evidence_type"] == ML_INFERENCE for e in synth["ml_evidence"]))
        self.assertNotIn("healthy", " ".join(synth["summary"]["what_the_model_says"]).lower())
        self.assertEqual(
            result["recommendation"],
            RecommendationEngine().recommend(
                result["risk"], result["diagnosis"], result["state"],
                observation_quality=result["observation_quality"],
            ),
        )

    def test_b_high_ml_without_engineering_signal_remains_prediction_evidence(self):
        result = run_pipeline(
            healthy_telemetry(), FixedPredictionTestDouble(0.80, 1)
        )[-1]
        self.assertEqual(result["risk"]["engineering"]["signals"], [])
        self.assertEqual(result["risk"]["probability"], 0.80)
        self.assertEqual(result["state"], ReliabilityState.WARNING)
        synthesis = result["evidence_synthesis"]
        ml = [item for item in synthesis["ml_evidence"] if item["evidence_id"] == "ML-risk"]
        self.assertTrue(ml)
        self.assertEqual(ml[0]["evidence_type"], ML_INFERENCE)
        self.assertEqual(synthesis["engineering_evidence"], [])
        self.assertIsNone(result["diagnosis"])

    def test_c_degraded_quality_and_low_ml_does_not_claim_healthy(self):
        records = healthy_telemetry(count=8)
        for record in records:
            record["motor_temperature"] = 42.0
        result = run_pipeline(records, FixedPredictionTestDouble(0.05, 0))[-1]
        self.assertEqual(result["observation_quality"]["groups"]["thermal"]["status"], "DEGRADED")
        self.assertEqual(result["risk"]["probability"], 0.05)
        self.assertEqual(result["state"], ReliabilityState.WATCH)
        self.assertIsNone(result["diagnosis"])
        self.assertEqual(result["evidence_synthesis"]["observation_quality"]["thermal"], "DEGRADED")

    def test_d_similar_history_is_context_not_current_cause_or_recommendation(self):
        result = Genesis(historical_incidents=demo_historical_incidents()).investigate(battery_telemetry())
        current = {item["signal"] for item in result["engineering_signals"]["signals"]}
        self.assertIn("critical_battery_level", current)
        self.assertNotIn("critical_motor_temperature", current)
        history = result["evidence_synthesis"]["historical_evidence"]
        self.assertTrue(any(item["evidence_type"] == HISTORICAL_COMPARISON for item in history))
        self.assertTrue(all(item["source"] == "ReliabilityMemory" or item["source"] in ("ComparisonEngine", "BaselineEngine") for item in history))
        self.assertTrue(any("matched on" in item["statement"] for item in history))
        self.assertFalse(any("caused" in item["statement"].lower() for item in history))
        self.assertNotEqual(result["recommendation"]["recommendation"], "Inspect motor assembly.")
        self.assertIsNone(result["ml_inference"]["diagnosis"])

    def test_e_fleet_normal_and_own_history_deviation_remain_distinct(self):
        records = healthy_telemetry(count=6)
        temps = [45.0, 46.0, 47.0, 48.0, 49.0, 50.0]
        for record, temperature in zip(records, temps):
            record["motor_temperature"] = temperature
        peers = [peer_record(f"P{i}", 50 + i * 0.1, 6) for i in range(3)]
        result = Genesis(peer_records=peers).investigate(records)
        fleet_motor = result["fleet_context"]["metrics"]["motor_temperature"]
        self.assertEqual(fleet_motor["status"], "NORMAL")
        synthesis = result["evidence_synthesis"]
        self.assertTrue(any(item["evidence_type"] == FLEET_COMPARISON for item in synthesis["fleet_evidence"]))
        self.assertTrue(any(item["evidence_type"] == HISTORICAL_COMPARISON for item in synthesis["historical_evidence"]))
        own_history = next(item for item in synthesis["historical_evidence"] if item["source"] == "ComparisonEngine" and item["supporting_data"].get("metric") == "temperature_difference")
        self.assertGreater(own_history["supporting_data"]["value"], 0)

    def test_f_fleet_outlier_does_not_change_risk_state_or_incident(self):
        own = healthy_telemetry(count=6)
        for record, temp in zip(own, [59.0, 59.3, 59.6, 60.0, 60.4, 61.0]):
            record["motor_temperature"] = temp
        low_peers = [peer_record(f"P{i}", 42 + i, 6) for i in range(3)]
        similar_peers = [peer_record(f"P{i}", 60.8 + i * 0.2, 6) for i in range(3)]
        outlier = Genesis(peer_records=low_peers).investigate(own)
        contextual = Genesis(peer_records=similar_peers).investigate(own)
        self.assertEqual(outlier["fleet_context"]["metrics"]["motor_temperature"]["status"], "OUTLIER")
        self.assertEqual(contextual["fleet_context"]["metrics"]["motor_temperature"]["status"], "NORMAL")
        own_history = next(item for item in outlier["evidence_synthesis"]["historical_evidence"] if item["source"] == "ComparisonEngine" and item["supporting_data"].get("metric") == "temperature_difference")
        self.assertLess(abs(own_history["supporting_data"]["value"]), 2.0)
        self.assertEqual(outlier["reliability_state"], contextual["reliability_state"])
        self.assertEqual(outlier["engineering_signals"], contextual["engineering_signals"])
        self.assertEqual(outlier["incident"]["status"], contextual["incident"]["status"])

    def test_g_record_existing_feature_boundary_perturbations_without_model_claim(self):
        # There is no fitted inference artifact wired in this checkout. These
        # cases record observable architecture response, not RF probabilities.
        perturbations = [
            ("motor_temperature", 59.9), ("motor_temperature", 60.0),
            ("thermal_rise", 34.9), ("thermal_rise", 35.0),
            ("battery_level", 5.1), ("battery_level", 5.0),
            ("battery_voltage", 39.9), ("battery_voltage", 40.0),
            ("battery_current", 39.9), ("battery_current", 40.0),
            ("power_consumption", 1000.0), ("workload", 85.0),
        ]
        findings = []
        for field, value in perturbations:
            records = healthy_telemetry(count=6)
            records[-1][field] = value
            result = Genesis().investigate(records)
            findings.append({
                "field": field,
                "input_value": value,
                "probability": result["ml_inference"]["probability"],
                "prediction_available": result["ml_inference"]["prediction_available"],
                "engineering_signals": [s["signal"] for s in result["engineering_signals"]["signals"]],
                "observation_quality": result["observation_quality"]["status"],
                "state": result["reliability_state"]["current"],
            })
        OBSERVED_PERTURBATIONS[:] = findings
        self.assertEqual(len(findings), len(perturbations))
        self.assertTrue(all(item["probability"] is None for item in findings))
        self.assertTrue(all(not item["prediction_available"] for item in findings))

    def test_h_existing_failure_trajectory_records_actual_observed_lead_time(self):
        data_path = Path(__file__).parent / "data" / "raw_dataset_v2.csv"
        if not data_path.is_file():
            self.skipTest(
                "Optional local validation dataset is not included in the public release."
            )
        with data_path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        candidates = {}
        for row in rows:
            if row.get("robot_id") != "R006":
                continue
            candidates.setdefault(row["robot_id"], []).append(row)
        trajectory = sorted(candidates.get("R006", []), key=lambda item: int(item["time_step"]))
        self.assertTrue(any(row.get("failure_event", "").lower() == "true" for row in trajectory))
        builder = TelemetryFeatureBuilder()
        pipeline = build_test_pipeline(None)
        history = []
        previous_state = None
        observed_signal_step = None
        failure_step = None
        for row in trajectory:
            telemetry = {}
            for key in ("motor_temperature", "ambient_temperature", "workload", "battery_level", "battery_voltage", "battery_current", "battery_temperature", "power_consumption", "voltage_drop", "time_step"):
                try:
                    telemetry[key] = float(row[key]) if key != "time_step" else int(row[key])
                except (TypeError, ValueError):
                    telemetry[key] = None
            feature = builder.build({
                "identity": {key: row.get(key) for key in ("robot_id", "manufacturer", "robot_type")},
                "telemetry": telemetry,
            })
            feature["failure_event"] = row.get("failure_event", "").lower() == "true"
            feature["failure_type"] = row.get("failure_type")
            result = pipeline.evaluate(feature, previous_state, history)
            signals = result["risk"]["engineering"]["signals"]
            if signals and observed_signal_step is None:
                observed_signal_step = int(row["time_step"])
            if feature["failure_event"]:
                failure_step = int(row["time_step"])
                break
            history.append(feature)
            previous_state = result["state"]
        self.assertIsNotNone(failure_step)
        # The dataset contains a failure; no lead time is asserted unless a
        # recorded engineering signal precedes it.
        if observed_signal_step is not None:
            self.assertLessEqual(observed_signal_step, failure_step)
            lead = failure_step - observed_signal_step
            ADVERSARIAL_FINDINGS[-1]["observed_behavior"] = (
                f"R006 failure at t={failure_step}; first engineering signal at "
                f"t={observed_signal_step}; observed lead={lead} step(s)."
            )
        else:
            ADVERSARIAL_FINDINGS[-1]["observed_behavior"] = (
                f"R006 failure at t={failure_step}; no pre-failure engineering signal was observed."
            )


if __name__ == "__main__":
    unittest.main()

class GenesisSecurityIntegrationTests(unittest.TestCase):
    def test_public_result_exposes_security_assessment(self):
        genesis = Genesis()
        result = genesis.investigate({
            "identity": {"robot_id": "RSEC-001"},
            "telemetry": {
                "time_step": 1,
                "motor_temperature": 40.0,
                "ambient_temperature": 25.0,
                "battery_level": 90.0,
                "battery_voltage": 48.0,
                "battery_current": 10.0,
                "battery_temperature": 30.0,
                "workload": 20.0,
            },
            "source_metadata": {
                "source_id": "robot:RSEC-001",
                "source_type": "simulator",
            },
        })
        security = result["observation_security"]
        self.assertEqual(security["source"]["source_id"], "robot:RSEC-001")
        self.assertEqual(security["freshness"], "TRUSTED")
        self.assertEqual(security["status"], "DEGRADED")
        self.assertIn("security_evidence", result["evidence_synthesis"])

    def test_verified_metadata_does_not_override_runtime_ordering(self):
        genesis = Genesis()
        genesis.investigate({
            "identity": {"robot_id": "RSEC-002"},
            "telemetry": {"time_step": 2, "motor_temperature": 40.0},
            "source_metadata": {
                "authentication": "verified",
                "integrity": "verified",
                "authorization": "verified",
            },
        })
        with self.assertRaises(ValueError):
            genesis.investigate({
                "identity": {"robot_id": "RSEC-002"},
                "telemetry": {"time_step": 2, "motor_temperature": 41.0},
                "source_metadata": {
                    "authentication": "verified",
                    "integrity": "verified",
                    "authorization": "verified",
                },
            })
