"""Deterministic Genesis demo for heterogeneous fleets and multiple industries."""

from dataclasses import asdict
from typing import Dict, List

from domain_adapter import (
    EnergyInfrastructureAdapter,
    IndustrialEquipmentAdapter,
    RoboticsAdapter,
    DomainAdapterRegistry,
)
from asset_contract import NormalizedObservation
from genesis_system.core.evidence_contract import Evidence, EvidenceCategory
from genesis_system.core.evidence_review import EvidenceReviewEngine
from genesis_system.core.investigation import InvestigationPlanner
from genesis_system.core.reliability_state import ReliabilityStateEvaluator
from fleet_registry import AssetFleetRegistry


ADAPTER_REGISTRY = DomainAdapterRegistry()
ADAPTER_REGISTRY.register("robotics", RoboticsAdapter())
ADAPTER_REGISTRY.register("energy_infrastructure", EnergyInfrastructureAdapter())
ADAPTER_REGISTRY.register("industrial_equipment", IndustrialEquipmentAdapter())


SCENARIO = [
    {"asset_id": "R001", "domain": "robotics", "asset_type": "AMR", "manufacturer": "Demo Robotics", "model": "AMR-X", "site_id": "WAREHOUSE-A", "timestamp": 1, "signals": {"motor_temperature": 44, "battery_voltage": 48, "velocity": 1.2}, "source": "sim.robot.r001"},
    {"asset_id": "R002", "domain": "robotics", "asset_type": "robotic_arm", "manufacturer": "Demo Robotics", "model": "ARM-X", "site_id": "FACTORY-A", "timestamp": 1, "signals": {"joint_temperature": 62, "motor_current": 14, "torque": 31}, "source": "sim.robot.r002"},
    {"asset_id": "R003", "domain": "robotics", "asset_type": "mobile_robot", "manufacturer": "Demo Robotics", "model": "MOBILE-X", "site_id": "WAREHOUSE-A", "timestamp": 1, "signals": {"motor_temperature": 47, "battery_voltage": 72, "velocity": 0.8}, "source": "sim.robot.r003"},
    {"asset_id": "R004", "domain": "robotics", "asset_type": "AMR", "manufacturer": "Demo Robotics", "model": "AMR-Y", "site_id": "WAREHOUSE-B", "timestamp": 1, "signals": {"motor_temperature": 58, "battery_voltage": 48, "velocity": 1.0}, "source": "sim.robot.r004"},
    {"asset_id": "E001", "domain": "energy_infrastructure", "asset_type": "transformer", "manufacturer": "Grid Systems", "model": "TX-100", "site_id": "ENERGY-SITE-A", "timestamp": 1, "signals": {"oil_temperature": 86, "load_percent": 78, "voltage": 22500}, "source": "sim.energy.e001"},
    {"asset_id": "E002", "domain": "energy_infrastructure", "asset_type": "generator", "manufacturer": "Power Systems", "model": "GEN-50", "site_id": "ENERGY-SITE-A", "timestamp": 1, "signals": {"bearing_temperature": 54, "vibration": 2.1, "load_percent": 61}, "source": "sim.energy.e002"},
    {"asset_id": "E003", "domain": "energy_infrastructure", "asset_type": "transformer", "manufacturer": "Grid Systems", "model": "TX-200", "site_id": "ENERGY-SITE-B", "timestamp": 1, "signals": {"oil_temperature": 64, "load_percent": 52, "voltage": 11000}, "source": "sim.energy.e003"},
    {"asset_id": "I001", "domain": "industrial_equipment", "asset_type": "compressor", "manufacturer": "Industrial Systems", "model": "CMP-20", "site_id": "FACTORY-A", "timestamp": 1, "signals": {"bearing_temperature": 71, "vibration": 4.8, "pressure": 8.2}, "source": "sim.industry.i001"},
    {"asset_id": "I002", "domain": "industrial_equipment", "asset_type": "cnc_machine", "manufacturer": "Industrial Systems", "model": "CNC-4", "site_id": "FACTORY-A", "timestamp": 1, "signals": {"spindle_temperature": 49, "vibration": 1.7, "power_kw": 18}, "source": "sim.industry.i002"},
]


def build_registry() -> AssetFleetRegistry:
    registry = AssetFleetRegistry()
    for payload in SCENARIO:
        observation = ADAPTER_REGISTRY.get(payload["domain"]).normalize(payload)
        registry.ingest(observation)
    return registry


def _evidence_for(asset_id: str, domain: str) -> List[Evidence]:
    if asset_id in {"R001", "E002", "E003", "I002"}:
        return []
    if asset_id in {"R003"}:
        return [Evidence(
            category=EvidenceCategory.OBSERVATION,
            name="asset_observation",
            value="within_expected_range",
            source=f"demo.{domain}.{asset_id}",
            metadata={"id": f"{asset_id}-observation"},
        )]
    signal_name = {
        "robotics": "motor_temperature_deviation",
        "energy_infrastructure": "thermal_load_deviation",
        "industrial_equipment": "bearing_temperature_deviation",
    }[domain]
    source = f"demo.{domain}.{asset_id}"
    return [
        Evidence(
            category=EvidenceCategory.DEVIATION,
            name=signal_name,
            value="above_domain_baseline",
            source=source,
            metadata={"id": f"{asset_id}-deviation", "signal": signal_name, "stance": "SUPPORTS"},
        ),
        Evidence(
            category=EvidenceCategory.TEMPORAL,
            name="persistent_behavior",
            value="repeated_across_observations",
            source=source,
            metadata={"id": f"{asset_id}-temporal", "signal": signal_name, "stance": "SUPPORTS"},
        ),
    ]


def run_demo() -> Dict[str, object]:
    registry = build_registry()
    state_engine = ReliabilityStateEvaluator()
    review_engine = EvidenceReviewEngine()
    investigation = InvestigationPlanner()
    asset_results = []

    for asset in registry.snapshot().assets:
        evidence = _evidence_for(asset.asset_id, asset.domain)
        review = review_engine.review(evidence)
        state = state_engine.evaluate(evidence, evidence_review=review)
        plan = investigation.plan(evidence, review)
        asset_results.append({
            "asset_id": asset.asset_id,
            "domain": asset.domain,
            "asset_type": asset.asset_type,
            "site_id": asset.site_id,
            "state": state.to_dict(),
            "evidence_review": review.to_dict(),
            "investigation": plan.to_dict(),
        })

    return {
        "demo": "GENESIS MULTI-DOMAIN FLEET DEMO V0.1",
        "registry": registry.summary(),
        "supported_domains": list(ADAPTER_REGISTRY.domains()),
        "architecture_claim": "Domain-specific adapters feed a shared Genesis reliability reasoning layer.",
        "asset_results": asset_results,
        "limitations": [
            "Telemetry is deterministic controlled simulation data.",
            "Adapters demonstrate the integration boundary; they are not production connectors.",
            "Reliability state is a reasoning demonstration, not proof of real-world failure prediction.",
        ],
    }


def render_report(result: Dict[str, object]) -> str:
    lines = [
        "=" * 58,
        result["demo"],
        "=" * 58,
        f"Assets monitored: {result['registry']['asset_count']}",
        f"Domains: {', '.join(result['registry']['assets_by_domain'])}",
        f"Sites: {', '.join(result['registry']['sites'])}",
        "",
        "ASSET RESULTS",
    ]
    for item in result["asset_results"]:
        state = item["state"]
        lines.extend([
            f"• {item['asset_id']} | {item['domain']} | {item['asset_type']} | {item['site_id']}",
            f"  State: {state['level']}",
            f"  Reason: {state['reason']}",
            f"  Investigation required: {item['investigation']['required']}",
        ])
    lines.extend(["", "LIMITATIONS"])
    lines.extend(f"• {item}" for item in result["limitations"])
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_report(run_demo()))
