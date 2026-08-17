# PocketPort

**Run more GitHub projects on the computer already in your pocket.**

PocketPort scans desktop-first Linux projects for Android/Termux incompatibilities and chooses an execution path:

- **native** — run directly in Termux
- **hybrid** — try native and keep a PRoot fallback ready
- **proot** — use a rootless Linux userland when the project assumes desktop Linux behavior

## MVP

```bash
pip install -e .

pocketport doctor
pocketport scan https://github.com/owner/repo
pocketport scan . --json
pocketport generate .
./termux-install.sh
```

`generate` creates:

```text
.pocketport/report.json
termux-install.sh
```

## Detects

- Node / Python / Rust / Go projects
- Dockerfile and Docker Compose assumptions
- CUDA / NVIDIA dependencies
- systemd / `systemctl`
- glibc and distro package-manager assumptions
- hard-coded `/usr/bin` and `/bin/bash`
- common native Node modules
- common heavy/native Python dependencies

## Why PRoot is part of the design

Termux software uses Android's bionic libc rather than desktop Linux glibc. Some repos therefore need a normal Linux userland instead of increasingly cursed shell patches.

PRoot-Distro provides a rootless fallback without requiring a normal Docker daemon.

## Install from source in Termux

```bash
pkg update -y
pkg install -y git python
git clone https://github.com/levomm/pocketport
cd pocketport
python -m pip install -e .
pocketport doctor
```

## Roadmap

### 0.1
- static compatibility scanner
- native / hybrid / proot strategy
- generated Termux installer
- local environment doctor

### 0.2
- auto-patch rules
- apt/dnf/apk -> pkg package translation
- architecture and binary-release detection
- aarch64 GitHub release asset selection

### 0.3
- `pocketport run <repo-url>`
- sandboxed test install
- failure-log classification
- LLM-assisted patch proposal

### 0.4
- public compatibility registry
- badges: `PocketPort: native / proot / broken`
- community-maintained per-repo recipes

## Non-goals

PocketPort will not magically make CUDA software run on a phone GPU or emulate missing kernel features by lying about them.

## License

MIT
