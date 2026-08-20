from __future__ import annotations

from pocketport.execution import ExecutionComponent, ExecutionPlan
from pocketport.workspace import render_install_script, render_run_script


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        status="ready",
        target={"platform": "android", "termux": True, "arch": "aarch64"},
        component=ExecutionComponent("cli", "client", "apps/cli", ["node"], 99, "native"),
        method="source",
        install_directory=".",
        working_directory="apps/cli",
        install=["npm install"],
        run=["pocketport run -- npm start"],
        compatibility=["pocketport-run"],
        notes=[],
    )


def test_install_script_installs_but_does_not_launch_project() -> None:
    script = render_install_script(_plan())
    assert "npm install" in script
    assert "[PocketPort] install phase complete" in script
    assert "pocketport run -- npm start" in script
    assert "cat <<'EOF'" in script
    assert script.index("cat <<'EOF'") < script.index("pocketport run -- npm start")


def test_run_script_enters_component_and_runs_through_pocketport() -> None:
    script = render_run_script(_plan())
    assert script is not None
    assert "cd apps/cli" in script
    assert "pocketport run -- npm start" in script


def test_no_runner_is_generated_without_trustworthy_run_command() -> None:
    plan = _plan()
    plan.run = []
    assert render_run_script(plan) is None
