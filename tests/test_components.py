from pathlib import Path

from pocketport.components import assess_components
from pocketport.scanner import scan


def test_cli_and_compose_stack_are_assessed_separately(tmp_path: Path):
    cli = tmp_path / "app" / "cli"
    server = tmp_path / "app" / "server"
    cli.mkdir(parents=True)
    server.mkdir(parents=True)

    (cli / "go.mod").write_text("module example/cli\n", encoding="utf-8")
    (cli / "install.sh").write_text("sudo mv tool /usr/local/bin/tool\n", encoding="utf-8")
    (server / "go.mod").write_text("module example/server\n", encoding="utf-8")
    (server / "Dockerfile").write_text("FROM golang:1.23\nRUN apt-get update\n", encoding="utf-8")
    (tmp_path / "app" / "docker-compose.yml").write_text(
        "services:\n  server:\n    build: ./server\n",
        encoding="utf-8",
    )

    report = scan(tmp_path)
    components = assess_components(tmp_path, report.findings)
    by_path = {component.path: component for component in components}

    assert by_path["app/cli"].strategy == "native"
    assert by_path["app/cli"].stack == ["go"]
    assert by_path["app/server"].strategy == "native"
    assert "go" in by_path["app/server"].stack
    assert "docker" in by_path["app/server"].stack
    assert by_path["app"].role == "service-stack"
    assert by_path["app"].strategy == "hybrid"
    assert by_path["app"].stack == ["docker-compose"]


def test_nested_component_owns_its_findings_instead_of_parent_stack(tmp_path: Path):
    cli = tmp_path / "app" / "cli"
    cli.mkdir(parents=True)
    (cli / "go.mod").write_text("module example/cli\n", encoding="utf-8")
    (cli / "install.sh").write_text("sudo cp x /usr/bin/x\n", encoding="utf-8")
    (tmp_path / "app" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    report = scan(tmp_path)
    components = assess_components(tmp_path, report.findings)
    by_path = {component.path: component for component in components}

    assert by_path["app/cli"].score < 100
    assert by_path["app"].score == 75


def test_role_named_fixture_does_not_become_fake_component(tmp_path: Path):
    server = tmp_path / "app" / "server"
    fixture_cli = server / "syntax" / "file_map" / "cli"
    fixture_cli.mkdir(parents=True)

    (server / "go.mod").write_text("module example/server\n", encoding="utf-8")
    (fixture_cli / "go.mod").write_text("module example/fixture-cli\n", encoding="utf-8")

    report = scan(tmp_path)
    components = assess_components(tmp_path, report.findings)
    paths = {component.path for component in components}

    assert "app/server" in paths
    assert "app/server/syntax/file_map/cli" not in paths
