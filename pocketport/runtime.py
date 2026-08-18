from __future__ import annotations

import os
from pathlib import Path
import subprocess


NODE_ATOMIC_PUBLISH_SHIM = r'''const fs = require('node:fs')
const fsp = require('node:fs/promises')
const path = require('node:path')
const { syncBuiltinESMExports } = require('node:module')

if (!globalThis.__pocketportAtomicPublishShim) {
  const originalLink = fsp.link.bind(fsp)

  fsp.link = async function pocketportLink(existingPath, newPath) {
    try {
      return await originalLink(existingPath, newPath)
    } catch (error) {
      const code = error && error.code
      const sameDir = path.dirname(existingPath) === path.dirname(newPath)
      const sourceName = path.basename(existingPath)
      const targetName = path.basename(newPath)
      const looksLikeAtomicTemp = sourceName.startsWith(`${targetName}.`) && sourceName.endsWith('.tmp')

      if ((code === 'EACCES' || code === 'EPERM') && sameDir && looksLikeAtomicTemp) {
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


def compat_env(env: dict[str, str] | None = None, *, home: Path | None = None) -> dict[str, str]:
    result = dict(os.environ if env is None else env)
    if not is_termux(result):
        return result

    shim = ensure_node_atomic_publish_shim(home)
    require_opt = f"--require={shim}"
    current = result.get("NODE_OPTIONS", "").strip()
    if require_opt not in current.split():
        result["NODE_OPTIONS"] = f"{current} {require_opt}".strip()
    result["POCKETPORT_NODE_ATOMIC_PUBLISH_FALLBACK"] = "1"
    return result


def run_compat(command: list[str], *, env: dict[str, str] | None = None) -> int:
    if not command:
        raise ValueError("command must not be empty")
    return subprocess.run(command, env=compat_env(env), check=False).returncode
