from demo_genesis_multi_domain_e2e import run_demo


def _by_id(result, asset_id):
    return next(item for item in result["asset_results"] if item["asset_id"] == asset_id)


def test_demo_runs_across_three_domains():
    result = run_demo()
    assert result["fleet"]["asset_count"] == 3
    assert result["supported_domains"] == [
        "energy_infrastructure",
        "industrial_equipment",
        "robotics",
    ]


def test_robot_history_requires_context_investigation_then_reassessment():
    result = run_demo()
    item = _by_id(result, "R004")
    assert item["initial"]["state"]["level"] == "CONCERN"
    assert item["context_compatibility"]["status"] == "UNKNOWN"
    assert item["context_compatibility"]["investigation_required"] is True
    assert item["initial"]["investigation"]["required"] is True
    assert item["reassessment"]["state"]["previous_level"] == "CONCERN"
    assert item["reassessment"]["state"]["level"] == "CRITICAL"
    assert item["reassessment"]["finding"]["status"] == "VALIDATED"


def test_energy_case_reassesses_with_new_cross_signal_evidence():
    result = run_demo()
    item = _by_id(result, "E001")
    assert item["initial"]["state"]["level"] == "CONCERN"
    assert item["reassessment"]["state"]["previous_level"] == "CONCERN"
    assert item["reassessment"]["state"]["level"] == "CRITICAL"
    assert item["reassessment"]["finding"]["status"] == "HYPOTHESIS"


def test_industrial_conflict_stays_uncertain():
    result = run_demo()
    item = _by_id(result, "I001")
    review = item["reassessment"]["evidence_review"]
    assert review["escalation_allowed"] is False
    assert review["conflicts"]
    assert item["reassessment"]["state"]["level"] == "OBSERVATION"
    assert item["reassessment"]["finding"]["status"] == "STILL_UNCERTAIN"


def test_demo_explicitly_limits_real_world_claims():
    result = run_demo()
    assert any("real-world failure prediction" in item for item in result["limitations"])
