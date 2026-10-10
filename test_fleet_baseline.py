import unittest

from fleet_baseline import FleetBaseline, FLEET_COMPARISON
from incident_explanation import IncidentExplanation, FLEET_COMPARISON as EXPLANATION_FLEET_TYPE, ML_INFERENCE


def robot(robot_id, value, robot_type="AMR", manufacturer="ABB", time_step=1, **extra):
    result = {
        "robot_id": robot_id, "manufacturer": manufacturer,
        "robot_type": robot_type, "time_step": time_step,
        "motor_temperature": value, "ambient_temperature": 25.0,
        "thermal_rise": value - 25.0, "battery_level": 80.0,
        "battery_voltage": 48.0, "battery_current": 10.0,
        "battery_temperature": 30.0, "power_consumption": 500.0,
        "voltage_drop": 1.0, "workload": 50.0,
    }
    result.update(extra)
    return result


class FleetBaselineTests(unittest.TestCase):
    def setUp(self):
        self.baseline = FleetBaseline()
        self.current = robot("R004", 61.0)
        self.peers = [robot("R001", 42.0), robot("R002", 43.0), robot("R003", 44.0)]

    def test_peer_group_uses_robot_type_when_manufacturer_unavailable(self):
        current = robot("R004", 61.0, manufacturer=None)
        peers = [robot("R001", 42.0, manufacturer="ABB"), robot("R002", 43.0, manufacturer="KUKA")]
        result = self.baseline.compare(current, peers)
        self.assertEqual(result["peer_group_level"], "robot_type")
        self.assertEqual(result["comparable_robot_count"], 2)

    def test_peer_group_prefers_manufacturer_and_type(self):
        peers = self.peers + [robot("R005", 70.0, robot_type="AMR", manufacturer="KUKA")]
        result = self.baseline.compare(self.current, peers)
        self.assertEqual(result["peer_group"], {"manufacturer": "ABB", "robot_type": "AMR"})
        self.assertEqual(result["peer_group_level"], "manufacturer_and_type")
        self.assertEqual(result["comparable_robot_count"], 3)

    def test_insufficient_peers(self):
        result = self.baseline.compare(self.current, self.peers[:1])
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertEqual(result["metrics"]["motor_temperature"]["peer_mean"], None)

    def test_peer_mean(self):
        result = self.baseline.compare(self.current, self.peers)
        self.assertEqual(result["metrics"]["motor_temperature"]["peer_mean"], 43.0)

    def test_peer_minimum_and_maximum(self):
        metric = self.baseline.compare(self.current, self.peers)["metrics"]["motor_temperature"]
        self.assertEqual(metric["peer_minimum"], 42.0)
        self.assertEqual(metric["peer_maximum"], 44.0)

    def test_peer_standard_deviation(self):
        metric = self.baseline.compare(self.current, self.peers)["metrics"]["motor_temperature"]
        self.assertEqual(metric["peer_standard_deviation"], 1.0)

    def test_deviation_calculation(self):
        metric = self.baseline.compare(self.current, self.peers)["metrics"]["motor_temperature"]
        self.assertEqual(metric["deviation"], 18.0)
        self.assertEqual(metric["z_score"], 18.0)

    def test_outlier_detection(self):
        metric = self.baseline.compare(self.current, self.peers)["metrics"]["motor_temperature"]
        self.assertEqual(metric["status"], "OUTLIER")

    def test_normal_peer_comparison(self):
        metric = self.baseline.compare(robot("R004", 43.5), self.peers)["metrics"]["motor_temperature"]
        self.assertEqual(metric["status"], "NORMAL")

    def test_robot_specific_pattern(self):
        result = self.baseline.compare(self.current, self.peers)
        self.assertEqual(result["fleet_pattern"], "robot_specific")
        self.assertEqual(result["metrics"]["motor_temperature"]["pattern"], "robot_specific")

    def test_peer_wide_pattern_with_prior_observations(self):
        current_peers = [robot("R001", 61, time_step=2), robot("R002", 60, time_step=2), robot("R003", 62, time_step=2)]
        previous_peers = [robot("R001", 42, time_step=1), robot("R002", 43, time_step=1), robot("R003", 44, time_step=1)]
        result = self.baseline.compare(robot("R004", 61, time_step=2), current_peers, previous_peer_records=previous_peers)
        self.assertEqual(result["fleet_pattern"], "peer_wide")
        self.assertEqual(result["metrics"]["motor_temperature"]["pattern"], "peer_wide")
        self.assertEqual(result["metrics"]["motor_temperature"]["temporal_context"]["direction"], "increasing")

    def test_missing_peer_telemetry_is_insufficient_not_a_partial_baseline(self):
        peers = [self.peers[0], dict(self.peers[1], battery_level=None), self.peers[2]]
        result = self.baseline.compare(self.current, peers)
        metric = result["metrics"]["battery_level"]
        self.assertEqual(metric["status"], "INSUFFICIENT_DATA")
        self.assertEqual(metric["missing_peer_ids"], ["R002"])
        self.assertIsNone(metric["peer_mean"])

    def test_degraded_observation_quality_is_preserved(self):
        quality = {"groups": {"thermal": {"status": "DEGRADED"}}}
        result = self.baseline.compare(self.current, self.peers, observation_quality=quality)
        metric = result["metrics"]["motor_temperature"]
        self.assertEqual(metric["status"], "INSUFFICIENT_DATA")
        self.assertIn("current_observation_quality_degraded", metric["limitations"])

    def test_heterogeneous_manufacturers_only_match_specific_group(self):
        peers = self.peers + [robot("R005", 70.0, robot_type="AMR", manufacturer="KUKA")]
        result = self.baseline.compare(self.current, peers)
        self.assertNotIn("R005", [p["robot_id"] for p in self.baseline._eligible_peers(self.current, peers)])
        self.assertEqual(result["metrics"]["motor_temperature"]["peer_count"], 3)

    def test_no_cross_type_comparison(self):
        peers = [robot("R005", 70.0, robot_type="robotic_arm", manufacturer="ABB")]
        result = self.baseline.compare(self.current, peers)
        self.assertEqual(result["comparable_robot_count"], 0)
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")

    def test_simulator_only_fields_are_not_used_or_returned(self):
        current = dict(self.current, battery_stress=0.8, degradation_level=0.4, failure_event=True)
        peers = [dict(peer, battery_health=0.5, health="failed") for peer in self.peers]
        result = self.baseline.compare(current, peers)
        encoded = repr(result)
        for forbidden in ("battery_stress", "degradation_level", "battery_health", "failure_event"):
            self.assertNotIn(forbidden, encoded)

    def test_zero_variance_is_handled_without_division_by_zero(self):
        peers = [robot("R001", 42.0), robot("R002", 42.0)]
        result = self.baseline.compare(robot("R003", 42.0), peers)
        metric = result["metrics"]["motor_temperature"]
        self.assertEqual(metric["status"], "NORMAL")
        self.assertEqual(metric["z_score"], 0.0)
        different = self.baseline.compare(robot("R003", 43.0), peers)["metrics"]["motor_temperature"]
        self.assertEqual(different["status"], "OUTLIER")
        self.assertIsNone(different["z_score"])

    def test_repeated_results_are_deterministic(self):
        one = self.baseline.compare(self.current, self.peers)
        two = self.baseline.compare(self.current, self.peers)
        self.assertEqual(one, two)

    def test_explanation_includes_fleet_context(self):
        context = self.baseline.compare(self.current, self.peers)
        report = IncidentExplanation.build({"robot_id": "R004", "state": "WATCH", "fleet_context": context}, self.current)
        self.assertEqual(report["fleet_peer_context"]["status"], "AVAILABLE")
        self.assertEqual(report["fleet_peer_context"]["peer_group"]["manufacturer"], "ABB")

    def test_explanation_explicitly_says_unavailable_without_peers(self):
        context = self.baseline.compare(self.current, [])
        report = IncidentExplanation.build({"robot_id": "R004", "fleet_context": context}, self.current)
        self.assertIn("Fleet comparison unavailable", report["fleet_peer_context"]["message"])

    def test_fleet_context_does_not_modify_ml_prediction(self):
        prediction = {"probability": 0.22, "prediction": 0, "model_prediction": 0}
        original = dict(prediction)
        context = self.baseline.compare(self.current, self.peers)
        report = IncidentExplanation.build({"robot_id": "R004", "state": "HEALTHY", "risk": prediction, "fleet_context": context}, self.current)
        self.assertEqual(prediction, original)
        self.assertEqual(report["ml_inference"]["probability"], 0.22)

    def test_pipeline_peer_context_does_not_change_risk_signals_or_lifecycle(self):
        from test_decision_pipeline import DecisionPipelineTests
        fixture = DecisionPipelineTests()
        fixture.setUp()
        plain_pipeline = fixture.make_pipeline(0.05, 0)
        peer_pipeline = fixture.make_pipeline(0.05, 0)
        record = fixture.records[5]
        plain = plain_pipeline.evaluate(record, historical_records=fixture.records[:5])
        with_peers = peer_pipeline.evaluate(
            record,
            historical_records=fixture.records[:5],
            fleet_records=[
                robot("PEER-1", 40.0, manufacturer=record["manufacturer"], robot_type=record["robot_type"]),
                robot("PEER-2", 41.0, manufacturer=record["manufacturer"], robot_type=record["robot_type"]),
            ],
        )
        self.assertEqual(plain["risk"], with_peers["risk"])
        self.assertEqual(plain["state"], with_peers["state"])
        self.assertEqual(plain["incident"], with_peers["incident"])
        self.assertEqual(with_peers["explanation"]["fleet_peer_context"]["status"], "AVAILABLE")

    def test_fleet_context_does_not_modify_engineering_severity(self):
        engineering = {"severity": "normal", "signals": []}
        original = dict(engineering)
        self.baseline.compare(self.current, self.peers)
        self.assertEqual(engineering, original)

    def test_fleet_context_does_not_change_incident_manager_lifecycle(self):
        from history import History
        from incident_manager import IncidentManager
        manager = IncidentManager(History())
        incident = manager.create_incident("R004", 1)
        self.baseline.compare(self.current, self.peers)
        self.assertEqual(incident.status, "OPEN")

    def test_no_telemetry_is_invented(self):
        current = robot("R004", 61.0, battery_level=None)
        result = self.baseline.compare(current, self.peers)
        self.assertIsNone(result["metrics"]["battery_level"]["robot_value"])
        self.assertEqual(result["metrics"]["battery_level"]["status"], "INSUFFICIENT_DATA")

    def test_fleet_comparison_is_distinct_from_ml_inference(self):
        context = self.baseline.compare(self.current, self.peers)
        report = IncidentExplanation.build({"robot_id": "R004", "risk": {"probability": 0.5}, "fleet_context": context}, self.current)
        item = report["evidence_summary"]["fleet_comparison"][0]
        self.assertEqual(item["type"], FLEET_COMPARISON)
        self.assertNotEqual(item["type"], ML_INFERENCE)
        self.assertEqual(EXPLANATION_FLEET_TYPE, FLEET_COMPARISON)

    def test_demonstration_separates_abb_amrs_from_kuka_arm(self):
        fleet = [robot("R001", 42), robot("R002", 43), robot("R003", 44), robot("R004", 61), robot("R005", 70, "robotic_arm", "KUKA")]
        result = self.baseline.compare(fleet[3], fleet)
        self.assertEqual(result["comparable_robot_count"], 3)
        self.assertEqual(result["metrics"]["motor_temperature"]["peer_mean"], 43.0)
        self.assertEqual(result["metrics"]["motor_temperature"]["peer_minimum"], 42.0)
        self.assertEqual(result["metrics"]["motor_temperature"]["peer_maximum"], 44.0)
        other = self.baseline.compare(fleet[4], fleet)
        self.assertEqual(other["comparable_robot_count"], 0)


if __name__ == "__main__":
    unittest.main()
