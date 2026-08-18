from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from .components import ComponentAssessment, assess_components
from .generator import _native_commands
from .scanner import Finding, ScanReport


@dataclass
class ExecutionComponent:
    name: str
    role: str
    path: str
    stack: list[str]
    score: int
    strategy: str


@dataclass
class ExecutionPlan:
    status: str
    target: dict[str, object]
    component: ExecutionComponent
    method: str
    install_directory: str
    working_directory: str
    install: list[str]
    run: list[str]
    compatibility: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


ROLE_PRIORITY = {
    "client": 5,
    "application": 4,
    "service": 3,
    "component": 2,
    "service-stack": 1,
    "repository": 0,
}

SURFACE_PRIORITY = {
    "cli": 5,
    "client": 4,
    "app": 3,
    "web": 2,
    "api": 1,
    "server": 0,
}

STRATEGY_PRIORITY = {
    "native": 3,
    "hybrid": 2,
    "proot": 1,
}

NODE_WORKSPACE_MARKERS = {
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
}


def _as_execution_component(component: ComponentAssessment) -> ExecutionComponent:
    return ExecutionComponent(
        name=component.name,
        role=component.role,
        path=component.path,
        stack=list(component.stack),
        score=component.score,
        strategy=component.strategy,
    )


def _component_root(root: Path, component: ExecutionComponent) -> Path:
    if component.path in {"", "."}:
        return root
    return root / component.path


def _relative(root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    return "." if not rel.parts else rel.as_posix()


def _read_package_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _node_package_manager(path: Path) -> str:
    package = _read_package_json(path / "package.json")
    package_manager = str(package.get("packageManager", ""))
    if package_manager.startswith("pnpm@") or (path / "pnpm-lock.yaml").exists():
        return "pnpm"
    return "npm"


def _node_workspace_root(root: Path, component_root: Path) -> Path:
    current = component_root.resolve()
    root = root.resolve()
    while True:
        package = _read_package_json(current / "package.json")
        package_manager = str(package.get("packageManager", ""))
        if package_manager or any((current / marker).exists() for marker in NODE_WORKSPACE_MARKERS):
            return current
        if current == root:
            return component_root
        if root not in current.parents:
            return component_root
        current = current.parent


def _node_run_command(component_root: Path, component: ExecutionComponent) -> str | None:
    package = _read_package_json(component_root / "package.json")
    if not package:
        return None

    package_manager = _node_package_manager(component_root)
    bin_value = package.get("bin")
    bin_name: str | None = None
    bin_target: str | None = None

    if isinstance(bin_value, str):
        package_name = str(package.get("name", "")).strip()
        if package_name:
            bin_name = package_name.rsplit("/", 1)[-1]
            bin_target = bin_value
    elif isinstance(bin_value, dict):
        entries = [
            (str(name), str(target))
            for name, target in bin_value.items()
            if isinstance(name, str) and isinstance(target, str)
        ]
        if entries:
            chosen = next((entry for entry in entries if entry[0] == component.name), None)
            if chosen is None:
                chosen = sorted(entries)[0]
            bin_name, bin_target = chosen

    if bin_name and bin_target and (component_root / bin_target).is_file():
        if package_manager == "pnpm":
            return f"pnpm exec {bin_name}"
        return f"npx --no-install {bin_name}"

    scripts = package.get("scripts")
    if isinstance(scripts, dict) and isinstance(scripts.get("start"), str):
        return "pnpm run start" if package_manager == "pnpm" else "npm run start"
    return None


def _python_script_name(component_root: Path) -> str | None:
    pyproject = component_root / "pyproject.toml"
    try:
        lines = pyproject.read_text("utf-8").splitlines()
    except OSError:
        return None

    in_scripts = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_scripts = stripped == "[project.scripts]"
            continue
        if not in_scripts or not stripped or stripped.startswith("#"):
            continue
        match = re.match(r'^(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z0-9_.-]+))\s*=\s*', stripped)
        if match:
            return next(group for group in match.groups() if group)
    return None


def _go_run_command(component_root: Path) -> str | None:
    root_main = component_root / "main.go"
    try:
        text = root_main.read_text("utf-8", errors="ignore")
    except OSError:
        text = ""
    if re.search(r"(?m)^\s*package\s+main\b", text) and re.search(r"\bfunc\s+main\s*\(", text):
        return "go run ."

    cmd_root = component_root / "cmd"
    if cmd_root.is_dir():
        candidates: list[Path] = []
        for main_go in cmd_root.glob("*/main.go"):
            try:
                source = main_go.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            if re.search(r"(?m)^\s*package\s+main\b", source) and re.search(r"\bfunc\s+main\s*\(", source):
                candidates.append(main_go.parent)
        if len(candidates) == 1:
            rel = candidates[0].relative_to(component_root).as_posix()
            return f"go run ./{rel}"
    return None


def _rust_run_command(component_root: Path) -> str | None:
    if (component_root / "Cargo.toml").exists() and (component_root / "src" / "main.rs").exists():
        return "cargo run --release"
    return None


def _detect_run_command(component_root: Path, component: ExecutionComponent) -> str | None:
    stack = set(component.stack)
    if "node" in stack:
        command = _node_run_command(component_root, component)
        if command:
            return command
    if "python" in stack:
        command = _python_script_name(component_root)
        if command:
            return command
    if "rust" in stack:
        command = _rust_run_command(component_root)
        if command:
            return command
    if "go" in stack:
        command = _go_run_command(component_root)
        if command:
            return command
    return None


def _component_key(component: ComponentAssessment, root: Path) -> tuple[int, int, int, int, int, int]:
    execution = _as_execution_component(component)
    component_root = _component_root(root, execution)
    launchable = int(_detect_run_command(component_root, execution) is not None)
    return (
        launchable,
        STRATEGY_PRIORITY.get(component.strategy, 0),
        ROLE_PRIORITY.get(component.role, 0),
        SURFACE_PRIORITY.get(component.name.lower(), 0),
        component.score,
        -component.path.count("/"),
    )


def _select_component(report: ScanReport, root: Path) -> ExecutionComponent:
    components = assess_components(root, report.findings)
    if components:
        chosen = max(components, key=lambda component: _component_key(component, root))
        return _as_execution_component(chosen)

    return ExecutionComponent(
        name=root.name or "repository",
        role="repository",
        path=".",
        stack=list(report.stack),
        score=report.score,
        strategy=report.strategy,
    )


def _install_root(root: Path, component_root: Path, component: ExecutionComponent) -> Path:
    if "node" in component.stack:
        return _node_workspace_root(root, component_root)
    return component_root


def _component_findings(report: ScanReport, component: ExecutionComponent) -> list[Finding]:
    if component.path in {"", "."}:
        return list(report.findings)
    prefix = component.path.rstrip("/") + "/"
    return [
        finding
        for finding in report.findings
        if finding.path is not None and (finding.path == component.path or finding.path.startswith(prefix))
    ]


def _compatibility_actions(report: ScanReport, component: ExecutionComponent) -> tuple[list[str], list[str]]:
    findings = _component_findings(report, component)
    compatibility = ["pocketport-run"]
    notes: list[str] = []

    if any(f.kind == "patchable" and f.scope == "runtime" for f in findings):
        compatibility.append("source-patch")
        notes.append("Runtime source contains Termux-patchable assumptions; `pocketport prepare` may be needed before launch.")
    if any(f.kind in {"node-native", "python-native"} and f.scope in {"runtime", "optional"} for f in findings):
        compatibility.append("native-dependencies")
        notes.append("Native dependencies must install or build successfully on the target Termux environment.")
    if component.strategy == "hybrid":
        compatibility.append("proot-fallback")
        notes.append("Native execution is preferred, but this component may still need the PRoot fallback path.")
    elif component.strategy == "proot":
        compatibility.append("proot")
        notes.append("This component is planned through PRoot rather than direct Termux execution.")

    return compatibility, notes


def _proot_install_commands() -> list[str]:
    return [
        "pkg update -y",
        "pkg install -y proot-distro git",
        "proot-distro install ubuntu:24.04",
    ]


def build_execution_plan(report: ScanReport, root: Path) -> ExecutionPlan:
    root = root.resolve()
    component = _select_component(report, root)
    component_root = _component_root(root, component)
    install_root = _install_root(root, component_root, component)
    compatibility, notes = _compatibility_actions(report, component)

    if component.strategy == "proot":
        return ExecutionPlan(
            status="fallback",
            target={"platform": "android", "termux": True, "arch": "aarch64"},
            component=component,
            method="proot",
            install_directory=".",
            working_directory=component.path,
            install=_proot_install_commands(),
            run=[],
            compatibility=compatibility,
            notes=notes + ["Launch command inside the Linux fallback is not inferred until PocketPort can prove it from project metadata."],
        )

    component_report = ScanReport(
        path=str(install_root),
        stack=list(component.stack),
        score=component.score,
        strategy=component.strategy,
        findings=_component_findings(report, component),
    )
    install = _native_commands(component_report, install_root)
    run_command = _detect_run_command(component_root, component)
    run = [f"pocketport run -- {run_command}"] if run_command else []
    status = "ready" if run else "installable"

    install_directory = _relative(root, install_root)
    if install_root != component_root:
        notes.append(f"Dependencies are installed from workspace root `{install_directory}` before entering `{component.path}`.")
    if not run:
        notes.append("Install path is known, but PocketPort did not find a trustworthy launch command in project metadata.")

    return ExecutionPlan(
        status=status,
        target={"platform": "android", "termux": True, "arch": "aarch64"},
        component=component,
        method="source",
        install_directory=install_directory,
        working_directory=component.path,
        install=install,
        run=run,
        compatibility=compatibility,
        notes=notes,
    )
