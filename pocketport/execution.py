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

STRATEGY_PRIORITY = {
    "native": 3,
    "hybrid": 2,
    "proot": 1,
}


def _component_key(component: ComponentAssessment) -> tuple[int, int, int, int]:
    return (
        STRATEGY_PRIORITY.get(component.strategy, 0),
        ROLE_PRIORITY.get(component.role, 0),
        component.score,
        -component.path.count("/"),
    )


def _select_component(report: ScanReport, root: Path) -> ExecutionComponent:
    components = assess_components(root, report.findings)
    if components:
        chosen = max(components, key=_component_key)
        return ExecutionComponent(
            name=chosen.name,
            role=chosen.role,
            path=chosen.path,
            stack=list(chosen.stack),
            score=chosen.score,
            strategy=chosen.strategy,
        )

    return ExecutionComponent(
        name=root.name or "repository",
        role="repository",
        path=".",
        stack=list(report.stack),
        score=report.score,
        strategy=report.strategy,
    )


def _component_root(root: Path, component: ExecutionComponent) -> Path:
    if component.path in {"", "."}:
        return root
    return root / component.path


def _node_package_manager(component_root: Path) -> str:
    package_json = component_root / "package.json"
    if package_json.exists():
        try:
            package_manager = str(json.loads(package_json.read_text("utf-8")).get("packageManager", ""))
        except (OSError, json.JSONDecodeError):
            package_manager = ""
        if package_manager.startswith("pnpm@"):
            return "pnpm"
    if (component_root / "pnpm-lock.yaml").exists():
        return "pnpm"
    return "npm"


def _node_run_command(component_root: Path, component: ExecutionComponent) -> str | None:
    package_json = component_root / "package.json"
    try:
        package = json.loads(package_json.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    package_manager = _node_package_manager(component_root)
    bin_value = package.get("bin")
    bin_name: str | None = None
    if isinstance(bin_value, str):
        package_name = str(package.get("name", "")).strip()
        if package_name:
            bin_name = package_name.rsplit("/", 1)[-1]
    elif isinstance(bin_value, dict):
        names = [str(name) for name, target in bin_value.items() if isinstance(target, str)]
        if component.name in names:
            bin_name = component.name
        elif names:
            bin_name = sorted(names)[0]

    if bin_name:
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
    compatibility, notes = _compatibility_actions(report, component)

    if component.strategy == "proot":
        return ExecutionPlan(
            status="fallback",
            target={"platform": "android", "termux": True, "arch": "aarch64"},
            component=component,
            method="proot",
            working_directory=component.path,
            install=_proot_install_commands(),
            run=[],
            compatibility=compatibility,
            notes=notes + ["Launch command inside the Linux fallback is not inferred until PocketPort can prove it from project metadata."],
        )

    component_report = ScanReport(
        path=str(component_root),
        stack=list(component.stack),
        score=component.score,
        strategy=component.strategy,
        findings=_component_findings(report, component),
    )
    install = _native_commands(component_report, component_root)
    run_command = _detect_run_command(component_root, component)
    run = [f"pocketport run -- {run_command}"] if run_command else []
    status = "ready" if run else "installable"
    if not run:
        notes.append("Install path is known, but PocketPort did not find a trustworthy launch command in project metadata.")

    return ExecutionPlan(
        status=status,
        target={"platform": "android", "termux": True, "arch": "aarch64"},
        component=component,
        method="source",
        working_directory=component.path,
        install=install,
        run=run,
        compatibility=compatibility,
        notes=notes,
    )
