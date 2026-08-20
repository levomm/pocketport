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
SAFE_SUDO_COMMANDS = {
    "apk", "apt", "apt-get", "cargo", "chmod", "clang", "clang++", "cmake", "cp",
    "curl", "dnf", "find", "g++", "gcc", "git", "go", "grep", "install", "ln",
    "make", "mkdir", "mv", "ninja", "node", "npm", "pip", "pip3", "pkg", "pnpm",
    "python", "python3", "rm", "rustc", "sed", "tar", "termux-open", "touch", "unzip",
    "wget", "xdg-open", "yum", "yarn", "zip",
}
NODE_DEPENDENCY_SECTIONS = (
    "dependencies", "devDependencies", "optionalDependencies", "peerDependencies"
)


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


def _safe_to_strip_sudo(command: str) -> bool:
    if command in SAFE_SUDO_COMMANDS:
        return True
    return command.startswith(("/", "./", "../")) and len(command) > 1


def _remove_sudo_prefix(line: str) -> str:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    match = re.match(r"^(?P<indent>[ \t]*)sudo[ \t]+(?P<rest>\S.*)$", body)
    if not match:
        return line
    rest = match.group("rest")
    command = rest.split(None, 1)[0]
    if rest.startswith(UNSAFE_SUDO_COMMAND_PREFIXES) or not _safe_to_strip_sudo(command):
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


def _unwrap_make_recipe(line: str) -> tuple[str, str]:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    match = re.match(
        r"^(?P<prefix>\t[ \t]*(?:[@+\-][ \t]*)+)(?P<body>.*)$",
        body,
    )
    if not match:
        return "", line
    return match.group("prefix"), match.group("body") + newline


def _patch_shell_text(
    text: str, *, makefile: bool = False
) -> tuple[str, list[tuple[str, str, str]], list[str]]:
    changes: list[tuple[str, str, str]] = []
    warnings: list[str] = []
    lines = text.splitlines(keepends=True)
    out: list[str] = []

    for i, line in enumerate(lines):
        original = line
        recipe_prefix, work = _unwrap_make_recipe(line) if makefile else ("", line)
        patched_work = work
        rule = None

        if i == 0 and not recipe_prefix:
            shebang = _patch_shebang(patched_work)
            if shebang is not None:
                patched_work = shebang
                rule = "termux-shebang"

        if patched_work == work or i != 0:
            complex_shell = any(x in patched_work for x in SHELL_META)
            if not complex_shell:
                candidate, package_rule = _patch_package_line(patched_work)
                if package_rule:
                    patched_work = candidate
                    rule = package_rule

                new = _remove_sudo_prefix(patched_work)
                if new != patched_work:
                    patched_work = new
                    rule = rule or "remove-sudo"

                new = _replace_command_prefix(patched_work, "xdg-open", "termux-open")
                if new != patched_work:
                    patched_work = new
                    rule = rule or "termux-open"

        patched = recipe_prefix + patched_work
        if patched != original:
            changes.append((rule or "shell", original.rstrip("\n"), patched.rstrip("\n")))
        if "systemctl" in patched:
            warnings.append("systemctl remains and normally requires PRoot/service adaptation")
        if "docker " in patched or "docker-compose" in patched:
            warnings.append("Docker command remains and normally requires PRoot/OCI adaptation")

        out.append(patched)

    return "".join(out), changes, warnings


def _package_has_dependency(data: dict, name: str) -> bool:
    for section in NODE_DEPENDENCY_SECTIONS:
        dependencies = data.get(section)
        if isinstance(dependencies, dict) and name in dependencies:
            return True
    return False


def _patch_node_script(value: str, *, has_tsx: bool) -> str:
    # Some Android/Termux Node wrappers lose the following argument for options
    # such as --import/--require. The equals form is accepted by stock Node too.
    value = re.sub(
        r"(?<!\S)node\s+--import\s+([^\s;&|]+)",
        r"node --import=\1",
        value,
    )
    value = re.sub(
        r"(?<!\S)node\s+--require\s+([^\s;&|]+)",
        r"node --require=\1",
        value,
    )

    if not has_tsx:
        return value

    # Avoid the tsx executable shim when a script can be launched through
    # Node's stable ESM import hook directly. Preserve script arguments.
    value = re.sub(
        r"(^|(?:&&|\|\||;)\s*)tsx\s+([^\s;&|]+\.tsx?)(?=\s|$)",
        lambda match: f"{match.group(1)}node --import=tsx/esm {match.group(2)}",
        value,
    )

    # tsdown's automatic/native TypeScript config loader uses Node
    # registerHooks on modern Node versions. That hook path is not reliable in
    # every Android Node build, while tsdown explicitly supports the tsx loader.
    def patch_tsdown(match: re.Match[str]) -> str:
        command = match.group(0)
        if "--config-loader" in command:
            return command
        return command.replace("tsdown", "tsdown --config-loader tsx", 1)

    value = re.sub(r"(?<![\w.-])tsdown(?:[^;&|]*)", patch_tsdown, value)
    return value


def _patch_package_json(path: Path) -> tuple[str | None, list[tuple[str, str, str]], list[str]]:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, [], ["package.json could not be parsed"]

    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return None, [], []

    has_tsx = _package_has_dependency(data, "tsx")
    changed = []
    warnings = []
    for name, value in list(scripts.items()):
        if not isinstance(value, str):
            continue
        original = value
        value = _patch_node_script(value, has_tsx=has_tsx)
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
            patched, local_changes, local_warnings = _patch_shell_text(
                original, makefile=path.name == "Makefile"
            )

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
