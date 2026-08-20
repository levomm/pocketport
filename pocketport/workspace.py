from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shlex
import shutil
import tempfile

from .components import assess_components
from .execution import ExecutionPlan, build_execution_plan
from .live_scan import _download_archive, _extract_archive, normalize_public_github_url
from .semantics import semantic_scan


def _relative_cd(path: str) -> str:
    if path in {"", "."}:
        return ""
    return f"cd {shlex.quote(path)}\n"


def render_install_script(plan: ExecutionPlan) -> str:
    install = "\n".join(plan.install)
    install_cd = _relative_cd(plan.install_directory)
    next_steps: list[str] = []
    if plan.run:
        next_steps.append(f"cd {plan.working_directory}" if plan.working_directory not in {"", "."} else "cd .")
        next_steps.extend(plan.run)
    else:
        next_steps.append("PocketPort did not infer a trustworthy launch command for this repository.")

    next_text = "\n".join(f"  {line}" for line in next_steps)
    return f'''#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"

if [ -z "${{PREFIX:-}}" ] || [[ "${{PREFIX}}" != *"com.termux"* ]]; then
  echo "This installer is intended to run inside Termux." >&2
  exit 2
fi

echo "[PocketPort] local prepared workspace"
echo "[PocketPort] method={plan.method} status={plan.status}"

{install_cd}{install}

echo
echo "[PocketPort] install phase complete"
echo "Next:"
cat <<'EOF'
{next_text}
EOF
'''


def render_run_script(plan: ExecutionPlan) -> str | None:
    if not plan.run:
        return None
    working_cd = _relative_cd(plan.working_directory)
    commands = "\n".join(plan.run)
    return f'''#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
{working_cd}{commands}
'''


def prepare_public_github(repository: str, *, home: Path | None = None) -> dict[str, object]:
    repo = normalize_public_github_url(repository)
    base = (home or Path.home()) / ".pocketport" / "workspaces"
    base.mkdir(parents=True, exist_ok=True)
    try:
        base.chmod(0o700)
    except OSError:
        pass

    workspace = Path(tempfile.mkdtemp(prefix=f"{repo.owner}-{repo.repo}-", dir=base))
    archive = workspace / "repo.tar.gz"
    root = workspace / "repo"

    try:
        _download_archive(repo, archive)
        _extract_archive(archive, root)
        try:
            archive.unlink()
        except OSError:
            pass

        report, artifact = semantic_scan(root)
        plan = build_execution_plan(report, root)
        components = assess_components(root, report.findings)

        metadata = root / ".pocketport"
        metadata.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict()
        payload["artifact"] = artifact.to_dict()
        if components:
            payload["components"] = [asdict(component) for component in components]
        payload["execution_plan"] = plan.to_dict()
        payload["repository"] = repo.url

        (metadata / "report.json").write_text(json.dumps(payload, indent=2), "utf-8")
        (metadata / "execution-plan.json").write_text(json.dumps(plan.to_dict(), indent=2), "utf-8")

        installer = root / "termux-install.sh"
        installer.write_text(render_install_script(plan), "utf-8")
        installer.chmod(0o755)

        runner_path: Path | None = None
        runner = render_run_script(plan)
        if runner is not None:
            runner_path = root / "termux-run.sh"
            runner_path.write_text(runner, "utf-8")
            runner_path.chmod(0o755)

        return {
            "ok": True,
            "repository": repo.url,
            "workspace": str(workspace),
            "repo_root": str(root),
            "installer": str(installer),
            "runner": str(runner_path) if runner_path else None,
            "execution_plan": plan.to_dict(),
        }
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
