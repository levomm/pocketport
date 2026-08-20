from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from .scanner import Finding, ScanReport, _score, _strategy, scan as raw_scan


SUPPORT_DIRS = {
    ".git", ".github", ".circleci", ".gitlab", ".devcontainer",
    "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "tests", "test", "testdata", "fixtures", "fixture", "examples", "example",
    "benchmarks", "benchmark", "packaging", "scripts", "script", "tools",
    "extra", "extras", ".pocketport",
}

ROOT_STACK_MARKERS = {
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


@dataclass(frozen=True)
class ArtifactProfile:
    type: str
    runnable: bool
    primary_surface: str
    confidence: str
    requirements: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _read(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="ignore")
    except OSError:
        return ""


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _root_package(root: Path) -> dict:
    return _read_json(root / "package.json")


def _python_has_scripts(root: Path) -> bool:
    return bool(re.search(r"(?m)^\s*\[project\.scripts\]\s*$", _read(root / "pyproject.toml")))


def _node_has_bin(package: dict) -> bool:
    value = package.get("bin")
    return isinstance(value, str) or (isinstance(value, dict) and bool(value))


def _node_has_start(package: dict) -> bool:
    scripts = package.get("scripts")
    return isinstance(scripts, dict) and isinstance(scripts.get("start"), str)


def _node_uses_electron(package: dict) -> bool:
    if str(package.get("name", "")).lower() == "electron":
        return True
    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        deps = package.get(key)
        if isinstance(deps, dict) and "electron" in deps:
            return True
    return False


def _has_go_main(root: Path) -> bool:
    candidates = [root / "main.go"]
    cmd_root = root / "cmd"
    if cmd_root.is_dir():
        candidates.extend(cmd_root.glob("*/main.go"))
    for candidate in candidates:
        text = _read(candidate)
        if re.search(r"(?m)^\s*package\s+main\b", text) and re.search(r"\bfunc\s+main\s*\(", text):
            return True
    return False


def _skill_files(root: Path) -> list[Path]:
    found: list[Path] = []
    direct = root / "SKILL.md"
    if direct.is_file():
        found.append(direct)
    skills = root / "skills"
    if skills.is_dir():
        found.extend(path for path in skills.glob("*/SKILL.md") if path.is_file())
    return found


def _primary_stack(root: Path) -> list[str]:
    stack: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part.lower() in SUPPORT_DIRS for part in rel.parts):
            continue
        name = ROOT_STACK_MARKERS.get(path.name)
        if name and name not in stack:
            stack.append(name)
    return stack or ["unknown"]


def _root_has_compose(root: Path) -> bool:
    return any((root / name).is_file() for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"))


def _root_has_dockerfile(root: Path) -> bool:
    return (root / "Dockerfile").is_file()


def _rescope(path: str | None, current: str) -> str:
    if not path:
        return current
    parts = [part.lower() for part in Path(path).parts]
    if any(part in {".github", ".circleci", ".gitlab"} for part in parts):
        return "ci"
    if any(part in {"tests", "test", "testdata", "fixtures", "fixture", "examples", "example", "benchmarks", "benchmark"} for part in parts):
        return "dev"
    if any(part in {".devcontainer", "packaging", "scripts", "script", "tools", "extra", "extras"} for part in parts):
        return "build"
    return current


def classify_repository(root: Path, stack: list[str] | None = None) -> ArtifactProfile:
    root = root.resolve()
    stack = list(stack or _primary_stack(root))
    package = _root_package(root)
    skill_files = _skill_files(root)
    readme = _read(root / "README.md").lower()

    if skill_files or (root / ".claude-plugin").is_dir():
        surface = "."
        if skill_files:
            try:
                surface = skill_files[0].parent.relative_to(root).as_posix() or "."
            except ValueError:
                surface = "."
        return ArtifactProfile(
            "agent-skill", False, surface, "high", [],
            ["Install into a SKILL.md-compatible agent; this repository is not a standalone process."],
        )

    intro = readme[:3000]
    if _node_uses_electron(package) or ("electron" in intro and "desktop" in intro):
        return ArtifactProfile(
            "desktop-app", True, ".", "high",
            ["graphical display environment"],
            ["Desktop GUI execution is not a normal stock-Termux target."],
        )

    if "python" in stack and _python_has_scripts(root):
        return ArtifactProfile("cli", True, ".", "high", [], [])
    if "node" in stack and _node_has_bin(package):
        return ArtifactProfile("cli", True, ".", "high", [], [])
    if "rust" in stack and (root / "src" / "main.rs").is_file():
        return ArtifactProfile("cli", True, ".", "high", [], [])
    if "go" in stack and _has_go_main(root):
        return ArtifactProfile("cli", True, ".", "high", [], [])

    if _root_has_compose(root):
        if set(stack) & {"node", "python", "go", "rust"}:
            return ArtifactProfile("service", True, ".", "high", ["long-running service environment"], [])
        return ArtifactProfile("container-stack", True, ".", "high", ["Linux container/service environment"], [])

    if "node" in stack and _node_has_start(package):
        start = str(package.get("scripts", {}).get("start", "")).lower()
        if (root / "server").exists() or "server" in start:
            return ArtifactProfile("service", True, ".", "medium", ["long-running service environment"], [])
        return ArtifactProfile("application", True, ".", "medium", [], [])

    if "python" in stack:
        return ArtifactProfile("library", False, ".", "medium", [], ["Installable Python package; no standalone entrypoint was detected."])
    if "rust" in stack:
        if (root / "src" / "lib.rs").is_file():
            return ArtifactProfile("library", False, ".", "high", [], ["Rust library crate; no standalone binary target was detected."])
        return ArtifactProfile("application", True, ".", "low", [], [])
    if "go" in stack:
        return ArtifactProfile("library", False, ".", "medium", [], ["Go module without a proven main package."])
    if "node" in stack:
        if package.get("private") is True and package.get("workspaces"):
            return ArtifactProfile("application", True, ".", "low", [], ["Workspace repository; runnable surface must be selected from components."])
        return ArtifactProfile("library", False, ".", "medium", [], ["Node package without a proven bin/start entrypoint."])
    if "docker-compose" in stack:
        return ArtifactProfile("container-stack", True, ".", "high", ["Linux container/service environment"], [])

    return ArtifactProfile("application", True, ".", "low", [], ["Repository type could not be proven more specifically."])


def _capability_findings(root: Path, profile: ArtifactProfile) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    requirements = list(profile.requirements)
    readme = _read(root / "README.md").lower()

    privilege_tokens = ("cap_net_raw", "cap_net_admin", "cap_sys_ptrace", "setcap ")
    packet_tokens = ("packet sniff", "packet capture", "sniffs a given network interface", "raw socket")
    if any(token in readme for token in privilege_tokens) and any(token in readme for token in packet_tokens):
        findings.append(Finding(
            "high", "capability",
            "Requires elevated packet-capture/network capabilities that stock Termux normally cannot grant.",
            "README.md", "runtime",
        ))
        requirements.append("elevated packet-capture/network privileges")

    if profile.type == "desktop-app":
        findings.append(Finding(
            "high", "capability",
            "Desktop GUI runtime requires a display/session environment outside normal stock Termux.",
            None, "runtime",
        ))

    if "kubeconfig" in readme or "kubernetes cluster" in readme:
        requirements.append("external Kubernetes cluster/configuration")

    return findings, list(dict.fromkeys(requirements))


def apply_semantics(report: ScanReport, root: Path) -> ArtifactProfile:
    root = root.resolve()
    primary_stack = _primary_stack(root)
    profile = classify_repository(root, primary_stack)

    cleaned: list[Finding] = []
    for finding in report.findings:
        scope = _rescope(finding.path, finding.scope)
        if finding.path is None and finding.detail.startswith("Docker Compose requires adaptation") and not _root_has_compose(root):
            continue
        if finding.path is None and finding.detail.startswith("Dockerfile found") and not _root_has_dockerfile(root):
            continue
        cleaned.append(Finding(finding.severity, finding.kind, finding.detail, finding.path, scope))

    capability_findings, requirements = _capability_findings(root, profile)
    cleaned.extend(capability_findings)

    report.findings = cleaned
    report.stack = primary_stack
    report.score = _score(cleaned)
    report.strategy = _strategy(cleaned, primary_stack)
    if any(f.kind == "capability" and f.severity == "high" and f.scope == "runtime" for f in cleaned):
        report.strategy = "hybrid" if report.strategy == "native" else report.strategy

    return ArtifactProfile(
        profile.type, profile.runnable, profile.primary_surface, profile.confidence,
        requirements, profile.notes,
    )


def semantic_scan(root: Path) -> tuple[ScanReport, ArtifactProfile]:
    report = raw_scan(root)
    return report, apply_semantics(report, root)
