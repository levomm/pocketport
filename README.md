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

## PocketPort 0.2

### Inspect the phone

```bash
pocketport doctor
```

Shows Termux detection, CPU architecture and the installed build/runtime toolchain.

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

- `/bin/bash` or `/usr/bin/env bash` shebang -> Termux bash
- `sudo` removal in shell/package scripts
- `xdg-open` -> `termux-open`
- simple `apt`, `apt-get`, `dnf`, `yum`, `apk` install/update commands -> `pkg`
- common package translations such as `build-essential -> clang make pkg-config`, `python3 -> python`, `libssl-dev -> openssl`
- npm `package.json` scripts using `sudo` or `xdg-open`

PocketPort deliberately refuses to rewrite complex shell expressions containing pipes, command substitution or chained commands. A patcher that confidently destroys working projects is not automation, it is vandalism with branding.

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

### Pick the correct GitHub release binary

```bash
pocketport asset owner/repo
pocketport asset owner/repo --tag v1.2.3
```

PocketPort normalizes Android ARM64 to `aarch64`, queries GitHub Releases and scores assets by:

- `aarch64` / `arm64` architecture
- Android / Termux preference
- Linux fallback
- archive format
- rejection of x86, Windows/macOS, source archives and checksum files

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

## Why PRoot is part of the design

Termux software uses Android's bionic libc rather than desktop Linux glibc. Some projects simply cannot be made native with a few path substitutions.

PocketPort therefore treats PRoot as a fallback, not as a lie that every Linux project is magically Android-native.

## Current strategy

### 0.1

- static compatibility scanner
- native / hybrid / proot strategy
- generated Termux installer
- local environment doctor

### 0.2

- safe auto-patch engine
- distro package-manager -> Termux `pkg` translation
- package-name translation map
- architecture assumption detection
- ARM64/aarch64 GitHub release asset selector
- `patch` and `prepare` commands
- machine-readable patch report

### 0.3 next

- `pocketport run <repo-url>`
- isolated test install
- failure-log classification
- retry with learned recipes
- optional LLM-assisted patch proposal

### Later

- public compatibility registry
- `PocketPort: native / proot / broken` badges
- community-maintained per-repo recipes

## Non-goals

PocketPort will not magically make CUDA software run on a phone GPU, emulate unavailable kernel features, or silently rewrite complicated shell logic and hope for divine intervention.

## License

MIT
