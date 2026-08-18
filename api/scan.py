from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json

from pocketport.live_scan import LiveScanError, scan_public_github


MAX_REQUEST_BYTES = 4096


class handler(BaseHTTPRequestHandler):
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

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_GET(self) -> None:
        self._send_json(200, {"ok": True, "service": "pocketport-live-scan", "version": 1})

    def do_POST(self) -> None:
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
