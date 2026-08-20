from __future__ import annotations

import json
from pathlib import Path
import re

from .execution import ExecutionPlan


_SOURCE_ENTRY_RE = re.compile(r"(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:[cm]?[jt]sx?))")


def _read_package(path: Path) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _bin_names(package: dict) -> list[str]:
    value = package.get("bin")
    if isinstance(value, dict):
        return [str(name) for name in value if isinstance(name, str)]
    if isinstance(value, str):
        package_name = str(package.get("name", "")).strip()
        if package_name:
            return [package_name.rsplit("/", 1)[-1]]
    return []


def enrich_workspace_entrypoint(plan: ExecutionPlan, root: Path) -> ExecutionPlan:
    """Promote a proven root workspace script to the plan's run command.

    Some monorepos publish a generated package bin while their source checkout
    exposes the runnable CLI through a root package script. We only accept that
    script when its name matches the selected package bin and its command points
    at an existing source file inside the selected component.
    """
    if plan.run or "node" not in plan.component.stack:
        return plan

    root = root.resolve()
    component_root = root if plan.component.path in {"", "."} else root / plan.component.path
    root_package = _read_package(root / "package.json")
    component_package = _read_package(component_root / "package.json")
    scripts = root_package.get("scripts")
    if not isinstance(scripts, dict):
        return plan

    try:
        relative_component = component_root.resolve().relative_to(root).as_posix()
    except ValueError:
        return plan
    component_prefix = "" if relative_component == "." else relative_component.rstrip("/") + "/"

    manager = (
        "pnpm"
        if str(root_package.get("packageManager", "")).startswith("pnpm@") or (root / "pnpm-lock.yaml").exists()
        else "npm"
    )

    for name in _bin_names(component_package):
        command = scripts.get(name)
        if not isinstance(command, str):
            continue

        referenced = [match.group("path") for match in _SOURCE_ENTRY_RE.finditer(command)]
        proven = False
        for relative in referenced:
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            if (not component_prefix or relative.startswith(component_prefix)) and candidate.is_file():
                proven = True
                break

        if not proven:
            continue

        plan.run = [f"pocketport run -- {manager} run {name}"]
        plan.status = "ready"
        plan.working_directory = "."
        plan.notes.append(
            f"Launch command is proven by root package script `{name}`, which references source inside `{plan.component.path}`."
        )
        return plan

    return plan
