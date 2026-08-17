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


@dataclass
class ScanReport:
    path: str
    stack: list[str]
    score: int
    strategy: str
    findings: list[Finding]

    def to_dict(self) -> dict:
        return asdict(self)


def _iter_text_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "tests", "test", "docs", ".pocketport"} for part in rel_parts):
            continue
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


def _detect_stack(root: Path) -> list[str]:
    stack = []
    markers = [
        ("package.json", "node"),
        ("pyproject.toml", "python"),
        ("requirements.txt", "python"),
        ("Cargo.toml", "rust"),
        ("go.mod", "go"),
        ("Dockerfile", "docker"),
        ("docker-compose.yml", "docker-compose"),
        ("docker-compose.yaml", "docker-compose"),
        ("compose.yml", "docker-compose"),
        ("compose.yaml", "docker-compose"),
    ]
    for filename, name in markers:
        if (root / filename).exists() and name not in stack:
            stack.append(name)
    return stack or ["unknown"]


def scan(root: Path) -> ScanReport:
    root = root.resolve()
    findings: list[Finding] = []
    stack = _detect_stack(root)

    if "docker-compose" in stack:
        findings.append(Finding("high", "runtime", "Docker Compose requires adaptation; no normal Docker daemon in stock Termux."))
    if "docker" in stack:
        findings.append(Finding("medium", "runtime", "Dockerfile found. PRoot-Distro can be a daemonless fallback."))

    package_json = root / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(_read(package_json))
            deps = {}
            deps.update(pkg.get("dependencies", {}))
            deps.update(pkg.get("devDependencies", {}))
            for name, why in NODE_RISKY.items():
                if name in deps:
                    findings.append(Finding("medium", "node-native", f"{name}: {why}", "package.json"))
        except json.JSONDecodeError:
            findings.append(Finding("low", "parse", "package.json is not valid JSON.", "package.json"))

    req_files = [root / "requirements.txt", root / "pyproject.toml"]
    py_blob = "\n".join(_read(p).lower() for p in req_files if p.exists())
    for name, why in PYTHON_RISKY.items():
        if re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", py_blob):
            findings.append(Finding("medium", "python-native", f"{name}: {why}"))

    seen = set()
    for path in _iter_text_files(root):
        text = _read(path)
        lower = text.lower()
        rel = str(path.relative_to(root))

        for needle, detail in HARD_BLOCKERS.items():
            if needle.lower() in lower:
                key = ("hard", needle, rel)
                if key not in seen:
                    findings.append(Finding("high", "blocker", detail, rel))
                    seen.add(key)

        for needle, detail in PROOT_SIGNALS.items():
            if needle.lower() in lower:
                key = ("proot", needle, rel)
                if key not in seen:
                    findings.append(Finding("medium", "linux-assumption", detail, rel))
                    seen.add(key)

        patchable_lower = lower.replace("/data/data/com.termux/files/usr/bin/bash", "")
        for needle, detail in TERMUX_PATCHABLE.items():
            if needle.lower() in patchable_lower:
                key = ("patch", needle, rel)
                if key not in seen:
                    findings.append(Finding("low", "patchable", detail, rel))
                    seen.add(key)

        x86 = any(token in lower for token in ("x86_64", "amd64"))
        arm = any(token in lower for token in ("aarch64", "arm64"))
        if x86 and not arm:
            key = ("arch", rel)
            if key not in seen:
                findings.append(Finding("medium", "architecture", "x86-only architecture assumption detected", rel))
                seen.add(key)

    unique_issues = {(f.severity, f.kind, f.detail) for f in findings}
    high = sum(severity == "high" for severity, _, _ in unique_issues)
    medium = sum(severity == "medium" for severity, _, _ in unique_issues)
    low = sum(severity == "low" for severity, _, _ in unique_issues)

    score = max(0, min(100, 100 - high * 25 - medium * 8 - low * 2))

    if high >= 2 or ("docker-compose" in stack and medium >= 2):
        strategy = "proot"
    elif high == 1 or medium >= 3:
        strategy = "hybrid"
    else:
        strategy = "native"

    return ScanReport(
        path=str(root),
        stack=stack,
        score=score,
        strategy=strategy,
        findings=findings,
    )
