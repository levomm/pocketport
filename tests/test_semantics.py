from __future__ import annotations

import json
from pathlib import Path

from pocketport.components import assess_components
from pocketport.execution import build_execution_plan
from pocketport.semantics import semantic_scan


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_rust_cli_low_build_scripts_do_not_flip_runtime_verdict(tmp_path: Path) -> None:
    write(tmp_path / "Cargo.toml", "[package]\nname='hyperfine-ish'\nversion='0.1.0'\n")
    write(tmp_path / "src/main.rs", "fn main() {}\n")
    write(tmp_path / "scripts/release.py", "#!/usr/bin/python3\n")

    report, artifact = semantic_scan(tmp_path)
    assert artifact.type == "cli"
    assert report.strategy == "native"
    assert report.score >= 99
    assert all(f.scope != "runtime" for f in report.findings if f.path == "scripts/release.py")


def test_python_cli_ignores_packaging_docker_as_primary_stack(tmp_path: Path) -> None:
    write(tmp_path / "pyproject.toml", "[project]\nname='httpie-ish'\nversion='1'\n[project.scripts]\nhttp='pkg.cli:main'\n")
    write(tmp_path / "extras/packaging/Dockerfile", "FROM debian:stable\nRUN apt-get update\n")
    write(tmp_path / "extras/packaging/docker-compose.yml", "services: {}\n")

    report, artifact = semantic_scan(tmp_path)
    assert artifact.type == "cli"
    assert report.stack == ["python"]
    assert report.strategy == "native"


def test_python_package_without_entrypoint_is_library(tmp_path: Path) -> None:
    write(tmp_path / "pyproject.toml", "[project]\nname='python-fire-ish'\nversion='1'\n")
    write(tmp_path / "src/pkg/__init__.py", "")

    report, artifact = semantic_scan(tmp_path)
    plan = build_execution_plan(report, tmp_path)
    assert artifact.type == "library"
    assert artifact.runnable is False
    assert plan.status == "installable"
    assert plan.run == []
    assert plan.method == "package"


def test_bandwhich_style_privileged_capture_is_not_100_native(tmp_path: Path) -> None:
    write(tmp_path / "Cargo.toml", "[package]\nname='bandwhich-ish'\nversion='1'\n")
    write(tmp_path / "src/main.rs", "fn main() {}\n")
    write(tmp_path / "README.md", "This tool does packet capture and packet sniffing. sudo setcap cap_net_raw,cap_net_admin+ep ./tool\n")

    report, artifact = semantic_scan(tmp_path)
    assert artifact.type == "cli"
    assert report.score < 100
    assert report.strategy == "hybrid"
    assert any(f.kind == "capability" for f in report.findings)
    assert "elevated packet-capture/network privileges" in artifact.requirements


def test_devcontainer_is_never_a_runnable_component(tmp_path: Path) -> None:
    write(tmp_path / "package.json", json.dumps({"name": "electron-ish", "devDependencies": {"electron": "1"}}))
    write(tmp_path / ".devcontainer/docker-compose.yml", "services: {}\n")
    write(tmp_path / ".devcontainer/Dockerfile", "FROM ubuntu\n")

    report, artifact = semantic_scan(tmp_path)
    components = assess_components(tmp_path, report.findings)
    plan = build_execution_plan(report, tmp_path)
    assert artifact.type == "desktop-app"
    assert report.stack == ["node"]
    assert components == []
    assert plan.status == "not-direct"
    assert plan.method == "desktop"
    assert plan.run == []


def test_agent_skill_gets_agent_install_plan_not_process_run(tmp_path: Path) -> None:
    write(tmp_path / "skills/scroll-world/SKILL.md", "# scroll-world\n")
    write(tmp_path / "README.md", "npx skills add oso95/scroll-world -a codex\nInvoke it with $scroll-world.\n")
    write(tmp_path / "skills/scroll-world/references/knockout.py", "#!/usr/bin/python3\n")

    report, artifact = semantic_scan(tmp_path)
    plan = build_execution_plan(report, tmp_path)
    assert artifact.type == "agent-skill"
    assert artifact.runnable is False
    assert plan.method == "agent-skill"
    assert plan.install == ["npx skills add oso95/scroll-world -a codex"]
    assert plan.run == []


def test_root_compose_service_remains_fallback_candidate(tmp_path: Path) -> None:
    write(tmp_path / "package.json", json.dumps({"name": "uptime-ish", "scripts": {"start": "node server/server.js"}}))
    write(tmp_path / "docker-compose.yml", "services:\n  app:\n    image: example\n")
    write(tmp_path / "server/server.js", "console.log('server')\n")

    report, artifact = semantic_scan(tmp_path)
    assert artifact.type == "service"
    assert "docker-compose" in report.stack
    assert report.strategy in {"hybrid", "proot"}
