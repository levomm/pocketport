from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
import json
import os
import platform
from urllib.parse import urlsplit

from .live_scan import LiveScanError, scan_public_github
from .release import normalize_arch


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 33343
MAX_REQUEST_BYTES = 4096
ALLOWED_ORIGINS = {
    "https://pocketport.vercel.app",
}


def _package_version() -> str:
    try:
        return version("pocketport")
    except PackageNotFoundError:
        return "dev"


def health_payload() -> dict[str, object]:
    prefix = os.environ.get("PREFIX", "")
    return {
        "ok": True,
        "service": "pocketport-local-bridge",
        "api": 2,
        "binding": "loopback",
        "version": _package_version(),
        "termux": "com.termux" in prefix,
        "arch": normalize_arch(platform.machine()),
        "capabilities": ["health", "local-plan"],
    }


def _allowed_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    if origin in ALLOWED_ORIGINS:
        return origin

    try:
        parsed = urlsplit(origin)
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return None
    return origin


def _local_plan(repository: str) -> dict[str, object]:
    report = scan_public_github(repository)
    return {
        "ok": True,
        "service": "pocketport-local-bridge",
        "api": 2,
        "source": "local-device",
        "repository": report.get("repository", repository),
        "device": health_payload(),
        "score": report.get("score"),
        "strategy": report.get("strategy"),
        "artifact": report.get("artifact"),
        "execution_plan": report.get("execution_plan"),
    }


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "PocketPortBridge/2"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _path(self) -> str:
        return urlsplit(self.path).path

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")

        allowed_origin = _allowed_origin(self.headers.get("Origin"))
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "content-type")

        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin and _allowed_origin(origin) is None:
            self._send_json(403, {"error": "origin not allowed", "code": "origin_denied"})
            return False
        return True

    def _read_json(self) -> dict[str, object] | None:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self._send_json(400, {"error": "invalid Content-Length", "code": "invalid_request"})
            return None

        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._send_json(
                413 if length > MAX_REQUEST_BYTES else 400,
                {"error": "request body is missing or too large", "code": "invalid_request"},
            )
            return None

        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "request body must be JSON", "code": "invalid_request"})
            return None

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "request body must be an object", "code": "invalid_request"})
            return None
        return payload

    def do_OPTIONS(self) -> None:
        if self._path() not in {"/health", "/api/health", "/api/plan"}:
            self._send_json(404, {"error": "not found", "code": "not_found"})
            return
        if not self._origin_allowed():
            return
        self._send_json(204, {})

    def do_GET(self) -> None:
        if self._path() not in {"/health", "/api/health"}:
            self._send_json(404, {"error": "not found", "code": "not_found"})
            return
        if not self._origin_allowed():
            return
        self._send_json(200, health_payload())

    def do_POST(self) -> None:
        if self._path() != "/api/plan":
            self._send_json(405, {
                "error": "only the read-only planning endpoint accepts POST",
                "code": "method_not_allowed",
            })
            return
        if not self._origin_allowed():
            return

        payload = self._read_json()
        if payload is None:
            return
        repository = payload.get("repository")
        if not isinstance(repository, str):
            self._send_json(400, {"error": "repository is required", "code": "invalid_repository"})
            return

        try:
            result = _local_plan(repository)
        except LiveScanError as exc:
            self._send_json(exc.status, {"error": str(exc), "code": exc.code})
            return
        except Exception:
            self._send_json(500, {"error": "local planning failed unexpectedly", "code": "internal_error"})
            return

        self._send_json(200, result)


def create_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    server = ThreadingHTTPServer((DEFAULT_HOST, port), BridgeHandler)
    server.daemon_threads = True
    return server


def serve(port: int = DEFAULT_PORT) -> None:
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")

    server = create_server(port)
    actual_port = server.server_address[1]
    print(f"[PocketPort] local bridge: http://{DEFAULT_HOST}:{actual_port}")
    print("[PocketPort] read-only health + planning API enabled; Ctrl+C to stop")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n[PocketPort] local bridge stopped")
    finally:
        server.server_close()
