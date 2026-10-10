from demo_genesis_multi_domain_e2e import run_demo
from genesis_operator_report import build_operator_report, render_operator_report


def _asset(report, asset_id):
    return next(item for item in report["assets"] if item["asset_id"] == asset_id)


def test_operator_report_preserves_all_demo_assets_and_domains():
    report = build_operator_report(run_demo())
    assert len(report["assets"]) == 3
    assert {item["domain"] for item in report["assets"]} == {
        "robotics", "energy_infrastructure", "industrial_equipment"
    }


def test_robot_report_exposes_context_uncertainty_and_reassessment():
    report = build_operator_report(run_demo())
    item = _asset(report, "R004")
    assert item["current_state"] == "CRITICAL"
    assert item["historical_context"]["compatibility"]["status"] == "UNKNOWN"
    assert item["historical_context"]["compatibility"]["investigation_required"] is True
    assert item["finding"]["status"] == "VALIDATED"
    assert item["assessment_mode"] == "GENESIS_ONLY"


def test_industrial_report_preserves_conflict_and_uncertainty():
    report = build_operator_report(run_demo())
    item = _asset(report, "I001")
    assert item["conflicting_evidence"]
    assert item["evidence_review"]["escalation_allowed"] is False
    assert item["finding"]["status"] == "STILL_UNCERTAIN"


def test_rendered_report_contains_operator_sections_and_limitations():
    report = build_operator_report(run_demo())
    rendered = render_operator_report(report)
    for section in (
        "CURRENT STATE",
        "WHAT GENESIS OBSERVED",
        "SUPPORTING EVIDENCE",
        "CONFLICTING EVIDENCE",
        "HISTORICAL CONTEXT",
        "INVESTIGATION",
        "REASSESSMENT",
        "FINDING",
        "ASSESSMENT SCOPE",
        "LIMITATIONS",
    ):
        assert section in rendered
    assert "Genesis-only assessment" in rendered
    assert "real-world failure prediction" in rendered
