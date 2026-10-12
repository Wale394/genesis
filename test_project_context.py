"""Focused checks for the project charter API and its trust boundary."""
import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen

from genesis_interface.server import Handler


def test_project_context_contract_has_current_and_future_scope():
    from pathlib import Path
    context_path = Path(__file__).resolve().parent / "project_context.json"
    context = json.loads(context_path.read_text(encoding="utf-8"))
    assert context["project"]["project_name"] == "Genesis"
    assert context["project"]["system_name"] == "KORDEX"
    assert context["current_focus"]["not_production_ready"] is True
    assert context["current_architecture"]["flow"]
    assert context["roadmap"]
    assert context["long_term_vision"]["vision_is_not_current_capability"] is True
    assert any(item["status"] == "FUTURE_GATED" for item in context["roadmap"])


def test_project_context_api_serves_read_only_charter():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/project-context", timeout=3) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["mission"]
        assert payload["current_architecture"]["flow"][0]["name"] == "Sources and adapters"
        assert "project_context" not in payload.get("current_focus", {})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
