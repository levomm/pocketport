import errno
import os
from pathlib import Path

import pocketport.doctor as doctor


def test_native_hardlink_permission_denial_is_reported(tmp_path: Path, monkeypatch):
    def deny_link(source, target):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(doctor.os, "link", deny_link)
    result = doctor._probe_native_hardlink(tmp_path)

    assert result.name == "native hardlink"
    assert result.status == "denied"
    assert "Permission denied" in result.detail


def test_native_hardlink_falls_back_to_ln_when_os_link_missing(tmp_path: Path, monkeypatch):
    monkeypatch.delattr(doctor.os, "link", raising=False)
    monkeypatch.setattr(doctor.shutil, "which", lambda name, path=None: "/usr/bin/ln" if name == "ln" else None)

    class Result:
        returncode = 1
        stderr = "ln: failed to create hard link: Permission denied"
        stdout = ""

    monkeypatch.setattr(doctor.subprocess, "run", lambda *args, **kwargs: Result())
    result = doctor._probe_native_hardlink(tmp_path)

    assert result.name == "native hardlink"
    assert result.status == "denied"
    assert "Permission denied" in result.detail


def test_non_termux_shim_probe_is_not_needed(tmp_path: Path):
    env = dict(os.environ)
    env["PREFIX"] = "/usr"

    result = doctor._probe_node_atomic_publish_shim(tmp_path, env)

    assert result.name == "PocketPort Node shim"
    assert result.status == "not-needed"


def test_termux_runtime_summary_marks_sandbox_project_specific(tmp_path: Path, monkeypatch):
    ok = doctor.RuntimeCapability("probe", "ok", "test")
    monkeypatch.setattr(doctor, "_probe_native_hardlink", lambda root: ok)
    monkeypatch.setattr(doctor, "_probe_node_exclusive_copy", lambda root, env: ok)
    monkeypatch.setattr(doctor, "_probe_node_atomic_publish_shim", lambda root, env: ok)
    env = dict(os.environ)
    env["PREFIX"] = "/data/data/com.termux/files/usr"

    capabilities = doctor.inspect_runtime_capabilities(env, home=tmp_path)
    sandbox = capabilities[-1]

    assert sandbox.name == "sandbox confinement"
    assert sandbox.status == "project-specific"
    assert "approval" in sandbox.detail
