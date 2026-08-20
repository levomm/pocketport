from __future__ import annotations

import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

import pocketport.bridge as bridge
from pocketport.bridge import DEFAULT_HOST, create_server


def _running_server():
    server = create_server(0)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    return server, thread


def _url(server, path: str = "/health") -> str:
    return f"http://{DEFAULT_HOST}:{server.server_address[1]}{path}"


def _post(server, path: str, payload: dict, *, origin: str = "https://pocketport.vercel.app"):
    return Request(
        _url(server, path),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )


def test_bridge_binds_loopback_and_returns_health() -> None:
    server, thread = _running_server()
    try:
        assert server.server_address[0] == DEFAULT_HOST
        with urlopen(_url(server), timeout=2) as response:
            payload = json.load(response)
        assert payload["ok"] is True
        assert payload["service"] == "pocketport-local-bridge"
        assert payload["binding"] == "loopback"
        assert payload["api"] == 3
        assert payload["capabilities"] == ["health", "local-plan", "prepare-workspace"]
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


def test_local_plan_endpoint_returns_core_plan(monkeypatch) -> None:
    expected = {
        "ok": True,
        "service": "pocketport-local-bridge",
        "api": 3,
        "source": "local-device",
        "repository": "https://github.com/example/project",
        "device": {"arch": "aarch64"},
        "score": 88,
        "strategy": "native",
        "artifact": {"type": "cli"},
        "execution_plan": {"status": "usable", "method": "native", "install": ["npm install"], "run": ["npm start"]},
    }
    monkeypatch.setattr(bridge, "_local_plan", lambda repository: expected)

    server, thread = _running_server()
    try:
        with urlopen(_post(server, "/api/plan", {"repository": "https://github.com/example/project"}), timeout=2) as response:
            payload = json.load(response)
            assert response.headers["Access-Control-Allow-Origin"] == "https://pocketport.vercel.app"
        assert payload == expected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_prepare_endpoint_materializes_only_after_explicit_post(monkeypatch) -> None:
    expected = {
        "ok": True,
        "service": "pocketport-local-bridge",
        "api": 3,
        "source": "local-device",
        "repository": "https://github.com/example/project",
        "workspace": "/tmp/.pocketport/workspaces/example-project-123",
        "repo_root": "/tmp/.pocketport/workspaces/example-project-123/repo",
        "installer": "/tmp/.pocketport/workspaces/example-project-123/repo/termux-install.sh",
        "runner": None,
        "execution_plan": {"status": "installable", "method": "source", "install": ["npm install"], "run": []},
        "device": {"arch": "aarch64"},
    }
    monkeypatch.setattr(bridge, "_prepare_workspace", lambda repository: expected)

    server, thread = _running_server()
    try:
        with urlopen(_post(server, "/api/prepare", {"repository": "https://github.com/example/project"}), timeout=2) as response:
            payload = json.load(response)
        assert payload == expected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_local_post_endpoints_reject_untrusted_origin(monkeypatch) -> None:
    monkeypatch.setattr(bridge, "_local_plan", lambda repository: pytest.fail("planner must not run"))
    monkeypatch.setattr(bridge, "_prepare_workspace", lambda repository: pytest.fail("preparer must not run"))
    server, thread = _running_server()
    try:
        for path in ("/api/plan", "/api/prepare"):
            with pytest.raises(HTTPError) as exc:
                urlopen(_post(server, path, {"repository": "https://github.com/example/project"}, origin="https://evil.example"), timeout=2)
            assert exc.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bridge_has_no_arbitrary_run_endpoint() -> None:
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
