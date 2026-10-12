"""Zero-dependency local HTTP server for the Genesis Command Center."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .controller import GenesisController, command_center_scenario

UI_DIR = Path(__file__).resolve().parent / "ui"
controller = GenesisController()


class Handler(BaseHTTPRequestHandler):
    server_version = "KordexInterface/1.7"

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(200, {"status": "online", "system": "KORDEX", "project": "Genesis"})
            return
        if path == "/api/project-context":
            context_path = Path(__file__).resolve().parents[1] / "project_context.json"
            try:
                context = json.loads(context_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._send_json(500, {"error": "project context is unavailable"})
                return
            self._send_json(200, context)
            return
        if path == "/api/state":
            self._send_json(200, controller.snapshot())
            return
        if path == "/api/assets":
            assets = controller.assets()
            self._send_json(200, {"count": len(assets), "assets": assets})
            return
        if path.startswith("/api/assets/"):
            from urllib.parse import unquote
            asset_id = unquote(path[len("/api/assets/"):])
            detail = controller.asset_detail(asset_id)
            if detail is None:
                self._send_json(404, {"error": "asset has no observations in this session"})
            else:
                self._send_json(200, detail)
            return
        if path == "/api/memory":
            entries = controller.memory_entries()
            self._send_json(200, {"count": len(entries), "entries": entries})
            return
        if path == "/api/decision-records":
            records = controller.decision_records()
            self._send_json(200, {"count": len(records), "records": records})
            return
        if path == "/api/incidents":
            incidents = controller.incidents()
            self._send_json(200, {"count": len(incidents), "incidents": incidents})
            return
        if path in ("/", "/index.html"):
            self._send_file(UI_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.css":
            self._send_file(UI_DIR / "app.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._send_file(UI_DIR / "app.js", "text/javascript; charset=utf-8")
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/reset":
                self._send_json(200, controller.reset())
                return
            if path == "/api/investigate":
                controller.validate_observation(payload)
                self._send_json(200, controller.investigate(payload))
                return
            if path == "/api/adapters/ros2":
                self._send_json(200, controller.investigate_ros2(payload))
                return
            if path == "/api/investigation/follow-up":
                result = controller.submit_followup_observation(payload)
                self._send_json(200, {"result": result, "state": controller.snapshot(), "note": "Submitted as a new observation. This does not automatically validate a hypothesis."})
                return
            if path == "/api/scenario":
                results = controller.run_scenario(command_center_scenario())
                self._send_json(200, {"results": results, "state": controller.snapshot()})
                return
            self._send_json(404, {"error": "not found"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # interface boundary: never leak a traceback
            self._send_json(500, {"error": f"Genesis interface error: {exc}"})

    def log_message(self, fmt, *args):
        # Keep the Command Center terminal readable.
        print(f"[genesis] {fmt % args}")


def serve(host="127.0.0.1", port=8765):
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"KORDEX Command Center (Genesis project): http://{host}:{port}")
    print("KORDEX local reliability-intelligence system ready. Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    serve()
