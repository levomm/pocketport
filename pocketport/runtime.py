from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


NODE_ATOMIC_PUBLISH_SHIM = r'''const fs = require('node:fs')
const fsp = require('node:fs/promises')
const path = require('node:path')
const { syncBuiltinESMExports } = require('node:module')

if (!globalThis.__pocketportAtomicPublishShim) {
  const originalLink = fsp.link.bind(fsp)

  function looksLikeAtomicPublish(existingPath, newPath) {
    const sourceDir = path.dirname(existingPath)
    const targetDir = path.dirname(newPath)
    const sourceName = path.basename(existingPath)
    const targetName = path.basename(newPath)

    // Common atomic-publish shape: <target>.<random>.tmp beside <target>.
    const sameDirTemp = sourceDir === targetDir
      && sourceName.startsWith(`${targetName}.`)
      && sourceName.endsWith('.tmp')

    // DeepSeek fs-local guarded-create shape:
    //   .<target>.<pid>.<uuid>.tmpdir/<target>.tmp -> <target>
    // Keep this deliberately narrow so ordinary hard-link semantics are not
    // silently replaced by copies on Android.
    const stagingDirName = path.basename(sourceDir)
    const stagedTemp = path.dirname(sourceDir) === targetDir
      && sourceName === `${targetName}.tmp`
      && stagingDirName.startsWith(`.${targetName}.`)
      && stagingDirName.endsWith('.tmpdir')

    return sameDirTemp || stagedTemp
  }

  fsp.link = async function pocketportLink(existingPath, newPath) {
    try {
      return await originalLink(existingPath, newPath)
    } catch (error) {
      const code = error && error.code
      if ((code === 'EACCES' || code === 'EPERM') && looksLikeAtomicPublish(existingPath, newPath)) {
        return fsp.copyFile(existingPath, newPath, fs.constants.COPYFILE_EXCL)
      }
      throw error
    }
  }

  // Built-in ESM named exports are snapshots until explicitly synchronized.
  // DeepSeek Harness imports { link } from node:fs/promises, so sync the patched export.
  syncBuiltinESMExports()
  globalThis.__pocketportAtomicPublishShim = true
}
'''


ANDROID_LINKER_MARKERS = (
    b"/system/bin/linker",
    b"/apex/com.android.runtime/bin/linker",
)


def is_termux(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return "com.termux" in source.get("PREFIX", "")


def ensure_node_atomic_publish_shim(home: Path | None = None) -> Path:
    base = (Path.home() if home is None else home).expanduser()
    shim_dir = base / ".pocketport" / "shims"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "node-atomic-publish.cjs"
    if not shim.exists() or shim.read_text("utf-8") != NODE_ATOMIC_PUBLISH_SHIM:
        shim.write_text(NODE_ATOMIC_PUBLISH_SHIM, "utf-8")
    return shim


def _prefer_termux_native_path(env: dict[str, str]) -> None:
    """Put Termux's own binaries ahead of app-specific Node/tool wrappers.

    Android automation stacks often prepend private Node installations to PATH.
    Those wrappers can reinterpret Node CLI flags intended for the target project.
    PocketPort compatibility runs should use the Termux toolchain installed for
    the workspace while preserving the rest of PATH for project dependencies.
    """
    prefix_bin = str(Path(env["PREFIX"]) / "bin")
    parts = [part for part in env.get("PATH", "").split(os.pathsep) if part and part != prefix_bin]
    env["PATH"] = os.pathsep.join([prefix_bin, *parts])
    env["POCKETPORT_TERMUX_NATIVE_PATH"] = "1"


def compat_env(env: dict[str, str] | None = None, *, home: Path | None = None) -> dict[str, str]:
    result = dict(os.environ if env is None else env)
    if not is_termux(result):
        return result

    _prefer_termux_native_path(result)
    shim = ensure_node_atomic_publish_shim(home)
    require_opt = f"--require={shim}"
    current = result.get("NODE_OPTIONS", "").strip()
    if require_opt not in current.split():
        result["NODE_OPTIONS"] = f"{current} {require_opt}".strip()
    result["POCKETPORT_NODE_ATOMIC_PUBLISH_FALLBACK"] = "1"
    return result


def _resolve_executable(command: list[str], env: dict[str, str]) -> Path | None:
    raw = command[0]
    if "/" in raw:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        return candidate.resolve(strict=False)

    found = shutil.which(raw, path=env.get("PATH"))
    return Path(found).resolve(strict=False) if found else None


def _linux_release_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            head = handle.read(65536)
    except OSError:
        return False

    if not head.startswith(b"\x7fELF"):
        return False
    return not any(marker in head for marker in ANDROID_LINKER_MARKERS)


def _nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_text("utf-8", errors="ignore").strip())
    except OSError:
        return False


def prepare_linux_release_compat(
    command: list[str],
    env: dict[str, str],
    *,
    system_resolv: Path = Path("/etc/resolv.conf"),
    proot_executable: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Adapt desktop Linux ELF releases to Termux without entering a full distro.

    Android does not normally expose the resolver and CA files at the desktop
    Linux paths many static Go/Rust releases expect. For non-Android ELF
    executables, PocketPort can overlay Termux's resolver with PRoot and point
    common TLS stacks at Termux's CA bundle. Native Android/Termux ELF binaries
    are left alone.
    """
    result_env = dict(env)
    if not command or not is_termux(result_env):
        return list(command), result_env

    executable = _resolve_executable(command, result_env)
    if executable is None or not _linux_release_elf(executable):
        return list(command), result_env

    prefix = Path(result_env["PREFIX"])
    cert_bundle = prefix / "etc" / "tls" / "cert.pem"
    if cert_bundle.is_file() and "SSL_CERT_FILE" not in result_env:
        result_env["SSL_CERT_FILE"] = str(cert_bundle)
        result_env["POCKETPORT_TERMUX_CA_BUNDLE"] = "1"

    prepared = list(command)
    termux_resolv = prefix / "etc" / "resolv.conf"
    if not _nonempty_file(system_resolv) and _nonempty_file(termux_resolv):
        proot = proot_executable or shutil.which("proot", path=result_env.get("PATH"))
        if proot:
            prepared = [proot, "-b", f"{termux_resolv}:/etc/resolv.conf", *prepared]
            result_env["POCKETPORT_TERMUX_DNS_OVERLAY"] = "1"

    return prepared, result_env


def run_compat(command: list[str], *, env: dict[str, str] | None = None) -> int:
    if not command:
        raise ValueError("command must not be empty")

    runtime_env = compat_env(env)
    prepared_command, runtime_env = prepare_linux_release_compat(command, runtime_env)
    return subprocess.run(prepared_command, env=runtime_env, check=False).returncode
