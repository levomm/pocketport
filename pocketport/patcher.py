from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re
import shutil

TERMUX_PREFIX = "/data/data/com.termux/files/usr"

PACKAGE_MAP: dict[str, list[str]] = {
    "build-essential": ["clang", "make", "pkg-config"],
    "gcc": ["clang"],
    "g++": ["clang"],
    "python3": ["python"],
    "python3-dev": ["python"],
    "python3-pip": ["python"],
    "libssl-dev": ["openssl"],
    "openssl-devel": ["openssl"],
    "libffi-dev": ["libffi"],
    "libffi-devel": ["libffi"],
    "libsqlite3-dev": ["libsqlite"],
    "sqlite-devel": ["libsqlite"],
    "zlib1g-dev": ["zlib"],
    "zlib-devel": ["zlib"],
    "libjpeg-dev": ["libjpeg-turbo"],
    "libpng-dev": ["libpng"],
    "pkg-config": ["pkg-config"],
    "cmake": ["cmake"],
    "ninja-build": ["ninja"],
    "make": ["make"],
    "git": ["git"],
    "curl": ["curl"],
    "wget": ["wget"],
    "rustc": ["rust"],
    "cargo": ["rust"],
    "golang": ["golang"],
    "go": ["golang"],
}

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "tests", "test", "docs", ".pocketport",
}

SHELL_NAMES = {"Makefile", "Procfile"}
SHELL_SUFFIXES = {".sh", ".bash", ".zsh"}
SHELL_META = ("|", "&&", "||", ";", "$(", "`")
SAFE_PACKAGE_FLAGS = {
    "-y", "--yes", "--assume-yes", "-q", "--quiet", "--no-install-recommends",
    "--no-cache",
}
UNSAFE_SUDO_COMMAND_PREFIXES = ("-", "#", ">", "<", "|", "&", ";", "(", ")", "{", "}", "!")


@dataclass
class PatchChange:
    path: str
    rule: str
    before: str
    after: str


@dataclass
class PatchReport:
    root: str
    dry_run: bool
    files_changed: list[str]
    changes: list[PatchChange]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _translate_packages(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for token in tokens:
        mapped = PACKAGE_MAP.get(token, [token])
        for package in mapped:
            if package not in out:
                out.append(package)
    return out


def _split_safe_package_args(rest: str) -> list[str] | None:
    if any(x in rest for x in SHELL_META):
        return None

    packages: list[str] = []
    for token in rest.split():
        if token.startswith("-"):
            if token not in SAFE_PACKAGE_FLAGS:
                return None
            continue
        packages.append(token)
    return packages


def _patch_package_line(line: str) -> tuple[str, str | None]:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line

    match = re.match(
        r"^(?P<indent>\s*)(?P<sudo>sudo\s+)?"
        r"(?P<pm>apt-get|apt|dnf|yum|apk)\s+"
        r"(?P<action>install|update|upgrade|add)\b(?P<rest>.*)$",
        body,
    )
    if not match:
        return line, None

    action = match.group("action")
    rest = match.group("rest").strip()
    args = _split_safe_package_args(rest)
    if args is None:
        return line, None

    if action in {"update", "upgrade"}:
        if args:
            return line, None
        replacement = f"{match.group('indent')}pkg {'upgrade' if action == 'upgrade' else 'update'} -y"
        return replacement + newline, "package-manager"

    if not args:
        return line, None

    packages = _translate_packages(args)
    replacement = f"{match.group('indent')}pkg install -y {' '.join(packages)}"
    return replacement + newline, "package-manager"


def _replace_command_prefix(line: str, old: str, new: str) -> str:
    pattern = rf"^(?P<indent>\s*){re.escape(old)}(?P<sep>\s+|$)"

    def repl(match: re.Match[str]) -> str:
        indent = match.group("indent")
        sep = match.group("sep")
        return f"{indent}{new}{sep}"

    return re.sub(pattern, repl, line, count=1)


def _remove_sudo_prefix(line: str) -> str:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    match = re.match(r"^(?P<indent>[ \t]*)sudo[ \t]+(?P<rest>\S.*)$", body)
    if not match:
        return line
    rest = match.group("rest")
    if rest.startswith(UNSAFE_SUDO_COMMAND_PREFIXES):
        return line
    return f"{match.group('indent')}{rest}{newline}"


def _patch_shebang(line: str) -> str | None:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    match = re.match(
        r"^#!\s*/(?:usr/)?bin/(?:env\s+)?bash\b(?P<args>.*)$",
        body,
    )
    if not match:
        return None
    return f"#!{TERMUX_PREFIX}/bin/bash{match.group('args')}{newline}"


def _patch_shell_text(text: str) -> tuple[str, list[tuple[str, str, str]], list[str]]:
    changes: list[tuple[str, str, str]] = []
    warnings: list[str] = []
    lines = text.splitlines(keepends=True)
    out: list[str] = []

    for i, line in enumerate(lines):
        original = line
        patched = line
        rule = None

        if i == 0:
            shebang = _patch_shebang(patched)
            if shebang is not None:
                patched = shebang
                rule = "termux-shebang"

        if patched == original or i != 0:
            complex_shell = any(x in patched for x in SHELL_META)
            if not complex_shell:
                candidate, package_rule = _patch_package_line(patched)
                if package_rule:
                    patched = candidate
                    rule = package_rule

                new = _remove_sudo_prefix(patched)
                if new != patched:
                    patched = new
                    rule = rule or "remove-sudo"

                new = _replace_command_prefix(patched, "xdg-open", "termux-open")
                if new != patched:
                    patched = new
                    rule = rule or "termux-open"

        if patched != original:
            changes.append((rule or "shell", original.rstrip("\n"), patched.rstrip("\n")))
        if "systemctl" in patched:
            warnings.append("systemctl remains and normally requires PRoot/service adaptation")
        if "docker " in patched or "docker-compose" in patched:
            warnings.append("Docker command remains and normally requires PRoot/OCI adaptation")

        out.append(patched)

    return "".join(out), changes, warnings


def _patch_package_json(path: Path) -> tuple[str | None, list[tuple[str, str, str]], list[str]]:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, [], ["package.json could not be parsed"]

    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return None, [], []

    changed = []
    warnings = []
    for name, value in list(scripts.items()):
        if not isinstance(value, str):
            continue
        original = value
        if not any(x in value for x in SHELL_META):
            value = _remove_sudo_prefix(value)
            value = _replace_command_prefix(value, "xdg-open", "termux-open")
        if "systemctl" in value:
            warnings.append(f"package.json script '{name}' still uses systemctl")
        if value != original:
            scripts[name] = value
            changed.append((f"package.json:scripts.{name}", original, value))

    if not changed:
        return None, [], warnings

    return json.dumps(data, indent=2, ensure_ascii=False) + "\n", changed, warnings


def patch_repo(root: Path, *, dry_run: bool = False, backup: bool = False) -> PatchReport:
    root = root.resolve()
    files_changed: list[str] = []
    changes: list[PatchChange] = []
    warnings: list[str] = []

    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SHELL_NAMES or path.suffix.lower() in SHELL_SUFFIXES or path.name == "package.json":
            try:
                if path.stat().st_size <= 2_000_000:
                    candidates.append(path)
            except OSError:
                pass

    for path in candidates:
        rel = str(path.relative_to(root))
        original = path.read_text("utf-8", errors="ignore")

        if path.name == "package.json":
            patched, local_changes, local_warnings = _patch_package_json(path)
            if patched is None:
                warnings.extend(f"{rel}: {w}" for w in local_warnings)
                continue
        else:
            patched, local_changes, local_warnings = _patch_shell_text(original)

        warnings.extend(f"{rel}: {w}" for w in local_warnings)
        if patched == original:
            continue

        files_changed.append(rel)
        for rule, before, after in local_changes:
            changes.append(PatchChange(rel, rule, before, after))

        if not dry_run:
            if backup:
                backup_path = path.with_suffix(path.suffix + ".pocketport.bak")
                if not backup_path.exists():
                    shutil.copy2(path, backup_path)
            path.write_text(patched, "utf-8")

    report = PatchReport(
        root=str(root),
        dry_run=dry_run,
        files_changed=files_changed,
        changes=changes,
        warnings=sorted(set(warnings)),
    )

    if not dry_run:
        out = root / ".pocketport"
        out.mkdir(parents=True, exist_ok=True)
        (out / "patch-report.json").write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            "utf-8",
        )

    return report
