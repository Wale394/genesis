import unittest

from architecture_contract import (
    CAPABILITY_OWNERS,
    COMPONENT_CAPABILITIES,
    CURRENT_COMPONENT_LAYERS,
    FORBIDDEN_CAPABILITIES,
    LAYER_ANALYSIS,
    LAYER_CONTEXT,
    LAYER_DATA_INGESTION,
    LAYER_DECISION,
    LAYER_EVIDENCE,
    LAYER_INCIDENT,
    LAYER_INTERFACE,
    LAYER_MEMORY,
    PLANNED_COMPONENT_BOUNDARIES,
)


class ArchitectureContractTests(unittest.TestCase):
    def test_ros2_adapter_is_ingestion_and_not_control(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["ros2_telemetry_adapter.py"], LAYER_DATA_INGESTION)
        self.assertIn("data_ingestion", COMPONENT_CAPABILITIES["ros2_telemetry_adapter.py"])
        self.assertIn("robot_control", FORBIDDEN_CAPABILITIES["ros2_telemetry_adapter.py"])

    def test_field_test_session_is_future_data_infrastructure(self):
        self.assertNotIn("field_test_session.py", CURRENT_COMPONENT_LAYERS)
        item = PLANNED_COMPONENT_BOUNDARIES["field_test_session.py"]
        self.assertEqual(item["status"], "NOT_IMPLEMENTED")
        self.assertEqual(item["layer"], "field_test_data_infrastructure")

    def test_pattern_engine_is_analysis_only_without_lifecycle_ownership(self):
        key = "telemetry_pattern_engine.py"
        self.assertEqual(CURRENT_COMPONENT_LAYERS[key], LAYER_ANALYSIS)
        self.assertIn("incident_lifecycle", FORBIDDEN_CAPABILITIES[key])
        self.assertNotEqual(CAPABILITY_OWNERS["incident_lifecycle"], key)

    def test_reliability_signal_is_analysis(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["reliability_signal.py"], LAYER_ANALYSIS)

    def test_prediction_engine_is_analysis(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["prediction_engine.py"], LAYER_ANALYSIS)

    def test_fleet_baseline_is_context(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["fleet_baseline.py"], LAYER_CONTEXT)
        self.assertIn("reliability_state_transition", FORBIDDEN_CAPABILITIES["fleet_baseline.py"])

    def test_reliability_memory_is_memory(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["reliability_memory.py"], LAYER_MEMORY)

    def test_evidence_synthesis_is_evidence_without_lifecycle_ownership(self):
        key = "evidence_synthesis.py"
        self.assertEqual(CURRENT_COMPONENT_LAYERS[key], LAYER_EVIDENCE)
        self.assertIn("incident_lifecycle", FORBIDDEN_CAPABILITIES[key])
        self.assertNotEqual(CAPABILITY_OWNERS["incident_lifecycle"], key)

    def test_incident_manager_owns_lifecycle(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["incident_manager.py"], LAYER_INCIDENT)
        self.assertEqual(CAPABILITY_OWNERS["incident_lifecycle"], "incident_manager.py")

    def test_recommendation_engine_owns_recommendation_generation(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["recommendation_engine.py"], LAYER_DECISION)
        self.assertEqual(CAPABILITY_OWNERS["recommendation_generation"], "recommendation_engine.py")

    def test_genesis_is_public_interface(self):
        self.assertEqual(CURRENT_COMPONENT_LAYERS["genesis.py"], LAYER_INTERFACE)
        self.assertIn("public_investigation_api", COMPONENT_CAPABILITIES["genesis.py"])

    def test_cli_is_interface_only(self):
        key = "genesis_cli.py"
        self.assertEqual(CURRENT_COMPONENT_LAYERS[key], LAYER_INTERFACE)
        self.assertIn("business_logic", FORBIDDEN_CAPABILITIES[key])

    def test_pattern_engine_has_no_diagnosis_or_causal_authority(self):
        forbidden = FORBIDDEN_CAPABILITIES["telemetry_pattern_engine.py"]
        self.assertIn("diagnosis", forbidden)
        self.assertIn("risk_scoring", forbidden)

    def test_no_control_capability_owner_exists(self):
        self.assertIsNone(CAPABILITY_OWNERS["robot_control"])


if __name__ == "__main__":
    unittest.main()
