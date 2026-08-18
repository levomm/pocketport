from pathlib import Path

from pocketport.execution import build_execution_plan
from pocketport.scanner import ScanReport, scan


def test_node_bin_becomes_real_run_command(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"@demo/tool","bin":"./dist/cli.js","scripts":{"build":"node build.js"}}',
        "utf-8",
    )

    report = scan(tmp_path)
    plan = build_execution_plan(report, tmp_path)

    assert plan.status == "ready"
    assert plan.method == "source"
    assert plan.component.path == "."
    assert plan.run == ["pocketport run -- npx --no-install tool"]
    assert any("npm" in command for command in plan.install)


def test_python_project_script_becomes_run_command(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """[project]\nname = \"demo\"\nversion = \"0.1\"\n\n[project.scripts]\ndemo = \"demo.cli:main\"\n""",
        "utf-8",
    )

    plan = build_execution_plan(scan(tmp_path), tmp_path)

    assert plan.status == "ready"
    assert plan.run == ["pocketport run -- demo"]
    assert any("python -m pip install ." in command for command in plan.install)


def test_best_runnable_component_beats_docker_service(tmp_path: Path) -> None:
    cli = tmp_path / "app" / "cli"
    cli.mkdir(parents=True)
    (cli / "go.mod").write_text("module example.com/demo\n\ngo 1.23\n", "utf-8")
    (cli / "main.go").write_text("package main\nfunc main() {}\n", "utf-8")

    server = tmp_path / "app" / "server"
    server.mkdir(parents=True)
    (server / "Dockerfile").write_text("FROM ubuntu:24.04\n", "utf-8")

    plan = build_execution_plan(scan(tmp_path), tmp_path)

    assert plan.component.name == "cli"
    assert plan.component.path == "app/cli"
    assert plan.component.strategy == "native"
    assert plan.run == ["pocketport run -- go run ."]


def test_unknown_launch_command_is_not_invented(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name":"library-only"}', "utf-8")

    plan = build_execution_plan(scan(tmp_path), tmp_path)

    assert plan.status == "installable"
    assert plan.run == []
    assert any("did not find a trustworthy launch command" in note for note in plan.notes)


def test_proot_plan_stays_explicitly_fallback(tmp_path: Path) -> None:
    report = ScanReport(
        path=str(tmp_path),
        stack=["unknown"],
        score=20,
        strategy="proot",
        findings=[],
    )

    plan = build_execution_plan(report, tmp_path)

    assert plan.status == "fallback"
    assert plan.method == "proot"
    assert plan.run == []
    assert "proot" in plan.compatibility
    assert "proot-distro install ubuntu:24.04" in plan.install
