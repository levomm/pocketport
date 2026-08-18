from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .scanner import Finding, _score, _strategy


COMPONENT_ROLES = {
    "cli": "client",
    "client": "client",
    "frontend": "client",
    "web": "client",
    "server": "service",
    "api": "service",
    "backend": "service",
    "worker": "service",
    "daemon": "service",
    "service": "service",
    "app": "application",
}

MARKER_STACK = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker-compose",
    "docker-compose.yaml": "docker-compose",
    "compose.yml": "docker-compose",
    "compose.yaml": "docker-compose",
}

IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "tests", "test", "docs", ".pocketport",
}


@dataclass
class ComponentAssessment:
    name: str
    role: str
    path: str
    stack: list[str]
    score: int
    strategy: str


def _iter_markers(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in MARKER_STACK:
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        yield path


def _nearest_named_component(path: Path, root: Path) -> Path | None:
    current = path
    while current != root:
        if current.name.lower() in COMPONENT_ROLES:
            return current
        current = current.parent
    return None


def _relative_component(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def _owns_path(component_path: str, finding_path: str, component_paths: list[str]) -> bool:
    matches = [
        candidate
        for candidate in component_paths
        if finding_path == candidate or finding_path.startswith(f"{candidate}/")
    ]
    if not matches:
        return False
    return component_path == max(matches, key=len)


def assess_components(root: Path, findings: list[Finding]) -> list[ComponentAssessment]:
    root = root.resolve()
    marker_owners: dict[str, list[str]] = {}
    roles: dict[str, str] = {}

    for marker in _iter_markers(root):
        marker_name = marker.name
        stack_name = MARKER_STACK[marker_name]

        if stack_name == "docker-compose":
            component_dir = marker.parent
            role = "service-stack"
        else:
            component_dir = _nearest_named_component(marker.parent, root)
            if component_dir is None:
                continue
            role = COMPONENT_ROLES.get(component_dir.name.lower(), "component")

        rel = _relative_component(component_dir, root)
        roles[rel] = "service-stack" if stack_name == "docker-compose" else roles.get(rel, role)
        stacks = marker_owners.setdefault(rel, [])
        if stack_name not in stacks:
            stacks.append(stack_name)

    component_paths = sorted(marker_owners, key=lambda item: (item.count("/"), item))
    assessments: list[ComponentAssessment] = []

    for component_path in component_paths:
        local_findings = [
            finding
            for finding in findings
            if finding.path is not None and _owns_path(component_path, finding.path, component_paths)
        ]
        stack = marker_owners[component_path]

        # Scanner-level Docker findings describe the whole repository. Recreate
        # those facts locally so component scores explain which surface actually
        # needs adaptation instead of making every sibling look container-bound.
        if "docker-compose" in stack:
            local_findings.append(Finding(
                "high",
                "runtime",
                "Docker Compose requires adaptation; no normal Docker daemon in stock Termux.",
                component_path,
                "runtime",
            ))
        if "docker" in stack:
            local_findings.append(Finding(
                "medium",
                "runtime",
                "Dockerfile found. PRoot-Distro can be a daemonless fallback.",
                component_path,
                "build",
            ))

        assessments.append(ComponentAssessment(
            name=Path(component_path).name,
            role=roles[component_path],
            path=component_path,
            stack=stack,
            score=_score(local_findings),
            strategy=_strategy(local_findings, stack),
        ))

    return assessments
