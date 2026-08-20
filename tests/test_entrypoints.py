from pathlib import Path

from pocketport.entrypoints import enrich_workspace_entrypoint
from pocketport.execution import build_execution_plan
from pocketport.scanner import scan


def _deepseek_like_repo(root: Path, *, script: str) -> None:
    (root / "package.json").write_text(
        '{"name":"workspace","private":true,"packageManager":"pnpm@11.7.0","scripts":{"dsh":' + repr(script).replace("'", '"') + '}}',
        "utf-8",
    )
    (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", "utf-8")
    cli = root / "apps" / "cli"
    (cli / "src").mkdir(parents=True)
    (cli / "package.json").write_text(
        '{"name":"@deepseek-ai/dsh","bin":{"dsh":"lib/bin.js"}}',
        "utf-8",
    )
    (cli / "src" / "bin.ts").write_text("console.log('dsh')\n", "utf-8")


def test_root_script_can_prove_generated_bin_source_entrypoint(tmp_path: Path) -> None:
    _deepseek_like_repo(tmp_path, script="node --import tsx/esm apps/cli/src/bin.ts")

    plan = build_execution_plan(scan(tmp_path), tmp_path)
    assert plan.component.path == "apps/cli"
    assert plan.run == []

    plan = enrich_workspace_entrypoint(plan, tmp_path)

    assert plan.status == "ready"
    assert plan.working_directory == "."
    assert plan.run == ["pocketport run -- pnpm run dsh"]
    assert any("root package script `dsh`" in note for note in plan.notes)


def test_root_script_is_not_trusted_without_component_source_reference(tmp_path: Path) -> None:
    _deepseek_like_repo(tmp_path, script="node scripts/dsh.ts")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "dsh.ts").write_text("console.log('not component')\n", "utf-8")

    plan = enrich_workspace_entrypoint(build_execution_plan(scan(tmp_path), tmp_path), tmp_path)

    assert plan.status == "installable"
    assert plan.run == []
