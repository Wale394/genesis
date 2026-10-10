import json
import subprocess
import sys
import time
import urllib.request

from genesis_interface.controller import GenesisController, command_center_scenario


def test_controller_uses_real_genesis_engine():
    controller = GenesisController()
    result = controller.investigate(command_center_scenario()[0])
    assert result["robot"]["robot_id"] == "R004"
    assert result["reliability_state"]["current"] in {"NORMAL", "WATCH", "WARNING", "CONCERN", "CRITICAL", "RECOVERING", "FAILED"}
    assert result["processing"]["observation_count"] == 1


def test_observation_contract_rejects_non_object_and_missing_telemetry():
    import pytest
    with pytest.raises(ValueError, match="observation must be an object"):
        GenesisController.validate_observation([{"motor_temperature": 30}])
    with pytest.raises(ValueError, match="at least one telemetry field"):
        GenesisController.validate_observation({"robot_id": "API-R001"})


def test_observation_contract_allows_supported_telemetry_without_inventing_identity():
    observation = {"motor_temperature": 30, "time_step": 1}
    assert GenesisController.validate_observation(observation) is observation
    import pytest
    with pytest.raises(ValueError, match="robot_id is required"):
        GenesisController.validate_observation(observation, require_identity=True)


def test_scenario_is_real_engine_end_to_end():
    controller = GenesisController()
    results = controller.run_scenario(command_center_scenario())
    assert len(results) == 8
    assert results[4]["reliability_state"]["current"] == "CRITICAL"
    assert results[-1]["processing"]["telemetry"][-1]["motor_temperature"] == 44
    assert controller.snapshot()["latest"] == results[-1]
    assert controller.snapshot()["events"]


def test_reset_removes_session_state():
    controller = GenesisController()
    controller.investigate(command_center_scenario()[0])
    state = controller.reset()
    assert state["latest"] is None
    assert state["events"] == []


def test_server_health_and_state(tmp_path):
    proc = subprocess.Popen([sys.executable, "-m", "genesis_interface.server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=0.5) as response:
                    assert json.loads(response.read())["status"] == "online"
                    break
            except Exception:
                time.sleep(0.05)
        else:
            raise AssertionError("server did not start")
        with urllib.request.urlopen("http://127.0.0.1:8765/api/state", timeout=1) as response:
            payload = json.loads(response.read())
            assert "latest" in payload and "events" in payload
        for endpoint, key in (("memory", "entries"), ("incidents", "incidents")):
            with urllib.request.urlopen(f"http://127.0.0.1:8765/api/{endpoint}", timeout=1) as response:
                payload = json.loads(response.read())
                assert key in payload and isinstance(payload[key], list)
        request = urllib.request.Request(
            "http://127.0.0.1:8765/api/investigation/follow-up",
            data=json.dumps({"robot_id":"API-R001", "time_step":1, "motor_temperature":30}).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read())
            assert payload["result"]["robot"]["robot_id"] == "API-R001"
            assert "does not automatically validate" in payload["note"]
    finally:
        proc.terminate()
        proc.wait(timeout=3)


def test_investigate_endpoint_rejects_payload_without_telemetry():
    proc = subprocess.Popen([sys.executable, "-m", "genesis_interface.server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=0.5):
                    break
            except Exception:
                time.sleep(0.05)
        else:
            raise AssertionError("server did not start")
        request = urllib.request.Request(
            "http://127.0.0.1:8765/api/investigate",
            data=json.dumps({"robot_id": "API-R001"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            assert "at least one telemetry field" in json.loads(exc.read())['error']
        else:
            raise AssertionError("invalid observation unexpectedly accepted")
    finally:
        proc.terminate()
        proc.wait(timeout=3)


def test_snapshot_preserves_each_real_result_for_inspection():
    controller = GenesisController()
    results = controller.run_scenario(command_center_scenario())
    snapshot = controller.snapshot()
    assert len(snapshot["history"]) == len(results) == 8
    assert snapshot["history"][4]["reliability_state"]["current"] == "CRITICAL"
    synthesis = snapshot["history"][4]["evidence_synthesis"]
    assert "observations" in synthesis
    assert "contradictions" in synthesis
    assert "missing_evidence" in synthesis
    assert snapshot["history"][-1] == snapshot["latest"]


def test_reset_clears_inspection_history():
    controller = GenesisController()
    controller.investigate(command_center_scenario()[0])
    state = controller.reset()
    assert state["history"] == []
    assert state["latest"] is None


def test_multi_workspace_navigation_is_present_and_separate():
    from pathlib import Path
    ui = Path(__file__).parent / "genesis_interface" / "ui" / "index.html"
    markup = ui.read_text(encoding="utf-8")
    for page in ("overview", "assets", "telemetry", "evidence", "investigations", "memory", "incidents", "audit"):
        assert f'data-page="{page}"' in markup
        assert f'data-view="{page}"' in markup


def test_memory_and_incident_pages_have_dedicated_live_workspaces():
    from pathlib import Path
    ui = Path(__file__).parent / "genesis_interface" / "ui" / "index.html"
    markup = ui.read_text(encoding="utf-8")
    assert 'data-view="memory"' in markup
    assert 'data-view="incidents"' in markup
    assert "Records currently held by this live Genesis engine session" in markup
    assert "Incident records owned by the actual Genesis incident manager" in markup


def test_controller_exposes_live_memory_and_incident_records():
    controller = GenesisController()
    controller.run_scenario(command_center_scenario())
    assert isinstance(controller.memory_entries(), list)
    incidents = controller.incidents()
    assert isinstance(incidents, list)
    assert all(isinstance(item, dict) for item in incidents)


def test_followup_observation_is_processed_by_real_engine():
    controller = GenesisController()
    controller.run_scenario(command_center_scenario())
    result = controller.submit_followup_observation({
        "robot_id": "R004", "time_step": 9,
        "motor_temperature": 28, "ambient_temperature": 25,
        "battery_level": 80, "workload": 50,
    })
    assert result["robot"]["robot_id"] == "R004"
    assert result["processing"]["observation_count"] == 1
    assert len(controller.snapshot()["history"]) == 9


def test_followup_observation_rejects_empty_telemetry():
    controller = GenesisController()
    try:
        controller.submit_followup_observation({"robot_id": "R004", "time_step": 1})
    except ValueError as exc:
        assert "at least one telemetry field" in str(exc)
    else:
        raise AssertionError("empty follow-up telemetry should be rejected")


def test_memory_and_incident_pages_use_real_endpoints_not_placeholders():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface"
    markup = (root / "ui" / "index.html").read_text(encoding="utf-8")
    app = (root / "ui" / "app.js").read_text(encoding="utf-8")
    server = (root / "server.py").read_text(encoding="utf-8")
    assert "api('/api/memory')" in app
    assert "api('/api/incidents')" in app
    assert 'data-view="memory"' in markup and 'data-view="incidents"' in markup
    assert 'path == "/api/memory"' in server
    assert 'path == "/api/incidents"' in server


def test_asset_inventory_and_detail_are_derived_from_real_results():
    controller = GenesisController()
    results = controller.run_scenario(command_center_scenario())
    assets = controller.assets()
    assert len(assets) == 1
    assert assets[0]["asset_id"] == "R004"
    assert assets[0]["observations"] == len(results)
    detail = controller.asset_detail("R004")
    assert detail is not None
    assert detail["latest"] == results[-1]
    assert len(detail["history"]) == len(results)
    assert detail["source_scope"] == "current Genesis interface session"


def test_unknown_asset_has_no_fabricated_detail():
    controller = GenesisController()
    assert controller.asset_detail("DOES-NOT-EXIST") is None


def test_asset_workspace_is_a_separate_interactive_page():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface"
    markup = (root / "ui" / "index.html").read_text(encoding="utf-8")
    app = (root / "ui" / "app.js").read_text(encoding="utf-8")
    server = (root / "server.py").read_text(encoding="utf-8")
    assert 'id="asset-list"' in markup
    assert 'id="asset-detail-panel"' in markup
    assert "api('/api/assets')" in app
    assert 'path == "/api/assets"' in server
    assert 'path.startswith("/api/assets/")' in server


def test_telemetry_workspace_has_real_time_series_and_quality_panels():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface"
    markup = (root / "ui" / "index.html").read_text(encoding="utf-8")
    app = (root / "ui" / "app.js").read_text(encoding="utf-8")
    for chart_id in ("chart-motor", "chart-ambient", "chart-battery", "chart-voltage", "chart-workload"):
        assert f'id="{chart_id}"' in markup
        assert chart_id in app
    assert 'id="telemetry-quality"' in markup
    assert "renderTelemetryCharts" in app
    assert "renderTelemetryQuality" in app
    assert "NOT EXPOSED" in app
    assert "Missing values are left as gaps; no interpolation is applied." in markup


def test_telemetry_visuals_explicitly_distinguish_unavailable_measurement_validity():
    from pathlib import Path
    app = (Path(__file__).parent / "genesis_interface" / "ui" / "app.js").read_text(encoding="utf-8")
    assert "Current runtime provides no calibration assessment" in app
    assert "Current runtime provides no dedicated measurement-validity assessment" in app
    assert "security.authentication" in app and "security.integrity" in app


def test_overview_contains_evidence_summary_target_used_by_assessment_renderer():
    from pathlib import Path
    markup = (Path(__file__).parent / "genesis_interface" / "ui" / "index.html").read_text(encoding="utf-8")
    app = (Path(__file__).parent / "genesis_interface" / "ui" / "app.js").read_text(encoding="utf-8")
    assert 'id="evidence-list"' in markup
    assert "$('evidence-list').innerHTML" in app


def test_interactive_measurement_trace_is_present_and_does_not_fabricate_provenance():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface" / "ui"
    markup = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "app.js").read_text(encoding="utf-8")
    assert 'id="measurement-trace"' in markup
    assert 'data-measurement-index' in script
    assert 'function selectMeasurement' in script
    assert 'NOT EXPOSED' in script
    assert 'normalized measurement present in Genesis' in script
    assert 'causally depends' not in script  # no unsupported causal linkage claim

def test_measurement_trace_can_navigate_to_raw_engine_result():
    from pathlib import Path
    script = (Path(__file__).parent / "genesis_interface" / "ui" / "app.js").read_text(encoding="utf-8")
    assert "trace-open-evidence" in script
    assert "trace-show-json" in script
    assert "details.open=true" in script


def test_theme_toggle_and_light_theme_tokens_are_present():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface" / "ui"
    markup = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "app.js").read_text(encoding="utf-8")
    css = (root / "app.css").read_text(encoding="utf-8")
    assert 'id="theme-toggle"' in markup
    assert "dataset.theme" in script and "genesis-theme" in script
    assert ':root[data-theme="light"]' in css
    assert 'aria-pressed' in script


def test_evidence_lineage_displays_only_engine_declared_support_and_limits():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface" / "ui"
    markup = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "app.js").read_text(encoding="utf-8")
    assert 'id="evidence-lineage"' in markup
    assert 'function renderEvidenceLineage(result)' in script
    assert 'supporting_evidence_ids' in script and 'input_evidence_ids' in script
    assert 'No upstream evidence IDs declared or conservatively matched' in script
    assert 'Engine lineage graph' in script
    assert 'item.limitations' in script
    assert 'Temporal scope' in script
    assert 'temporal_order_warnings' in script


def test_controller_preserves_submitted_telemetry_not_exposed_by_normalized_output():
    controller = GenesisController()
    observation = command_center_scenario()[0]
    result = controller.investigate(observation)
    captured = result["interface_capture"]
    assert captured["status"] == "SUBMITTED_INPUT_NOT_ENGINE_NORMALIZED"
    assert captured["telemetry"]["ambient_temperature"] == observation["ambient_temperature"]
    assert captured["telemetry"]["battery_level"] == observation["battery_level"]
    assert captured["telemetry"]["battery_voltage"] == observation["battery_voltage"]
    assert captured["telemetry"]["workload"] == observation["workload"]
    assert "battery_voltage" not in result["processing"]["telemetry"][0]


def test_telemetry_workspace_labels_captured_input_boundary():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface"
    app = (root / "ui" / "app.js").read_text(encoding="utf-8")
    controller = (root / "controller.py").read_text(encoding="utf-8")
    assert "SUBMITTED_INPUT_NOT_ENGINE_NORMALIZED" in controller
    assert "result.interface_capture?.status" in app
    assert "chart-ambient" in app and "chart-voltage" in app
    assert "followup-voltage" in app


def test_asset_latest_measurements_use_controller_capture_when_engine_omits_fields():
    from pathlib import Path
    app = (Path(__file__).parent / "genesis_interface" / "ui" / "app.js").read_text(encoding="utf-8")
    # Asset details must use the same merged telemetry view as the main dashboard.
    assert "const telemetry=latestTelemetry(latest);" in app
    assert "ambient_temperature" in app and "battery_level" in app
    assert "battery_voltage" in app and "workload" in app
    assert "not independently sensor-authenticated readings" in app


def test_controller_captures_all_requested_latest_measurement_fields():
    controller = GenesisController()
    observation = {
        "robot_id": "ASSET-TELEMETRY-TEST", "time_step": 1,
        "motor_temperature": 31, "ambient_temperature": 26,
        "battery_level": 73, "battery_voltage": 47.5, "workload": 62,
    }
    result = controller.investigate(observation)
    captured = result["interface_capture"]["telemetry"]
    assert {key: captured[key] for key in ("ambient_temperature", "battery_level", "battery_voltage", "workload")} == {
        "ambient_temperature": 26, "battery_level": 73, "battery_voltage": 47.5, "workload": 62,
    }
    detail = controller.asset_detail("ASSET-TELEMETRY-TEST")
    assert detail["latest"]["interface_capture"]["telemetry"] == captured


def test_evidence_lineage_ui_displays_engine_graph_relationships():
    from pathlib import Path
    script = (Path(__file__).parent / "genesis_interface" / "ui" / "app.js").read_text(encoding="utf-8")
    assert "Engine graph relationships" in script
    assert "graph.edges" in script
    assert "edge.relationship" in script
    assert "Pattern-window links record embedded source-row membership" in script


def test_default_scenario_evidence_lineage_has_traceable_pattern_window_links():
    controller = GenesisController()
    results = controller.run_scenario(command_center_scenario())
    graph = results[-1]["evidence_synthesis"]["evidence_lineage"]
    assert graph["counts"]["edges"] > 0
    assert graph["counts"]["window_observation_nodes"] > 0
    assert any(edge["relationship"] == "OBSERVED_IN_PATTERN_WINDOW" for edge in graph["edges"])
    assert graph["counts"]["evidence_items"] >= graph["counts"]["unlinked_evidence"]
    assert not any(edge["relationship"] == "CAUSAL" for edge in graph["edges"])


def test_derived_feature_lineage_declares_exact_historical_inputs():
    controller = GenesisController()
    results = controller.run_scenario(command_center_scenario())
    result = results[-1]
    synthesis = result["evidence_synthesis"]
    graph = synthesis["evidence_lineage"]
    feature = next((item for item in synthesis["temporal_evidence"] if item.get("field") == "temperature_change"), None)
    assert feature is not None
    feature_id = feature["evidence_id"]
    assert feature["supporting_data"]["temporal_scope"] == "DERIVED_FEATURE_WINDOW_EXPOSED"
    assert feature["supporting_data"]["input_fields"] == ["motor_temperature"]
    assert feature["supporting_data"]["window"]["observation_count"] == 2
    links = [edge for edge in graph["edges"] if edge["to_evidence_id"] == feature_id and edge["relationship"] == "INPUT_TO_DERIVED_FEATURE"]
    assert len(links) >= 2
    assert any(edge["from_evidence_id"].startswith("INPUT-ROW-") for edge in links)
    assert any(edge["from_evidence_id"] == "OBS-motor_temperature" for edge in links)
    assert all("not causation" in edge["basis"].lower() or "not causal" in edge["basis"].lower() for edge in links)


def test_derived_feature_lineage_does_not_invent_missing_history_inputs():
    controller = GenesisController()
    result = controller.investigate({"robot_id": "LINEAGE-ONE", "time_step": 1, "motor_temperature": 31})
    synthesis = result["evidence_synthesis"]
    feature = next((item for item in synthesis["temporal_evidence"] if item.get("field") == "temperature_change"), None)
    assert feature is None  # no previous observation means no computed delta evidence
    graph = synthesis["evidence_lineage"]
    assert not any(edge["relationship"] == "INPUT_TO_DERIVED_FEATURE" and edge["to_evidence_id"] == "TEMP-temperature_change" for edge in graph["edges"])


def test_thermal_rise_lineage_uses_exact_feature_contract_formula():
    from evidence_synthesis import EvidenceSynthesis
    result = EvidenceSynthesis().synthesize(
        feature_record={
            "robot_id": "THERMAL-LINEAGE", "time_step": 3,
            "motor_temperature": 42, "ambient_temperature": 25,
            "thermal_rise": 17,
        }
    )
    graph = result["evidence_lineage"]
    links = [edge for edge in graph["edges"] if edge["to_evidence_id"] == "OBS-thermal_rise"]
    assert {edge["from_evidence_id"] for edge in links} == {
        "OBS-motor_temperature", "OBS-ambient_temperature"
    }
    assert all(edge["relationship"] == "FORMULA_INPUT_TO_DERIVED_FEATURE" for edge in links)


def test_derived_feature_lineage_never_uses_other_robot_history():
    from evidence_synthesis import EvidenceSynthesis
    result = EvidenceSynthesis().synthesize(
        feature_record={
            "robot_id": "ROBOT-A", "time_step": 8,
            "motor_temperature": 32, "ambient_temperature": 22,
            "thermal_rise": 10, "temperature_change": 2,
        },
        historical_records=[
            {"robot_id": "ROBOT-B", "time_step": 7, "motor_temperature": 99},
            {"robot_id": "ROBOT-A", "time_step": 7, "motor_temperature": 30},
        ],
    )
    graph = result["evidence_lineage"]
    feature_edges = [edge for edge in graph["edges"] if edge["to_evidence_id"] == "TEMP-temperature_change"]
    assert any(edge["from_evidence_id"].startswith("INPUT-ROW-ROBOT-A-") for edge in feature_edges)
    assert not any("ROBOT-B" in edge["from_evidence_id"] for edge in graph["edges"])
    assert not any("ROBOT-B" in node["evidence_id"] for node in graph["nodes"])


def test_command_center_uses_kordex_brand_and_inline_mark():
    from pathlib import Path
    markup = (Path(__file__).parent / "genesis_interface" / "ui" / "index.html").read_text(encoding="utf-8")
    assert "KORDEX" in markup
    assert "Engineering Intelligence" in markup
    assert '<svg viewBox="0 0 64 64"' in markup
    assert '<span class="brand-mark">G</span>' not in markup
    assert "Run Assessment" in markup


def test_brand_mark_has_light_theme_adaptation():
    from pathlib import Path
    styles = (Path(__file__).parent / "genesis_interface" / "ui" / "app.css").read_text(encoding="utf-8")
    assert '.brand-mark svg' in styles
    assert ':root[data-theme="light"] .brand-mark' in styles


def test_decision_provenance_records_hashes_and_explicit_limits():
    from genesis_interface.controller import GenesisController, command_center_scenario
    controller = GenesisController()
    controller.run_scenario(command_center_scenario()[:2])
    snapshot = controller.snapshot()
    records = snapshot["decision_records"]
    assert len(records) == 2
    assert records[0]["record_id"] == "KDX-DEC-00001"
    assert len(records[0]["input_sha256"]) == 64
    assert len(records[0]["result_sha256"]) == 64
    assert records[0]["record_scope"].endswith("unsigned")
    assert any("not tamper-proof" in limitation for limitation in records[0]["limitations"])


def test_reset_clears_session_decision_provenance():
    from genesis_interface.controller import GenesisController, command_center_scenario
    controller = GenesisController()
    controller.run_scenario(command_center_scenario()[:1])
    assert controller.decision_records()
    controller.reset()
    assert controller.decision_records() == []


def test_audit_view_exposes_decision_record_workspace():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface"
    markup = (root / "ui" / "index.html").read_text(encoding="utf-8")
    script = (root / "ui" / "app.js").read_text(encoding="utf-8")
    assert 'id="decision-records"' in markup
    assert "renderDecisionRecords" in script
    assert "/api/decision-records" in script


def test_kordex_overview_matches_dashboard_mockup_with_real_measurement_slots():
    from pathlib import Path
    root = Path(__file__).parent / "genesis_interface" / "ui"
    markup = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "app.css").read_text(encoding="utf-8")
    for element_id in (
        "overview-chart-motor", "overview-chart-battery", "overview-chart-workload",
        "overview-ambient", "overview-battery", "overview-voltage", "overview-workload",
    ):
        assert f'id="{element_id}"' in markup
    assert "dashboard-lower-grid" in styles
    assert "overview-chart-motor" in script
    assert "submitted values" in markup


def test_result_preserves_submitted_input_separately_from_engine_telemetry():
    controller = GenesisController()
    submitted = {
        "robot_id": "TRACE-R001",
        "time_step": 2,
        "motor_temperature": 31,
        "ambient_temperature": 24,
        "battery_level": 76,
        "battery_voltage": 48,
        "workload": 42,
    }
    result = controller.investigate(submitted)
    capture = result["interface_capture"]
    assert capture["status"] == "SUBMITTED_INPUT_NOT_ENGINE_NORMALIZED"
    assert capture["telemetry"]["motor_temperature"] == 31
    assert capture["telemetry"]["workload"] == 42
    # The provenance layer must not silently rewrite the engine's own output.
    assert result["processing"]["telemetry"]
    assert result["processing"]["telemetry"] is not capture["telemetry"]
    assert capture["source"] == "GenesisController.investigate input"


def test_ros2_adapter_endpoint_preserves_mapping_provenance_and_limits():
    controller = GenesisController()
    payload = {
        "robot_id": "ROS-API-01",
        "manufacturer": "ABB",
        "robot_type": "AMR",
        "diagnostic_array": {
            "header": {"stamp": {"sec": 12, "nanosec": 500000000}},
            "status": [{"name": "thermal", "values": [
                {"key": "motor_temperature", "value": "104 F"},
                {"key": "vendor_unknown", "value": "123"},
            ]}],
        },
    }
    result = controller.investigate_ros2(payload)
    provenance = result["adapter_provenance"]
    assert result["robot"]["robot_id"] == "ROS-API-01"
    assert provenance["adapter"] == "ROS2TelemetryAdapter"
    assert provenance["status"] == "ADAPTED_JSON_PAYLOAD_NOT_LIVE_ROS_CONNECTION"
    assert provenance["adapted_observation"]["telemetry"]["motor_temperature"] == 40.0
    assert provenance["source_metadata"]["timestamp"] == {"sec": 12, "nanosec": 500000000}
    assert any("Unmapped diagnostic keys" in item for item in provenance["limitations"])
    assert controller.snapshot()["latest"]["adapter_provenance"] == provenance


def test_ros2_adapter_rejects_payload_without_usable_telemetry():
    import pytest
    controller = GenesisController()
    with pytest.raises(ValueError, match="no usable telemetry"):
        controller.investigate_ros2({
            "robot_id": "ROS-EMPTY",
            "diagnostic_array": {"status": [{"name": "unknown", "values": [
                {"key": "unknown_field", "value": "12"},
            ]}]},
        })


def test_ros2_adapter_requires_identity_and_diagnostic_array():
    import pytest
    controller = GenesisController()
    with pytest.raises(ValueError, match="robot_id is required"):
        controller.investigate_ros2({"diagnostic_array": {"status": []}})
    with pytest.raises(ValueError, match="diagnostic_array must be an object"):
        controller.investigate_ros2({"robot_id": "ROS-1", "diagnostic_array": []})
