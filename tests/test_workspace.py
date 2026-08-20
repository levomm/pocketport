from __future__ import annotations

import json

from pocketport.execution import ExecutionComponent, ExecutionPlan
from pocketport.workspace import _repository_has_node_dependency, render_install_script, render_run_script


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        status="ready",
        target={"platform": "android", "termux": True, "arch": "aarch64"},
        component=ExecutionComponent("cli", "client", "apps/cli", ["node"], 99, "native"),
        method="source",
        install_directory=".",
        working_directory="apps/cli",
        install=["pkg update -y", "pkg install -y git nodejs-lts clang make pkg-config python", "npm install"],
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


def test_install_script_prefers_termux_toolchain_before_package_manager_runs() -> None:
    script = render_install_script(_plan())
    path_export = 'export PATH="${PREFIX}/bin:${PATH:-}"'
    assert path_export in script
    assert "hash -r" in script
    assert "export POCKETPORT_TERMUX_TOOLCHAIN=1" in script
    assert script.index(path_export) < script.index("npm install")


def test_install_script_sets_android_native_target_without_overriding_explicit_target() -> None:
    script = render_install_script(_plan())
    assert 'getprop ro.build.version.sdk' in script
    assert 'aarch64-linux-android30' in script
    assert 'armv7a-linux-androideabi30' in script
    assert 'x86_64-linux-android30' in script
    assert 'i686-linux-android30' in script
    assert 'POCKETPORT_ANDROID_API" -ge 30' in script
    assert 'export POCKETPORT_ANDROID_NATIVE_TARGET="$POCKETPORT_ANDROID_TARGET"' in script
    assert 'export CFLAGS="${CFLAGS:+$CFLAGS }-target $POCKETPORT_ANDROID_TARGET"' in script
    assert 'export CXXFLAGS="${CXXFLAGS:+$CXXFLAGS }-target $POCKETPORT_ANDROID_TARGET"' in script
    assert '*" -target "*|*" --target"*)' in script
    assert script.index("POCKETPORT_ANDROID_TARGET") < script.index("npm install")


def test_sharp_compat_installs_libvips_before_node_dependencies() -> None:
    script = render_install_script(_plan(), sharp_compat=True)
    assert "pkg install -y libvips pkg-config" in script
    assert "export SHARP_FORCE_GLOBAL_LIBVIPS=1" in script
    assert script.index("pkg update -y") < script.index("pkg install -y libvips pkg-config")
    assert script.index("pkg install -y libvips pkg-config") < script.index("npm install")


def test_node_dependency_detection_finds_nested_sharp(tmp_path) -> None:
    package = tmp_path / "packages" / "images" / "package.json"
    package.parent.mkdir(parents=True)
    package.write_text(json.dumps({"dependencies": {"sharp": "^0.35.3"}}), "utf-8")
    assert _repository_has_node_dependency(tmp_path, "sharp") is True


def test_node_dependency_detection_ignores_node_modules(tmp_path) -> None:
    package = tmp_path / "node_modules" / "sharp-wrapper" / "package.json"
    package.parent.mkdir(parents=True)
    package.write_text(json.dumps({"dependencies": {"sharp": "^0.35.3"}}), "utf-8")
    assert _repository_has_node_dependency(tmp_path, "sharp") is False


def test_run_script_enters_component_and_runs_through_pocketport() -> None:
    script = render_run_script(_plan())
    assert script is not None
    assert "cd apps/cli" in script
    assert "pocketport run -- npm start" in script


def test_run_script_forwards_user_arguments_to_package_manager_script() -> None:
    script = render_run_script(_plan())
    assert script is not None
    assert 'if [ "$#" -gt 0 ]; then' in script
    assert 'pocketport run -- npm start -- "$@"' in script


def test_run_script_keeps_no_argument_launch_unchanged() -> None:
    script = render_run_script(_plan())
    assert script is not None
    assert "else\n  pocketport run -- npm start\nfi" in script


def test_pnpm_run_runner_uses_argument_separator() -> None:
    plan = _plan()
    plan.run = ["pocketport run -- pnpm run dsh"]
    script = render_run_script(plan)
    assert script is not None
    assert 'pocketport run -- pnpm run dsh -- "$@"' in script


def test_plain_cli_runner_forwards_arguments_without_extra_separator() -> None:
    plan = _plan()
    plan.run = ["pocketport run -- my-cli"]
    script = render_run_script(plan)
    assert script is not None
    assert 'pocketport run -- my-cli "$@"' in script
    assert 'my-cli -- "$@"' not in script


def test_cargo_runner_uses_application_argument_separator() -> None:
    plan = _plan()
    plan.run = ["pocketport run -- cargo run --release"]
    script = render_run_script(plan)
    assert script is not None
    assert 'pocketport run -- cargo run --release -- "$@"' in script


def test_no_runner_is_generated_without_trustworthy_run_command() -> None:
    plan = _plan()
    plan.run = []
    assert render_run_script(plan) is None
