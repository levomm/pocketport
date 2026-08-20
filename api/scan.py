from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
from urllib.parse import urlsplit

from pocketport.live_scan import LiveScanError, scan_public_github


MAX_REQUEST_BYTES = 4096
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/refresh.css": ("refresh.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/adapter.js": ("adapter.js", "text/javascript; charset=utf-8"),
    "/bridge-probe.js": ("bridge-probe.js", "text/javascript; charset=utf-8"),
    "/recorded-scans/deepseek-harness.json": ("recorded-scans/deepseek-harness.json", "application/json; charset=utf-8"),
    "/recorded-scans/plandex.json": ("recorded-scans/plandex.json", "application/json; charset=utf-8"),
}


class handler(BaseHTTPRequestHandler):
    def _path(self) -> str:
        return urlsplit(self.path).path

    def _send_bytes(self, status: int, body: bytes, content_type: str, *, cache_control: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()
        self.wfile.write(body)

    def _serve_web(self, relative: str, content_type: str) -> None:
        path = WEB_ROOT / relative
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json(500, {"error": "web asset unavailable", "code": "static_asset_error"})
            return
        cache = "public, max-age=300" if relative != "index.html" else "no-store"
        self._send_bytes(200, body, content_type, cache_control=cache)

    def do_OPTIONS(self) -> None:
        if self._path() == "/api/scan":
            self._send_json(204, {})
        else:
            self._send_json(404, {"error": "not found", "code": "not_found"})

    def do_GET(self) -> None:
        path = self._path()
        if path == "/api/scan":
            self._send_json(200, {"ok": True, "service": "pocketport-live-scan", "version": 1})
            return

        static = STATIC_ROUTES.get(path)
        if static:
            self._serve_web(*static)
            return

        if path == "/target" or path.startswith("/scan/"):
            self._serve_web("index.html", "text/html; charset=utf-8")
            return

        self._send_json(404, {"error": "not found", "code": "not_found"})

    def do_POST(self) -> None:
        if self._path() != "/api/scan":
            self._send_json(404, {"error": "not found", "code": "not_found"})
            return

        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self._send_json(400, {"error": "invalid Content-Length", "code": "invalid_request"})
            return

        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._send_json(413 if length > MAX_REQUEST_BYTES else 400, {
                "error": "request body is missing or too large",
                "code": "invalid_request",
            })
            return

        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "request body must be JSON", "code": "invalid_request"})
            return

        repository = payload.get("repository") if isinstance(payload, dict) else None
        try:
            report = scan_public_github(repository)
        except LiveScanError as exc:
            self._send_json(exc.status, {"error": str(exc), "code": exc.code})
            return
        except Exception:
            # Do not expose filesystem paths, stack traces or upstream internals.
            self._send_json(500, {"error": "live scan failed unexpectedly", "code": "internal_error"})
            return

        self._send_json(200, report)
