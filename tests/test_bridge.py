from __future__ import annotations

import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from pocketport.bridge import DEFAULT_HOST, create_server


def _running_server():
    server = create_server(0)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    return server, thread


def _url(server, path: str = "/health") -> str:
    return f"http://{DEFAULT_HOST}:{server.server_address[1]}{path}"


def test_bridge_binds_loopback_and_returns_health() -> None:
    server, thread = _running_server()
    try:
        assert server.server_address[0] == DEFAULT_HOST
        with urlopen(_url(server), timeout=2) as response:
            payload = json.load(response)
        assert payload["ok"] is True
        assert payload["service"] == "pocketport-local-bridge"
        assert payload["binding"] == "loopback"
        assert payload["api"] == 1
        assert isinstance(payload["arch"], str)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_production_ui_origin_gets_cors_grant() -> None:
    server, thread = _running_server()
    try:
        request = Request(_url(server), headers={"Origin": "https://pocketport.vercel.app"})
        with urlopen(request, timeout=2) as response:
            assert response.headers["Access-Control-Allow-Origin"] == "https://pocketport.vercel.app"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_untrusted_origin_is_rejected() -> None:
    server, thread = _running_server()
    try:
        request = Request(_url(server), headers={"Origin": "https://evil.example"})
        with pytest.raises(HTTPError) as exc:
            urlopen(request, timeout=2)
        assert exc.value.code == 403
        payload = json.loads(exc.value.read())
        assert payload["code"] == "origin_denied"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bridge_has_no_state_changing_endpoint() -> None:
    server, thread = _running_server()
    try:
        request = Request(
            _url(server, "/api/run"),
            data=b'{}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(request, timeout=2)
        assert exc.value.code == 405
        payload = json.loads(exc.value.read())
        assert payload["code"] == "method_not_allowed"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_invalid_port_is_rejected() -> None:
    with pytest.raises(ValueError):
        create_server(-1)
    with pytest.raises(ValueError):
        create_server(65536)
