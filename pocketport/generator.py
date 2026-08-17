from __future__ import annotations

from pathlib import Path
from .scanner import ScanReport


def _native_commands(report: ScanReport) -> list[str]:
    stack = set(report.stack)
    pkgs = ["git"]
    commands = []

    if "python" in stack:
        pkgs += ["python", "clang", "make", "pkg-config", "rust"]
    if "node" in stack:
        pkgs += ["nodejs-lts", "clang", "make", "pkg-config", "python"]
    if "rust" in stack:
        pkgs += ["rust"]
    if "go" in stack:
        pkgs += ["golang"]

    unique = []
    for p in pkgs:
        if p not in unique:
            unique.append(p)

    commands.append("pkg update -y")
    commands.append("pkg install -y " + " ".join(unique))

    if "python" in stack:
        commands += [
            'if [ -f pyproject.toml ]; then python -m pip install -U pip setuptools wheel; python -m pip install .; fi',
            'if [ -f requirements.txt ]; then python -m pip install -U pip setuptools wheel; python -m pip install -r requirements.txt; fi',
        ]
    if "node" in stack:
        commands.append('if [ -f package-lock.json ]; then npm ci; else npm install; fi')
    if "rust" in stack:
        commands.append('cargo build --release')
    if "go" in stack:
        commands.append('go build ./...')

    return commands


def render_install_script(report: ScanReport) -> str:
    native = "\n".join(_native_commands(report))
    fallback = r'''echo "[PocketPort] Native install may fail. Preparing PRoot fallback..."
pkg install -y proot-distro git
if ! proot-distro list | grep -q 'ubuntu'; then
  proot-distro install ubuntu:24.04
fi

cat <<'EOF'

[PocketPort] PRoot fallback installed.

Enter it with:
  proot-distro login ubuntu

Inside Ubuntu, clone/copy this project and use its normal Linux install instructions.

Why not fake Docker/systemd?
Because pretending Android is a desktop Linux box until something explodes is not portability.

EOF'''

    mode = report.strategy
    body = native
    if mode == "proot":
        body = fallback
    elif mode == "hybrid":
        body = native + "\n\n" + 'echo "[PocketPort] Native path finished. If it failed, PRoot fallback follows."\n' + fallback

    return f'''#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

echo "[PocketPort] strategy={mode} score={report.score}/100"
echo "[PocketPort] stack={','.join(report.stack)}"

if [ -z "${{PREFIX:-}}" ] || [[ "${{PREFIX}}" != *"com.termux"* ]]; then
  echo "This installer is intended to run inside Termux." >&2
  exit 2
fi

{body}
'''


def write_generated(report: ScanReport, root: Path) -> Path:
    out = root / ".pocketport"
    out.mkdir(parents=True, exist_ok=True)

    import json
    (out / "report.json").write_text(json.dumps(report.to_dict(), indent=2), "utf-8")

    script = root / "termux-install.sh"
    script.write_text(render_install_script(report), "utf-8")
    script.chmod(0o755)
    return script
