"""Machine-readable, descriptive architecture boundaries for Genesis v0.1.

This module contains metadata only. It does not participate in runtime decisions.
"""

LAYER_DATA_INGESTION = "data_ingestion"
LAYER_NORMALIZATION = "normalization"
LAYER_IDENTITY = "robot_identity_profile"
LAYER_ANALYSIS = "analysis"
LAYER_SECURITY = "security_trust"
LAYER_CONTEXT = "analysis_context"
LAYER_MEMORY = "reliability_memory"
LAYER_EVIDENCE = "evidence"
LAYER_INCIDENT = "incident_lifecycle"
LAYER_DECISION = "decision"
LAYER_INTERFACE = "interface_platform"
LAYER_OFFLINE = "offline_training_validation"
LAYER_LEGACY = "legacy_analysis"
LAYER_TEST = "tests"

CURRENT_COMPONENT_LAYERS = {
    # Ingestion and canonical telemetry representation.
    "ros2_telemetry_adapter.py": LAYER_DATA_INGESTION,
    "robot_adapter.py": LAYER_DATA_INGESTION,
    "normalizer.py": LAYER_NORMALIZATION,
    "telemetry.py": LAYER_NORMALIZATION,
    "telemetry_features.py": LAYER_NORMALIZATION,
    "feature_contract.py": LAYER_NORMALIZATION,
    "robot.py": LAYER_IDENTITY,
    "robot_profile.py": LAYER_IDENTITY,
    "history.py": LAYER_DATA_INGESTION,
    # Evidence producers and contextual analysis.
    "observation_quality.py": LAYER_ANALYSIS,
    "observation_security.py": LAYER_SECURITY,
    "telemetry_pattern_engine.py": LAYER_ANALYSIS,
    "reliability_signal.py": LAYER_ANALYSIS,
    "prediction_engine.py": LAYER_ANALYSIS,
    "diagnosis_engine.py": LAYER_ANALYSIS,
    "risk_engine.py": LAYER_ANALYSIS,
    "fleet_baseline.py": LAYER_CONTEXT,
    "comparison_engine.py": LAYER_CONTEXT,
    "baseline_engine.py": LAYER_CONTEXT,
    "pattern_detector.py": LAYER_CONTEXT,
    # Synthesis, lifecycle, and decisions.
    "evidence_synthesis.py": LAYER_EVIDENCE,
    "evidence_engine.py": LAYER_EVIDENCE,
    "evidence_timeline.py": LAYER_EVIDENCE,
    "incident_explanation.py": LAYER_EVIDENCE,
    "incident.py": LAYER_INCIDENT,
    "incident_manager.py": LAYER_INCIDENT,
    "reliability_event.py": LAYER_INCIDENT,
    "reliability_state.py": LAYER_DECISION,
    "reliability_fusion.py": LAYER_DECISION,
    "recommendation_engine.py": LAYER_DECISION,
    "warning_engine.py": LAYER_DECISION,
    "decision_pipeline.py": LAYER_DECISION,
    "reliability_memory.py": LAYER_MEMORY,
    # Public interface and platform/demo entry points.
    "genesis.py": LAYER_INTERFACE,
    "genesis_cli.py": LAYER_INTERFACE,
    "demo_genesis_investigation.py": LAYER_INTERFACE,
    "main.py": LAYER_INTERFACE,
    # Dataset/model development and validation are not the streaming runtime.
    "fleet_simulator.py": LAYER_OFFLINE,
    "dataset_generator.py": LAYER_OFFLINE,
    "label_generator.py": LAYER_OFFLINE,
    "feature_engineering.py": LAYER_OFFLINE,
    "train_model.py": LAYER_OFFLINE,
    "validation_experiment.py": LAYER_OFFLINE,
    "validation_factorial.py": LAYER_OFFLINE,
    "failure_investigation.py": LAYER_OFFLINE,
    "inspect_false_warning.py": LAYER_OFFLINE,
    "inspect_validation_probabilities.py": LAYER_OFFLINE,
    "analyzer.py": LAYER_LEGACY,
}

# Absent components are recorded as planned boundaries, not as current modules.
PLANNED_COMPONENT_BOUNDARIES = {
    "field_test_session.py": {
        "status": "NOT_IMPLEMENTED",
        "layer": "field_test_data_infrastructure",
        "purpose": "Persist field-test session metadata and observations.",
    },
    "field_test_config.py": {
        "status": "NOT_IMPLEMENTED",
        "layer": "field_test_data_infrastructure",
    },
    "field_test_runner.py": {
        "status": "NOT_IMPLEMENTED",
        "layer": "field_test_data_infrastructure",
    },
    "field_test_report.py": {
        "status": "NOT_IMPLEMENTED",
        "layer": "field_test_data_infrastructure",
    },
    "genesis_field_test.py": {
        "status": "NOT_IMPLEMENTED",
        "layer": "field_test_data_infrastructure",
    },
}

# Capability ownership is descriptive and intentionally narrower than file imports.
CAPABILITY_OWNERS = {
    "incident_lifecycle": "incident_manager.py",
    "recommendation_generation": "recommendation_engine.py",
    "evidence_synthesis": "evidence_synthesis.py",
    "public_investigation_api": "genesis.py",
    "robot_control": None,
}

COMPONENT_CAPABILITIES = {
    "ros2_telemetry_adapter.py": frozenset({"data_ingestion", "telemetry_translation"}),
    "telemetry_pattern_engine.py": frozenset({"observable_pattern_description"}),
    "reliability_signal.py": frozenset({"engineering_signal_detection"}),
    "prediction_engine.py": frozenset({"risk_model_inference"}),
    "fleet_baseline.py": frozenset({"peer_context"}),
    "reliability_memory.py": frozenset({"incident_memory_storage", "historical_retrieval"}),
    "evidence_synthesis.py": frozenset({"evidence_synthesis", "security_evidence_synthesis"}),
    "observation_security.py": frozenset({"observation_trust_assessment", "provenance_assessment"}),
    "incident_manager.py": frozenset({"incident_lifecycle"}),
    "recommendation_engine.py": frozenset({"recommendation_generation"}),
    "genesis.py": frozenset({"public_investigation_api", "pipeline_coordination"}),
    "genesis_cli.py": frozenset({"human_presentation", "json_presentation"}),
}

FORBIDDEN_CAPABILITIES = {
    "ros2_telemetry_adapter.py": frozenset({"robot_control", "reliability_decision", "incident_lifecycle"}),
    "telemetry_pattern_engine.py": frozenset({"risk_scoring", "diagnosis", "incident_lifecycle", "recommendation_generation"}),
    "evidence_synthesis.py": frozenset({"reliability_state_transition", "incident_lifecycle", "recommendation_generation"}),
    "observation_security.py": frozenset({"robot_control", "reliability_decision", "incident_lifecycle"}),
    "fleet_baseline.py": frozenset({"reliability_state_transition", "risk_scoring", "incident_lifecycle"}),
    "reliability_memory.py": frozenset({"reliability_decision", "recommendation_generation", "incident_lifecycle"}),
    "genesis_cli.py": frozenset({"business_logic", "reliability_decision", "incident_lifecycle"}),
    "main.py": frozenset({"production_policy_ownership"}),
}

DEPENDENCY_RULES = (
    "data_ingestion may depend on telemetry contracts, never decision or lifecycle layers",
    "normalization produces canonical telemetry/features and does not infer reliability state",
    "analysis components consume observations and emit evidence; they do not own lifecycle",
    "telemetry_pattern_engine does not depend on IncidentManager",
    "evidence_synthesis consumes evidence and does not depend on IncidentManager",
    "FleetBaseline provides peer context and does not set reliability state",
    "ReliabilityMemory stores/retrieves incident knowledge and does not recommend actions",
    "DecisionPipeline coordinates existing components; policy ownership stays with the owning engines",
    "Genesis is the public interface/coordinator; CLI renders returned structured results",
    "ROS2 adapter translates incoming messages and has no robot-control behavior",
    "field-test infrastructure, when implemented, stores session/configuration/run/report data and does not duplicate reasoning",
)

