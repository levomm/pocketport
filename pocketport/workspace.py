from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shlex
import shutil
import tempfile

from .components import assess_components
from .entrypoints import enrich_workspace_entrypoint
from .execution import ExecutionPlan, build_execution_plan
from .live_scan import _download_archive, _extract_archive, normalize_public_github_url
from .semantics import semantic_scan


_NODE_DEPENDENCY_SECTIONS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


def _relative_cd(path: str) -> str:
    if path in {"", "."}:
        return ""
    return f"cd {shlex.quote(path)}\n"


def _repository_has_node_dependency(root: Path, name: str) -> bool:
    for package_json in root.rglob("package.json"):
        try:
            relative = package_json.relative_to(root)
        except ValueError:
            continue
        if "node_modules" in relative.parts or ".git" in relative.parts:
            continue
        try:
            package = json.loads(package_json.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(package, dict):
            continue
        for section in _NODE_DEPENDENCY_SECTIONS:
            dependencies = package.get(section)
            if isinstance(dependencies, dict) and name in dependencies:
                return True
    return False


def _run_command_with_forwarded_args(command: str) -> str:
    prefix = "pocketport run -- "
    inner = command[len(prefix):] if command.startswith(prefix) else command
    try:
        tokens = shlex.split(inner)
    except ValueError:
        tokens = []

    needs_separator = False
    if len(tokens) >= 2 and tokens[0] in {"npm", "pnpm"}:
        needs_separator = tokens[1] == "run" or tokens[1] in {"start", "test"}
    elif len(tokens) >= 2 and tokens[0] == "cargo" and tokens[1] == "run":
        needs_separator = True

    separator = " --" if needs_separator else ""
    return f'{command}{separator} "$@"'


def _render_install_commands(plan: ExecutionPlan, *, sharp_compat: bool = False) -> str:
    commands: list[str] = []
    sharp_setup = [
        'echo "[PocketPort] sharp detected; enabling Termux libvips source build"',
        "pkg install -y libvips pkg-config",
        "export SHARP_FORCE_GLOBAL_LIBVIPS=1",
    ]
    inserted = False
    for command in plan.install:
        tokens: list[str]
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = []
        is_node_install = bool(tokens) and tokens[0] in {"npm", "pnpm", "yarn", "bun"} and "install" in tokens[1:]
        if sharp_compat and not inserted and is_node_install:
            commands.extend(sharp_setup)
            inserted = True
        commands.append(command)
    if sharp_compat and not inserted:
        commands = sharp_setup + commands
    return "\n".join(commands)


def render_install_script(plan: ExecutionPlan, *, sharp_compat: bool = False) -> str:
    install = _render_install_commands(plan, sharp_compat=sharp_compat)
    install_cd = _relative_cd(plan.install_directory)
    next_steps: list[str] = []
    if plan.run:
        next_steps.append(f"cd {plan.working_directory}" if plan.working_directory not in {"", "."} else "cd .")
        next_steps.extend(plan.run)
    else:
        next_steps.append("PocketPort did not infer a trustworthy launch command for this repository.")

    next_text = "\n".join(f"  {line}" for line in next_steps)
    return f'''#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"

if [ -z "${{PREFIX:-}}" ] || [[ "${{PREFIX}}" != *"com.termux"* ]]; then
  echo "This installer is intended to run inside Termux." >&2
  exit 2
fi

# Prepared installs must use the Android/Termux toolchain even when another
# private Node/Python toolchain appears earlier in the user's inherited PATH.
# Native package managers use their runtime platform to select optional binary
# dependencies such as esbuild, rollup and sharp.
export PATH="${{PREFIX}}/bin:${{PATH:-}}"
hash -r
export POCKETPORT_TERMUX_TOOLCHAIN=1

# Some native Node modules build against Linux-flavoured assumptions even when
# npm/pnpm correctly detects Android. On Android 11+ target API 30, the oldest
# API level that exposes interfaces such as statx() needed by packages like
# koffi. Respect an existing explicit compiler target instead of overwriting it.
POCKETPORT_ANDROID_API="$(getprop ro.build.version.sdk 2>/dev/null || true)"
POCKETPORT_ANDROID_TARGET=""
if [[ "$POCKETPORT_ANDROID_API" =~ ^[0-9]+$ ]] && [ "$POCKETPORT_ANDROID_API" -ge 30 ]; then
  case "$(uname -m)" in
    aarch64|arm64) POCKETPORT_ANDROID_TARGET="aarch64-linux-android30" ;;
    armv7l|armv8l|arm) POCKETPORT_ANDROID_TARGET="armv7a-linux-androideabi30" ;;
    x86_64|amd64) POCKETPORT_ANDROID_TARGET="x86_64-linux-android30" ;;
    i686|i386) POCKETPORT_ANDROID_TARGET="i686-linux-android30" ;;
  esac
fi
if [ -n "$POCKETPORT_ANDROID_TARGET" ]; then
  case " ${{CFLAGS:-}} " in
    *" -target "*|*" --target"*) ;;
    *) export CFLAGS="${{CFLAGS:+$CFLAGS }}-target $POCKETPORT_ANDROID_TARGET" ;;
  esac
  case " ${{CXXFLAGS:-}} " in
    *" -target "*|*" --target"*) ;;
    *) export CXXFLAGS="${{CXXFLAGS:+$CXXFLAGS }}-target $POCKETPORT_ANDROID_TARGET" ;;
  esac
  export POCKETPORT_ANDROID_NATIVE_TARGET="$POCKETPORT_ANDROID_TARGET"
fi

echo "[PocketPort] local prepared workspace"
echo "[PocketPort] method={plan.method} status={plan.status}"
echo "[PocketPort] Termux toolchain preferred for install"
if [ -n "$POCKETPORT_ANDROID_TARGET" ]; then
  echo "[PocketPort] Android native target=$POCKETPORT_ANDROID_TARGET"
fi

{install_cd}{install}

echo
echo "[PocketPort] install phase complete"
echo "Next:"
cat <<'EOF'
{next_text}
EOF
'''


def render_run_script(plan: ExecutionPlan) -> str | None:
    if not plan.run:
        return None
    working_cd = _relative_cd(plan.working_directory)
    setup_commands = "\n".join(plan.run[:-1])
    final_command = plan.run[-1]
    forwarded_command = _run_command_with_forwarded_args(final_command)
    setup_block = f"{setup_commands}\n" if setup_commands else ""
    return f'''#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
{working_cd}{setup_block}if [ "$#" -gt 0 ]; then
  {forwarded_command}
else
  {final_command}
fi
'''


def prepare_public_github(repository: str, *, home: Path | None = None) -> dict[str, object]:
    repo = normalize_public_github_url(repository)
    base = (home or Path.home()) / ".pocketport" / "workspaces"
    base.mkdir(parents=True, exist_ok=True)
    try:
        base.chmod(0o700)
    except OSError:
        pass

    workspace = Path(tempfile.mkdtemp(prefix=f"{repo.owner}-{repo.repo}-", dir=base))
    archive = workspace / "repo.tar.gz"
    root = workspace / "repo"

    try:
        _download_archive(repo, archive)
        _extract_archive(archive, root)
        try:
            archive.unlink()
        except OSError:
            pass

        report, artifact = semantic_scan(root)
        plan = enrich_workspace_entrypoint(build_execution_plan(report, root), root)
        components = assess_components(root, report.findings)
        sharp_compat = _repository_has_node_dependency(root, "sharp")
        if sharp_compat:
            if "sharp-libvips" not in plan.compatibility:
                plan.compatibility.append("sharp-libvips")
            plan.notes.append("Sharp detected; prepared install will build it against Termux libvips when Android has no prebuilt binary.")

        metadata = root / ".pocketport"
        metadata.mkdir(parents=True, exist_ok=True)
        payload = report.to_dict()
        payload["artifact"] = artifact.to_dict()
        if components:
            payload["components"] = [asdict(component) for component in components]
        payload["execution_plan"] = plan.to_dict()
        payload["repository"] = repo.url

        (metadata / "report.json").write_text(json.dumps(payload, indent=2), "utf-8")
        (metadata / "execution-plan.json").write_text(json.dumps(plan.to_dict(), indent=2), "utf-8")

        installer = root / "termux-install.sh"
        installer.write_text(render_install_script(plan, sharp_compat=sharp_compat), "utf-8")
        installer.chmod(0o755)

        runner_path: Path | None = None
        runner = render_run_script(plan)
        if runner is not None:
            runner_path = root / "termux-run.sh"
            runner_path.write_text(runner, "utf-8")
            runner_path.chmod(0o755)

        return {
            "ok": True,
            "repository": repo.url,
            "workspace": str(workspace),
            "repo_root": str(root),
            "installer": str(installer),
            "runner": str(runner_path) if runner_path else None,
            "execution_plan": plan.to_dict(),
        }
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
