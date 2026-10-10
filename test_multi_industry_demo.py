from demo_multi_industry import build_registry, run_demo
from asset_contract import AssetProfile
from domain_adapter import DomainAdapterRegistry, RoboticsAdapter


def test_registry_handles_heterogeneous_assets():
    registry = build_registry()
    summary = registry.summary()
    assert summary["asset_count"] == 9
    assert summary["domain_count"] == 3
    assert summary["assets_by_domain"] == {
        "energy_infrastructure": 3,
        "industrial_equipment": 2,
        "robotics": 4,
    }


def test_registry_preserves_cross_industry_identity_and_peer_groups():
    registry = build_registry()
    asset = registry.get_asset("E001")
    assert asset.domain == "energy_infrastructure"
    assert [item.asset_id for item in registry.peer_group(asset)] == ["E003"]

    robot = registry.get_asset("R001")
    assert [item.asset_id for item in registry.peer_group(robot)] == ["R004"]


def test_demo_uses_shared_reasoning_across_domains():
    result = run_demo()
    assert result["supported_domains"] == [
        "energy_infrastructure",
        "industrial_equipment",
        "robotics",
    ]
    assert len(result["asset_results"]) == 9
    states = {item["asset_id"]: item["state"]["level"] for item in result["asset_results"]}
    assert states["R001"] == "NORMAL"
    assert states["R003"] == "OBSERVATION"
    assert states["R004"] == "CONCERN"
    assert states["R002"] == "CONCERN"
    assert states["E001"] == "CONCERN"
    assert states["I001"] == "CONCERN"
    assert all(item["evidence_review"]["escalation_allowed"] for item in result["asset_results"])


def test_demo_does_not_claim_production_connectors():
    result = run_demo()
    assert any("not production connectors" in item for item in result["limitations"])


def test_asset_contract_rejects_empty_identity():
    try:
        AssetProfile(asset_id="", domain="robotics", asset_type="AMR")
    except ValueError as exc:
        assert "asset_id" in str(exc)
    else:
        raise AssertionError("Expected empty asset_id to be rejected")


def test_new_industry_can_be_added_at_adapter_boundary():
    registry = DomainAdapterRegistry()
    registry.register("robotics", RoboticsAdapter())
    assert registry.domains() == ("robotics",)
