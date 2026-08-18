from pathlib import Path

from pocketport.execution import build_execution_plan
from pocketport.scanner import ScanReport, scan


def test_node_bin_becomes_real_run_command_when_target_exists(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"@demo/tool","bin":"./dist/cli.js","scripts":{"build":"node build.js"}}',
        "utf-8",
    )
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "cli.js").write_text("console.log('ok')\n", "utf-8")

    report = scan(tmp_path)
    plan = build_execution_plan(report, tmp_path)

    assert plan.status == "ready"
    assert plan.method == "source"
    assert plan.component.path == "."
    assert plan.run == ["pocketport run -- npx --no-install tool"]
    assert any("npm" in command for command in plan.install)


def test_missing_node_bin_target_is_not_called_runnable(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"@demo/tool","bin":{"tool":"lib/bin.js"}}',
        "utf-8",
    )

    plan = build_execution_plan(scan(tmp_path), tmp_path)

    assert plan.status == "installable"
    assert plan.run == []


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


def test_launchable_cli_beats_higher_scored_library_and_uses_workspace_root(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"workspace","private":true,"packageManager":"pnpm@11.7.0"}',
        "utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", "utf-8")

    cli = tmp_path / "apps" / "cli"
    (cli / "lib").mkdir(parents=True)
    (cli / "package.json").write_text(
        '{"name":"@demo/dsh","bin":{"dsh":"lib/bin.js"}}',
        "utf-8",
    )
    (cli / "lib" / "bin.js").write_text("console.log('dsh')\n", "utf-8")

    client = tmp_path / "packages" / "client"
    client.mkdir(parents=True)
    (client / "package.json").write_text('{"name":"@demo/client"}', "utf-8")

    plan = build_execution_plan(scan(tmp_path), tmp_path)

    assert plan.component.path == "apps/cli"
    assert plan.install_directory == "."
    assert plan.working_directory == "apps/cli"
    assert plan.run == ["pocketport run -- npx --no-install dsh"]
    assert any("pnpm install --frozen-lockfile" in command for command in plan.install)
    assert any("workspace root" in note for note in plan.notes)


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
    assert plan.install_directory == "."
    assert plan.run == []
    assert "proot" in plan.compatibility
    assert "proot-distro install ubuntu:24.04" in plan.install
