from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import PackageNotFoundError, version
import json
import os
import platform
from urllib.parse import urlsplit

from .release import normalize_arch


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 33343
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
        "api": 1,
        "binding": "loopback",
        "version": _package_version(),
        "termux": "com.termux" in prefix,
        "arch": normalize_arch(platform.machine()),
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


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "PocketPortBridge/1"

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
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
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

    def do_OPTIONS(self) -> None:
        if self._path() not in {"/health", "/api/health"}:
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
        self._send_json(405, {
            "error": "local bridge is read-only in API v1",
            "code": "method_not_allowed",
        })


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
    print("[PocketPort] read-only health API enabled; Ctrl+C to stop")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n[PocketPort] local bridge stopped")
    finally:
        server.server_close()
