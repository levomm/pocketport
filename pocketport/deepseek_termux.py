from __future__ import annotations

_SCRIPT = r'''#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PACKAGE="__PACKAGE__"
TARGET="aarch64-unknown-linux-android30"

echo "[PocketPort] DeepSeek Harness Android compatibility install"

ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|arm64) ;;
  *)
    echo "[PocketPort] DeepSeek Android recipe is currently validated only on arm64/aarch64 (got $ARCH)." >&2
    exit 2
    ;;
esac

pkg install -y git nodejs build-essential clang cmake ninja python libvips pkg-config

NODE_BIN="$(command -v node)"
NPM_ROOT="$(npm root -g)"
NODE_GYP_BIN="$NPM_ROOT/npm/node_modules/node-gyp/bin/node-gyp.js"
CREATE_GYPI="$NPM_ROOT/npm/node_modules/node-gyp/lib/create-config-gypi.js"

if [ -z "$NODE_BIN" ] || [ ! -f "$CREATE_GYPI" ]; then
  echo "[PocketPort] Node/npm toolchain is incomplete after package install." >&2
  exit 3
fi

python3 - "$CREATE_GYPI" <<'PY'
import sys
path = sys.argv[1]
src = open(path, encoding="utf-8").read()
if "delete variables.OS" not in src:
    anchor = "const variables = config.variables\n"
    if anchor not in src:
        raise SystemExit("PocketPort: node-gyp patch anchor changed")
    src = src.replace(anchor, anchor + "  delete variables.OS\n", 1)
    open(path, "w", encoding="utf-8").write(src)
PY

export CFLAGS="--target=$TARGET"
export CXXFLAGS="--target=$TARGET"

npm install -g "$PACKAGE"

DSH_LIB="$(npm root -g)/@deepseek-ai/dsh"
if [ ! -d "$DSH_LIB" ]; then
  echo "[PocketPort] @deepseek-ai/dsh was not installed where expected." >&2
  exit 4
fi

SHARP_DIR="$DSH_LIB/node_modules/sharp"
if [ -d "$SHARP_DIR" ] && ! compgen -G "$SHARP_DIR/src/build/Release/sharp-android-arm64-*.node" >/dev/null; then
  if [ -f "$NODE_GYP_BIN" ]; then
    echo "[PocketPort] building sharp against Termux libvips"
    (
      cd "$SHARP_DIR"
      SHARP_FORCE_GLOBAL_LIBVIPS=1 \
      CFLAGS="--target=$TARGET" CXXFLAGS="--target=$TARGET" \
      "$NODE_BIN" "$NODE_GYP_BIN" rebuild --directory=src
    )
  fi
fi

DSH_BIN="$DSH_LIB/lib/bin.js"
if [ ! -f "$DSH_BIN" ]; then
  echo "[PocketPort] DeepSeek CLI entrypoint not found." >&2
  exit 5
fi

python3 - "$DSH_BIN" "$NODE_BIN" <<'PY'
import sys
path, node = sys.argv[1], sys.argv[2]
src = open(path, encoding="utf-8").read()
first, sep, rest = src.partition("\n")
wanted = f"#!{node} --expose-internals"
if first != wanted:
    if not first.startswith("#!"):
        raise SystemExit("PocketPort: dsh shebang missing")
    open(path, "w", encoding="utf-8").write(wanted + "\n" + rest)
PY

python3 - "$DSH_LIB" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])

def patch(path: Path, replacements: list[tuple[str, str]], marker: str) -> None:
    if not path.exists():
        return
    src = path.read_text("utf-8")
    if marker in src:
        return
    changed = False
    for old, new in replacements:
        if old in src:
            src = src.replace(old, new)
            changed = True
    if changed:
        src += f"\n/* {marker} */\n"
        path.write_text(src, "utf-8")

session = root / "node_modules/@deepseek-ai/dsh-session-persistence-jsonl/lib/index.js"
patch(
    session,
    [
        (
            'import { link, mkdir, mkdtemp, open, readFile, readdir, realpath, rm, stat, truncate } from "node:fs/promises";',
            'import { mkdir, mkdtemp, open, readFile, readdir, realpath, rename, rm, stat, truncate } from "node:fs/promises";',
        ),
        ("await link(tmp, finalPath);", "await rename(tmp, finalPath);"),
    ],
    "pocketport-termux-session-publish",
)

attachment = root / "node_modules/@deepseek-ai/dsh-attachment-local/lib/index.js"
if attachment.exists():
    src = attachment.read_text("utf-8")
    if "pocketport-termux-attachment-publish" not in src:
        src = src.replace(
            "const handle = await open(path, constants.O_RDONLY);",
            'let handle;\n\ttry { handle = await open(path, constants.O_RDONLY); } catch (error) {\n'
            '\t\tif (error?.code === "EACCES" || error?.code === "EPERM" || error?.code === "ENOENT") return;\n'
            '\t\tthrow error;\n\t}',
        )
        src = src.replace(
            "await link(staged.path, target);",
            'try { await link(staged.path, target); } catch (error) {\n'
            '\t\t\tif (error?.code !== "EACCES" && error?.code !== "EPERM") throw error;\n'
            '\t\t\tawait rename(staged.path, target);\n\t\t}',
        )
        src += "\n/* pocketport-termux-attachment-publish */\n"
        attachment.write_text(src, "utf-8")

fs_local = root / "node_modules/@deepseek-ai/dsh-fs-local/lib/index.js"
if fs_local.exists():
    src = fs_local.read_text("utf-8")
    if "pocketport-termux-fs-publish" not in src:
        old = "await linkFile(tempPath, absolutePath);"
        new = (
            'try { await linkFile(tempPath, absolutePath); } catch (error) {\n'
            '\t\t\t\tif (error?.code !== "EACCES" && error?.code !== "EPERM") throw error;\n'
            '\t\t\t\tawait rename(tempPath, absolutePath);\n\t\t\t}'
        )
        if old in src:
            src = src.replace(old, new, 1)
            src += "\n/* pocketport-termux-fs-publish */\n"
            fs_local.write_text(src, "utf-8")
PY

echo "[PocketPort] validating DeepSeek Harness CLI"
if ! dsh --version >/dev/null 2>&1; then
  echo "[PocketPort] DeepSeek Harness CLI smoke test failed after compatibility install." >&2
  exit 9
fi
mkdir -p "$HOME/.pocketport"
touch "$HOME/.pocketport/deepseek-harness-ready"
echo "[PocketPort] DeepSeek Harness Android compatibility ready"
echo "[PocketPort] start with: dsh web --no-open"
'''

def render_deepseek_termux_installer(package: str) -> str:
    return _SCRIPT.replace("__PACKAGE__", package)
