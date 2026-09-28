from __future__ import annotations

import json
from pathlib import Path

from .execution import ExecutionPlan


DEEPSEEK_HARNESS = "deepseek-ai/deepseek-harness"


def _package_version(root: Path, package_path: str) -> str | None:
    try:
        package = json.loads((root / package_path).read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = package.get("version") if isinstance(package, dict) else None
    return version.strip() if isinstance(version, str) and version.strip() else None


def apply_repository_recipe(slug: str, plan: ExecutionPlan, root: Path) -> ExecutionPlan:
    """Apply a validated Android runtime recipe for a known repository.

    Recipes are deliberately narrow. They replace a source-build plan only when
    PocketPort has already validated a materially better Android execution path.
    """
    if slug.lower() != DEEPSEEK_HARNESS:
        return plan

    version = _package_version(root, "apps/cli/package.json")
    package = "@deepseek-ai/dsh" + (f"@{version}" if version else "")

    plan.status = "ready"
    plan.method = "published-package"
    plan.install_directory = "."
    plan.working_directory = "."
    plan.install = [
        "pkg update -y",
        "pkg install -y git nodejs-lts clang make pkg-config python",
        f"npm install -g {package}",
    ]
    plan.run = ["pocketport run -- dsh web --no-open"]

    for marker in ("validated-recipe", "pocketport-run"):
        if marker not in plan.compatibility:
            plan.compatibility.append(marker)

    plan.notes = [
        "PocketPort uses the published @deepseek-ai/dsh runtime instead of building the full monorepo from source on the phone.",
        "This Android/Termux path has been validated end-to-end and avoids the source client build's multi-gigabyte memory requirement.",
        "The DeepSeek Harness Web UI listens on http://127.0.0.1:3080 by default.",
        *plan.notes,
    ]
    return plan
