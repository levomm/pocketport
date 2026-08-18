from __future__ import annotations

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .runtime import compat_env, is_termux


@dataclass(frozen=True)
class RuntimeCapability:
    name: str
    status: str
    detail: str = ""


def _node_path(env: dict[str, str]) -> str | None:
    return shutil.which("node", path=env.get("PATH"))


def _probe_native_hardlink(root: Path) -> RuntimeCapability:
    source = root / "hardlink-source"
    target = root / "hardlink-target"
    source.write_text("ok", encoding="utf-8")

    link_fn = getattr(os, "link", None)
    if link_fn is not None:
        try:
            link_fn(source, target)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EPERM}:
                return RuntimeCapability("native hardlink", "denied", exc.strerror or str(exc))
            return RuntimeCapability("native hardlink", "unavailable", f"{exc.__class__.__name__}: {exc}")
        return RuntimeCapability("native hardlink", "ok", "link() succeeded")

    # Some Android/Termux Python builds do not expose os.link at all even
    # though the host still has the POSIX ln utility. Probe the actual host
    # capability instead of treating a missing Python wrapper as the result.
    ln = shutil.which("ln")
    if not ln:
        return RuntimeCapability(
            "native hardlink",
            "unavailable",
            "Python os.link is unavailable and ln is not installed",
        )

    result = subprocess.run(
        [ln, str(source), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return RuntimeCapability("native hardlink", "ok", "ln hard link succeeded")

    detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
    lowered = detail.lower()
    if "permission denied" in lowered or "operation not permitted" in lowered:
        return RuntimeCapability("native hardlink", "denied", detail)
    return RuntimeCapability("native hardlink", "unavailable", detail)


def _probe_node_exclusive_copy(root: Path, env: dict[str, str]) -> RuntimeCapability:
    node = _node_path(env)
    if not node:
        return RuntimeCapability("Node exclusive copy", "missing", "node is not installed")

    source = root / "copy-source"
    target = root / "copy-target"
    source.write_text("ok", encoding="utf-8")
    script = r"""
const fs = require('node:fs')
const source = process.argv[1]
const target = process.argv[2]
fs.copyFileSync(source, target, fs.constants.COPYFILE_EXCL)
try {
  fs.copyFileSync(source, target, fs.constants.COPYFILE_EXCL)
  process.exit(3)
} catch (error) {
  if (!error || error.code !== 'EEXIST') throw error
}
"""
    result = subprocess.run(
        [node, "-e", script, str(source), str(target)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and target.exists() and target.read_text("utf-8") == "ok":
        return RuntimeCapability("Node exclusive copy", "ok", "COPYFILE_EXCL preserves no-clobber behavior")
    detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
    return RuntimeCapability("Node exclusive copy", "unavailable", detail)


def _probe_node_atomic_publish_shim(root: Path, env: dict[str, str]) -> RuntimeCapability:
    if not is_termux(env):
        return RuntimeCapability("PocketPort Node shim", "not-needed", "host is not Termux")

    node = _node_path(env)
    if not node:
        return RuntimeCapability("PocketPort Node shim", "missing", "node is not installed")

    target = root / "atomic-target"
    source = root / "atomic-target.doctor.tmp"
    source.write_text("ok", encoding="utf-8")
    script = r"""
const fsp = require('node:fs/promises')
const source = process.argv[1]
const target = process.argv[2]
;(async () => {
  await fsp.link(source, target)
  const value = await fsp.readFile(target, 'utf8')
  if (value !== 'ok') process.exit(4)
})().catch(error => {
  console.error(error)
  process.exit(2)
})
"""
    result = subprocess.run(
        [node, "-e", script, str(source), str(target)],
        env=compat_env(env, home=root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0 and target.exists() and target.read_text("utf-8") == "ok":
        return RuntimeCapability("PocketPort Node shim", "ok", "atomic publish works through pocketport run compatibility")
    detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
    return RuntimeCapability("PocketPort Node shim", "unavailable", detail)


def inspect_runtime_capabilities(
    env: dict[str, str] | None = None,
    *,
    home: Path | None = None,
) -> list[RuntimeCapability]:
    source_env = dict(os.environ if env is None else env)
    base = (Path.home() if home is None else home).expanduser()

    try:
        with tempfile.TemporaryDirectory(prefix=".pocketport-doctor-", dir=base) as temp_dir:
            root = Path(temp_dir)
            capabilities = [
                _probe_native_hardlink(root),
                _probe_node_exclusive_copy(root, source_env),
                _probe_node_atomic_publish_shim(root, source_env),
            ]
    except OSError as exc:
        capabilities = [RuntimeCapability("runtime probes", "unavailable", str(exc))]

    if is_termux(source_env):
        capabilities.append(RuntimeCapability(
            "sandbox confinement",
            "project-specific",
            "native Linux sandbox backends may be unavailable on Android; keep approval gates enabled until the target is validated",
        ))
    else:
        capabilities.append(RuntimeCapability(
            "sandbox confinement",
            "project-specific",
            "probe the target project's sandbox backend on its actual host",
        ))
    return capabilities
