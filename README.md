# PocketPort

**Run more GitHub projects on the computer already in your pocket.**

PocketPort scans desktop-first Linux projects for Android/Termux incompatibilities, safely patches common assumptions, and chooses the least painful execution path:

- **native** — run directly in Termux
- **hybrid** — patch what is safe, keep a PRoot fallback ready
- **proot** — use a rootless Linux userland when the project really expects desktop Linux

## Install

```bash
pkg update -y
pkg install -y git python
git clone https://github.com/levomm/pocketport
cd pocketport
python -m pip install -e .
```

## PocketPort 0.2.1

### Inspect the phone

```bash
pocketport doctor
```

Shows Termux detection, CPU architecture and the installed build/runtime toolchain.

On Termux it also performs runtime capability probes for:

- native hard-link publication
- Node `COPYFILE_EXCL` no-clobber copying
- the PocketPort Node atomic-publish compatibility shim
- sandbox/confinement status, which remains target-project specific on Android

This matters because a dependency can install successfully and still fail later on a filesystem or kernel assumption. Apparently software enjoys saving the interesting failure for after installation.

### Scan a repo

```bash
pocketport scan .
pocketport scan https://github.com/owner/repo
pocketport scan . --json
```

Detects:

- Node / Python / Rust / Go projects
- Dockerfile and Docker Compose assumptions
- CUDA / NVIDIA dependencies
- systemd / `systemctl`
- glibc and distro package-manager assumptions
- hard-coded `/usr/bin` and `/bin/bash`
- x86-only architecture assumptions
- common native Node modules
- common heavy/native Python dependencies

### Preview safe patches

```bash
pocketport patch . --dry-run -v
```

### Patch a repo

```bash
pocketport patch .
```

Current safe auto-patches include:

- `/bin/bash` or `/usr/bin/env bash` shebang -> Termux bash while preserving interpreter arguments
- conservative `sudo` removal only before known external commands or explicit executable paths
- `xdg-open` -> `termux-open`
- simple `apt`, `apt-get`, `dnf`, `yum`, `apk` install/update commands -> `pkg`
- common package translations such as `build-essential -> clang make pkg-config`, `python3 -> python`, `libssl-dev -> openssl`
- standard Make recipe control prefixes such as `@`, `-` and `+`
- npm `package.json` scripts when the rewrite is unambiguous

PocketPort deliberately leaves ambiguous `sudo` forms, shell builtins/keywords, unknown commands, package-manager options with values, and complex shell expressions untouched. Pipes, command substitution and chained commands are not rewritten blindly. A patcher that confidently destroys working projects is not automation, it is vandalism with branding.

Patch details are written to:

```text
.pocketport/patch-report.json
```

Use `--backup` if you also want `.pocketport.bak` copies of modified files.

### Prepare in one command

```bash
pocketport prepare .
```

This performs:

1. scan
2. safe patch
3. rescan
4. generate `termux-install.sh`

### Run with Termux runtime compatibility

```bash
pocketport run -- <command> [args...]
```

On Termux, PocketPort can inject narrowly scoped runtime compatibility shims without modifying the upstream package. The current Node atomic-publish shim first attempts the application's original hard link and only falls back on recognized atomic temp-file patterns when Android returns `EACCES` or `EPERM`.

The fallback uses exclusive no-clobber copying rather than silently overwriting an existing target. Ordinary hard-link calls are left untouched.

### Pick the correct GitHub release binary

```bash
pocketport asset owner/repo
pocketport asset owner/repo --tag v1.2.3
```

PocketPort normalizes common CPU architecture spellings, queries GitHub Releases and filters candidates before scoring them. It prefers:

- the requested architecture such as `aarch64` / `arm64`
- Android / Termux assets
- Linux fallbacks
- usable archive formats

It rejects known wrong architectures, Windows/macOS/BSD and other foreign-OS assets, checksum/signature metadata, and obvious source archives before returning a candidate.

It respects `GITHUB_TOKEN` or `GH_TOKEN` when set.

### Generate only the installer

```bash
pocketport generate .
./termux-install.sh
```

Generated files:

```text
.pocketport/report.json
termux-install.sh
```

## Validated experiment: DeepSeek Harness

PocketPort has been tested end-to-end against `deepseek-ai/deepseek-harness` on Android 16 / aarch64 Termux.

The validation covered npm installation, Web UI startup, a real model/agent turn, shell execution, session persistence, and the Harness native filesystem `write` + `read` tools. The tested workflow runs directly in Termux with a PocketPort runtime shim and does not require PRoot.

The remaining limitation is sandbox confinement: the Harness `workspace-write` backend was not usable on the tested Android host, so a safer Termux-specific approval/confinement fallback is still needed.

See [`experiments/deepseek-harness.md`](experiments/deepseek-harness.md) for the full validation and failure analysis.

## Why PRoot is part of the design

Termux software uses Android's bionic libc rather than desktop Linux glibc. Some projects simply cannot be made native with a few path substitutions.

PocketPort therefore treats PRoot as a fallback, not as a lie that every Linux project is magically Android-native.

## Current strategy

### 0.1

- static compatibility scanner
- native / hybrid / proot strategy
- generated Termux installer
- local environment doctor

### 0.2 / 0.2.1

- safe auto-patch engine
- distro package-manager -> Termux `pkg` translation
- package-name translation map
- architecture assumption detection
- architecture-aware GitHub release asset selector
- `patch` and `prepare` commands
- machine-readable patch report
- conservative patch safety rules and regression coverage
- GitHub Actions pytest gate on Python 3.10 and 3.12

### Experimental runtime work

- `pocketport run -- <command>` compatibility environment
- Node atomic-publish hard-link fallback for Android/Termux
- runtime capability probes in `pocketport doctor`
- DeepSeek Harness end-to-end Android validation

### 0.3 next

- repo-aware `pocketport run <repo-url>` flow
- isolated test install
- failure-log classification
- retry with learned recipes
- runtime-aware scanner scoring
- safer Android approval/confinement fallback
- optional LLM-assisted patch proposal

### Later

- public compatibility registry
- `PocketPort: native / proot / broken` badges
- community-maintained per-repo recipes

## Non-goals

PocketPort will not magically make CUDA software run on a phone GPU, emulate unavailable kernel features, or silently rewrite complicated shell logic and hope for divine intervention.

## License

MIT
