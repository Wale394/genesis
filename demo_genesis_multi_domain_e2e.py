"""Deterministic end-to-end Genesis demo across heterogeneous industries.

This demo is intentionally thin: adapters and fleet registration feed the
existing Genesis evidence/review/state/investigation/memory contracts.
"""

from dataclasses import replace
from typing import Any, Dict, List

from domain_adapter import (
    DomainAdapterRegistry,
    EnergyInfrastructureAdapter,
    IndustrialEquipmentAdapter,
    RoboticsAdapter,
)
from fleet_registry import AssetFleetRegistry
from genesis_system.core.context_compatibility import (
    CompatibilityStatus,
    ContextComparison,
    ContextRelationship,
    ContextCompatibilityEvaluator,
)
from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.evidence_review import EvidenceReviewEngine
from genesis_system.core.investigation import InvestigationPlanner
from genesis_system.core.investigation_memory import (
    InvestigationFinding,
    InvestigationFindingStatus,
    InvestigationOutcome,
)
from genesis_system.core.reliability_memory import ReliabilityMemory
from genesis_system.core.reliability_memory_retrieval import (
    MemoryQuery,
    ReliabilityMemoryRetriever,
)
from genesis_system.core.reliability_state import ReliabilityLevel, ReliabilityStateEvaluator


ADAPTER_REGISTRY = DomainAdapterRegistry()
ADAPTER_REGISTRY.register("robotics", RoboticsAdapter())
ADAPTER_REGISTRY.register("energy_infrastructure", EnergyInfrastructureAdapter())
ADAPTER_REGISTRY.register("industrial_equipment", IndustrialEquipmentAdapter())


ASSETS = [
    {"asset_id": "R004", "domain": "robotics", "asset_type": "AMR", "manufacturer": "Demo Robotics", "model": "AMR-Y", "site_id": "WAREHOUSE-B", "timestamp": 1, "signals": {"motor_temperature": 58, "battery_voltage": 48, "velocity": 1.0}, "source": "sim.robot.r004"},
    {"asset_id": "E001", "domain": "energy_infrastructure", "asset_type": "transformer", "manufacturer": "Grid Systems", "model": "TX-100", "site_id": "ENERGY-SITE-A", "timestamp": 1, "signals": {"oil_temperature": 86, "load_percent": 78, "voltage": 22500}, "source": "sim.energy.e001"},
    {"asset_id": "I001", "domain": "industrial_equipment", "asset_type": "compressor", "manufacturer": "Industrial Systems", "model": "CMP-20", "site_id": "FACTORY-A", "timestamp": 1, "signals": {"bearing_temperature": 71, "vibration": 4.8, "pressure": 8.2}, "source": "sim.industry.i001"},
]


def build_registry() -> AssetFleetRegistry:
    registry = AssetFleetRegistry()
    for payload in ASSETS:
        registry.ingest(ADAPTER_REGISTRY.get(payload["domain"]).normalize(payload))
    return registry


def _initial_evidence(asset_id: str, domain: str) -> List[Evidence]:
    signal = {
        "robotics": "motor_temperature",
        "energy_infrastructure": "oil_temperature",
        "industrial_equipment": "bearing_temperature",
    }[domain]
    return [
        Evidence(
            category=EvidenceCategory.DEVIATION,
            name="domain_signal_deviation",
            value="above_expected_behavior",
            source=f"telemetry.{asset_id}",
            metadata={"id": f"{asset_id}-deviation", "signal": signal, "stance": "SUPPORTS"},
        ),
        Evidence(
            category=EvidenceCategory.TEMPORAL,
            name="persistent_behavior",
            value="repeated_observations",
            source=f"telemetry.{asset_id}",
            metadata={"id": f"{asset_id}-temporal", "signal": signal, "stance": "SUPPORTS"},
        ),
    ]


def _robot_historical_memory() -> ReliabilityMemory:
    memory = ReliabilityMemory()
    outcome = InvestigationOutcome(
        investigation_id="INV-HIST-R001",
        status="VALIDATED",
        findings=[
            InvestigationFinding(
                finding_id="F-HIST-R001",
                statement="Motor thermal behavior was a validated reliability concern in the historical case.",
                status=InvestigationFindingStatus.VALIDATED,
                evidence_refs=["hist-temperature", "hist-context"],
                context={
                    "robot_type": "AMR",
                    "manufacturer": "Demo Robotics",
                    "signals": ["motor_temperature"],
                    "motor_model": "AMR-X",
                },
                provenance={"source": "historical-demo-case", "validation": "independent_test"},
            )
        ],
        new_evidence=[],
    )
    memory.store_investigation(outcome)
    return memory


def _robot_compatibility() -> Dict[str, Any]:
    assessment = ContextCompatibilityEvaluator().assess(
        historical_finding_id="F-HIST-R001",
        current_case_id="R004-case",
        comparisons=[
            ContextComparison("robot_type", "AMR", "AMR", ContextRelationship.SAME, material=True),
            ContextComparison("manufacturer", "Demo Robotics", "Demo Robotics", ContextRelationship.SAME, material=True),
            ContextComparison("motor_model", "AMR-X", "UNKNOWN", ContextRelationship.UNKNOWN, material=True),
            ContextComparison("site", "WAREHOUSE-A", "WAREHOUSE-B", ContextRelationship.DIFFERENT, material=False),
        ],
    )
    return assessment.to_dict()


def _investigation_evidence(asset_id: str) -> List[Evidence]:
    return [
        Evidence(
            category=EvidenceCategory.CONTEXT,
            name="motor_model_identified",
            value="AMR-Y",
            source=f"investigation.{asset_id}.asset_record",
            metadata={"id": f"{asset_id}-context", "signal": "motor_model", "stance": "SUPPORTS"},
        ),
        Evidence(
            category=EvidenceCategory.CROSS_SIGNAL,
            name="electrical_behavior_correlated",
            value="current_rise_observed",
            source=f"investigation.{asset_id}.current_sensor",
            metadata={"id": f"{asset_id}-cross-signal", "signal": "motor_current", "stance": "SUPPORTS"},
        ),
    ]


def run_demo() -> Dict[str, Any]:
    registry = build_registry()
    review_engine = EvidenceReviewEngine()
    state_engine = ReliabilityStateEvaluator()
    planner = InvestigationPlanner()

    results: List[Dict[str, Any]] = []
    for asset in registry.snapshot().assets:
        initial = _initial_evidence(asset.asset_id, asset.domain)
        initial_review = review_engine.review(initial)
        initial_state = state_engine.evaluate(initial, evidence_review=initial_review)
        investigation_plan = planner.plan(initial, initial_review)

        record: Dict[str, Any] = {
            "asset_id": asset.asset_id,
            "domain": asset.domain,
            "asset_type": asset.asset_type,
            "initial": {
                "state": initial_state.to_dict(),
                "evidence_review": initial_review.to_dict(),
                "investigation": investigation_plan.to_dict(),
            },
        }

        if asset.asset_id == "R004":
            memory = _robot_historical_memory()
            retrieval = ReliabilityMemoryRetriever(memory).retrieve(
                MemoryQuery(
                    robot_type="AMR",
                    manufacturer="Demo Robotics",
                    signals=["motor_temperature"],
                )
            )
            compatibility = _robot_compatibility()
            if compatibility["investigation_required"] and not investigation_plan.required:
                investigation_plan = replace(
                    investigation_plan,
                    required=True,
                    reasons=list(investigation_plan.reasons) + [compatibility["reason"]],
                    actions=list(investigation_plan.actions) + [
                        "Resolve material context uncertainty before reusing the historical finding."
                    ],
                )
            record["initial"]["investigation"] = investigation_plan.to_dict()
            new_evidence = _investigation_evidence("R004")
            reassessment_evidence = initial + new_evidence
            reassessment_review = review_engine.review(reassessment_evidence)
            reassessment_state = state_engine.evaluate(
                reassessment_evidence,
                previous_level=initial_state.level,
                evidence_review=reassessment_review,
            )
            finding = InvestigationFinding(
                finding_id="F-R004-DEMO",
                statement="R004 has a validated reliability concern; the evidence supports abnormal thermal/electrical behavior, but does not establish a specific failure cause.",
                status=InvestigationFindingStatus.VALIDATED,
                evidence_refs=["R004-deviation", "R004-temporal", "R004-context", "R004-cross-signal"],
                context={"asset_id": "R004", "finding_scope": "reliability_concern"},
                limitations=["The demo does not establish component failure or root cause."],
            )
            outcome = InvestigationOutcome(
                investigation_id="INV-R004-DEMO",
                status="VALIDATED_FINDING",
                findings=[finding],
                new_evidence=new_evidence,
                new_evidence_refs=["R004-context", "R004-cross-signal"],
            )
            memory.store_investigation(outcome)
            record["historical_memory"] = retrieval
            record["context_compatibility"] = compatibility
            record["reassessment"] = {
                "new_evidence": [item.to_dict() for item in new_evidence],
                "evidence_review": reassessment_review.to_dict(),
                "state": reassessment_state.to_dict(),
                "finding": finding.to_dict(),
            }
        elif asset.asset_id == "E001":
            new_evidence = [Evidence(
                category=EvidenceCategory.CROSS_SIGNAL,
                name="load_temperature_relationship",
                value="load_and_temperature_rise_correlated",
                source="investigation.E001.load_monitor",
                metadata={"id": "E001-cross-signal", "signal": "load_percent", "stance": "SUPPORTS"},
            )]
            reassessment_evidence = initial + new_evidence
            reassessment_review = review_engine.review(reassessment_evidence)
            reassessment_state = state_engine.evaluate(reassessment_evidence, previous_level=initial_state.level, evidence_review=reassessment_review)
            record["reassessment"] = {
                "new_evidence": [item.to_dict() for item in new_evidence],
                "evidence_review": reassessment_review.to_dict(),
                "state": reassessment_state.to_dict(),
                "finding": {"status": "HYPOTHESIS", "statement": "Thermal behavior is correlated with load; root cause remains unvalidated."},
            }
        else:
            contradictory = Evidence(
                category=EvidenceCategory.CROSS_SIGNAL,
                name="vibration_relationship",
                value="no_abnormal_vibration",
                source="investigation.I001.vibration_monitor",
                metadata={"id": "I001-cross-signal", "signal": "bearing_temperature", "stance": "CONTRADICTS"},
            )
            reassessment_evidence = initial + [contradictory]
            reassessment_review = review_engine.review(reassessment_evidence)
            reassessment_state = state_engine.evaluate(reassessment_evidence, previous_level=initial_state.level, evidence_review=reassessment_review)
            record["reassessment"] = {
                "new_evidence": [contradictory.to_dict()],
                "evidence_review": reassessment_review.to_dict(),
                "state": reassessment_state.to_dict(),
                "finding": {"status": "STILL_UNCERTAIN", "statement": "Evidence conflicts about the compressor thermal signal; further investigation is required."},
            }

        results.append(record)

    return {
        "demo": "GENESIS MULTI-DOMAIN END-TO-END DEMO V0.1",
        "fleet": registry.summary(),
        "supported_domains": list(ADAPTER_REGISTRY.domains()),
        "asset_results": results,
        "claims": [
            "The same Genesis evidence/review/state reasoning is reused across domains.",
            "Historical memory is advisory and context compatibility can require investigation.",
            "New evidence can change the reliability state without rewriting the original assessment.",
            "Conflicting evidence remains unresolved instead of being resolved by voting.",
        ],
        "limitations": [
            "All telemetry and investigation inputs are deterministic demonstration data.",
            "Domain adapters are integration-boundary demonstrations, not production connectors.",
            "The demo validates software reasoning behavior, not real-world failure prediction accuracy.",
        ],
    }


def render_report(result: Dict[str, Any]) -> str:
    lines = ["=" * 72, result["demo"], "=" * 72]
    lines.append(f"Fleet: {result['fleet']['asset_count']} assets | {result['fleet']['domain_count']} domains")
    lines.append("")
    for item in result["asset_results"]:
        initial = item["initial"]
        reassessment = item["reassessment"]
        lines.extend([
            f"{item['asset_id']} | {item['domain']} | {item['asset_type']}",
            f"  Initial state: {initial['state']['level']} — {initial['state']['reason']}",
            f"  Investigation required: {initial['investigation']['required']}",
            f"  Reassessed state: {reassessment['state']['level']} — {reassessment['state']['reason']}",
            f"  Finding: {reassessment['finding'].get('status')}",
            "",
        ])
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_report(run_demo()))
