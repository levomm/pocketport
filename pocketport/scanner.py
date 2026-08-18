from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import json
import re

TEXT_SUFFIXES = {
    ".sh", ".bash", ".zsh", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg",
}

IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "tests", "test", "docs", ".pocketport",
}

CI_DIRS = {".github", ".circleci", ".gitlab"}
DEV_DIRS = {"examples", "example", "benchmarks", "benchmark", "fixtures", "fixture"}
LOCKFILE_NAMES = {
    "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb",
    "Cargo.lock", "poetry.lock", "uv.lock",
}

HARD_BLOCKERS = {
    "nvidia/cuda": "CUDA base image",
    "nvidia-smi": "NVIDIA GPU tooling",
    "systemctl": "systemd service control",
    "/var/run/docker.sock": "Docker daemon socket",
}

PROOT_SIGNALS = {
    "docker compose": "Docker Compose",
    "docker-compose": "Docker Compose",
    "apt-get": "Debian/Ubuntu package manager",
    "apt install": "Debian/Ubuntu package manager",
    "dnf install": "Fedora package manager",
    "yum install": "RPM package manager",
    "apk add": "Alpine package manager",
    "glibc": "glibc dependency",
    "ld-linux": "glibc loader",
}

TERMUX_PATCHABLE = {
    "sudo ": "sudo is normally unavailable/unneeded in Termux",
    "/usr/bin/": "hard-coded /usr path",
    "/bin/bash": "hard-coded bash path",
    "xdg-open": "desktop opener; use termux-open where appropriate",
}

NODE_RISKY = {
    "puppeteer": "Chromium automation",
    "playwright": "browser automation",
    "canvas": "native graphics dependency",
    "sharp": "native image dependency",
    "better-sqlite3": "native Node module",
    "sqlite3": "native Node module",
    "node-pty": "PTY native module",
}

PYTHON_RISKY = {
    "torch": "PyTorch wheel availability/build cost",
    "tensorflow": "TensorFlow Android/Termux mismatch",
    "bitsandbytes": "CUDA-centric native dependency",
    "llama-cpp-python": "native C/C++ build",
    "onnxruntime": "wheel/platform compatibility",
    "pyarrow": "large native dependency",
}


@dataclass
class Finding:
    severity: str
    kind: str
    detail: str
    path: str | None = None
    scope: str = "runtime"


@dataclass
class ScanReport:
    path: str
    stack: list[str]
    score: int
    strategy: str
    findings: list[Finding]

    def to_dict(self) -> dict:
        return asdict(self)


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in IGNORED_DIRS for part in rel_parts)


def _iter_repo_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file() or _is_ignored(p, root):
            continue
        yield p


def _iter_text_files(root: Path) -> Iterable[Path]:
    for p in _iter_repo_files(root):
        if p.name in {"Dockerfile", "Makefile", "Procfile"} or p.suffix.lower() in TEXT_SUFFIXES:
            try:
                if p.stat().st_size <= 2_000_000:
                    yield p
            except OSError:
                pass


def _read(path: Path) -> str:
    try:
        return path.read_text("utf-8", errors="ignore")
    except OSError:
        return ""


def _scope_for_path(rel: str) -> str:
    path = Path(rel)
    parts = set(path.parts)
    name = path.name
    lowered = name.lower()

    if parts & CI_DIRS:
        return "ci"
    if name in LOCKFILE_NAMES:
        return "metadata"
    if parts & DEV_DIRS:
        return "dev"
    if lowered == "dockerfile" or lowered.startswith("dockerfile.") or lowered.endswith(".dockerfile"):
        return "build"
    if any(token in lowered for token in ("build", "release", "publish", "packaging")):
        return "build"
    return "runtime"


def _combine_scope(path_scope: str, dependency_scope: str) -> str:
    if path_scope != "runtime":
        return path_scope
    return dependency_scope


def _detect_stack(root: Path) -> list[str]:
    marker_map = {
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
    stack: list[str] = []
    for path in _iter_repo_files(root):
        name = marker_map.get(path.name)
        if name and name not in stack:
            stack.append(name)
    return stack or ["unknown"]


def _scan_node_dependencies(root: Path, findings: list[Finding]) -> None:
    dependency_scopes = {
        "dependencies": "runtime",
        "peerDependencies": "runtime",
        "optionalDependencies": "optional",
        "devDependencies": "dev",
    }
    scope_priority = {"runtime": 3, "optional": 2, "dev": 1}

    for package_json in _iter_repo_files(root):
        if package_json.name != "package.json":
            continue
        try:
            pkg = json.loads(_read(package_json))
        except json.JSONDecodeError:
            rel = str(package_json.relative_to(root))
            findings.append(Finding(
                "low", "parse", "package.json is not valid JSON.", rel, _scope_for_path(rel)
            ))
            continue

        rel = str(package_json.relative_to(root))
        path_scope = _scope_for_path(rel)
        detected: dict[str, str] = {}
        for key, dependency_scope in dependency_scopes.items():
            value = pkg.get(key, {})
            if not isinstance(value, dict):
                continue
            for name in NODE_RISKY:
                if name not in value:
                    continue
                current = detected.get(name)
                if current is None or scope_priority[dependency_scope] > scope_priority[current]:
                    detected[name] = dependency_scope

        for name, dependency_scope in detected.items():
            why = NODE_RISKY[name]
            findings.append(Finding(
                "medium",
                "node-native",
                f"{name}: {why}",
                rel,
                _combine_scope(path_scope, dependency_scope),
            ))


def _scan_python_dependencies(root: Path, findings: list[Finding]) -> None:
    for path in _iter_repo_files(root):
        if path.name not in {"requirements.txt", "pyproject.toml"}:
            continue
        blob = _read(path).lower()
        rel = str(path.relative_to(root))
        scope = _scope_for_path(rel)
        for name, why in PYTHON_RISKY.items():
            if re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", blob):
                findings.append(Finding("medium", "python-native", f"{name}: {why}", rel, scope))


def _finding_penalty(finding: Finding) -> int:
    base = {"high": 25, "medium": 8, "low": 2}.get(finding.severity, 0)

    scope_factor = {
        "runtime": 1.0,
        "optional": 0.45,
        "build": 0.35,
        "dev": 0.2,
        "ci": 0.0,
        "metadata": 0.0,
    }.get(finding.scope, 1.0)
    penalty = round(base * scope_factor)

    # Native dependencies are compatibility risks until exercised, not proof
    # that the runtime is broken. DeepSeek Harness is the first real-world case
    # that demonstrated why treating every native package as an 8-point runtime
    # failure is too pessimistic.
    if finding.kind in {"node-native", "python-native"}:
        penalty = min(penalty, 3 if finding.scope == "runtime" else 1)
    if finding.kind == "patchable":
        penalty = min(penalty, 1)
    return penalty


def _score(findings: list[Finding]) -> int:
    # The same assumption can appear in runtime source, CI and lockfiles. Count
    # the strongest occurrence once instead of charging the project repeatedly.
    penalties: dict[tuple[str, str], int] = {}
    for finding in findings:
        key = (finding.kind, finding.detail)
        penalties[key] = max(penalties.get(key, 0), _finding_penalty(finding))
    return max(0, min(100, 100 - sum(penalties.values())))


def _strategy(findings: list[Finding], stack: list[str]) -> str:
    runtime_high = {
        (f.kind, f.detail)
        for f in findings
        if f.scope == "runtime" and f.severity == "high"
    }
    runtime_adaptations = {
        (f.kind, f.detail)
        for f in findings
        if f.scope == "runtime"
        and f.kind in {"runtime", "linux-assumption", "architecture"}
        and f.severity in {"high", "medium"}
    }

    if len(runtime_high) >= 2:
        return "proot"
    if len(runtime_high) == 1 or len(runtime_adaptations) >= 3:
        return "hybrid"

    # A repository whose only executable surface is a Docker image is not a
    # native Termux application merely because Dockerfile assumptions are build
    # scoped. If source/runtime markers exist beside the Dockerfile, assess that
    # native surface on its own merits instead.
    native_runtime_stacks = {"node", "python", "rust", "go"}
    if "docker" in stack and not (set(stack) & native_runtime_stacks):
        return "hybrid"

    return "native"


def scan(root: Path) -> ScanReport:
    root = root.resolve()
    findings: list[Finding] = []
    stack = _detect_stack(root)

    if "docker-compose" in stack:
        findings.append(Finding(
            "high", "runtime", "Docker Compose requires adaptation; no normal Docker daemon in stock Termux."
        ))
    if "docker" in stack:
        findings.append(Finding(
            "medium", "runtime", "Dockerfile found. PRoot-Distro can be a daemonless fallback.", scope="build"
        ))

    if "node" in stack:
        _scan_node_dependencies(root, findings)
    if "python" in stack:
        _scan_python_dependencies(root, findings)

    seen = set()
    for path in _iter_text_files(root):
        text = _read(path)
        lower = text.lower()
        rel = str(path.relative_to(root))
        scope = _scope_for_path(rel)

        for needle, detail in HARD_BLOCKERS.items():
            if needle.lower() in lower:
                key = ("hard", needle, rel)
                if key not in seen:
                    findings.append(Finding("high", "blocker", detail, rel, scope))
                    seen.add(key)

        for needle, detail in PROOT_SIGNALS.items():
            if needle.lower() in lower:
                key = ("proot", needle, rel)
                if key not in seen:
                    findings.append(Finding("medium", "linux-assumption", detail, rel, scope))
                    seen.add(key)

        patchable_lower = lower.replace("/data/data/com.termux/files/usr/bin/bash", "")
        for needle, detail in TERMUX_PATCHABLE.items():
            if needle.lower() in patchable_lower:
                key = ("patch", needle, rel)
                if key not in seen:
                    findings.append(Finding("low", "patchable", detail, rel, scope))
                    seen.add(key)

        x86 = any(token in lower for token in ("x86_64", "amd64"))
        arm = any(token in lower for token in ("aarch64", "arm64"))
        if x86 and not arm:
            key = ("arch", rel)
            if key not in seen:
                findings.append(Finding(
                    "medium", "architecture", "x86-only architecture assumption detected", rel, scope
                ))
                seen.add(key)

    score = _score(findings)
    strategy = _strategy(findings, stack)

    return ScanReport(
        path=str(root),
        stack=stack,
        score=score,
        strategy=strategy,
        findings=findings,
    )
