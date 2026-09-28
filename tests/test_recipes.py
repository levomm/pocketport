from pathlib import Path

from pocketport.execution import ExecutionComponent, ExecutionPlan
from pocketport.recipes import apply_repository_recipe


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        status="ready",
        target={"platform": "android", "termux": True, "arch": "aarch64"},
        component=ExecutionComponent("cli", "client", "apps/cli", ["node"], 70, "native"),
        method="source",
        install_directory=".",
        working_directory=".",
        install=["pnpm install --frozen-lockfile"],
        run=["pocketport run -- pnpm run dsh"],
        compatibility=["pocketport-run"],
        notes=[],
    )


def test_deepseek_harness_uses_published_android_recipe(tmp_path: Path) -> None:
    package = tmp_path / "apps" / "cli" / "package.json"
    package.parent.mkdir(parents=True)
    package.write_text('{"name":"@deepseek-ai/dsh","version":"0.1.7-rc.2"}', "utf-8")

    plan = apply_repository_recipe("deepseek-ai/deepseek-harness", _plan(), tmp_path)

    assert plan.method == "published-package"
    assert plan.status == "ready"
    rendered = "\n".join(plan.install)
    assert "@deepseek-ai/dsh@0.1.7-rc.2" in rendered
    assert "SHARP_FORCE_GLOBAL_LIBVIPS" in rendered
    assert "--expose-internals" in rendered
    assert "deepseek-termux-compat" in plan.compatibility
    assert plan.run == ["pocketport run -- dsh web --no-open"]
    assert "validated-recipe" in plan.compatibility
    assert not any("pnpm install" in command for command in plan.install)


def test_unknown_repository_keeps_generic_plan(tmp_path: Path) -> None:
    original = _plan()
    plan = apply_repository_recipe("example/tool", original, tmp_path)

    assert plan is original
    assert plan.method == "source"
