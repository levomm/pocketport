<p align="center">
  <img src="./assets/pocketport-logo.svg" alt="PocketPort" width="760">
</p>

<p align="center">
  <strong>Run more GitHub projects on the computer already in your pocket.</strong>
</p>

<p align="center">
  <a href="https://github.com/levomm/pocketport/actions/workflows/tests.yml"><img alt="tests" src="https://github.com/levomm/pocketport/actions/workflows/tests.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
  <img alt="Android + Termux" src="https://img.shields.io/badge/Android-Termux-19c37d">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-8affc1">
  <img alt="PocketPort 0.3.8" src="https://img.shields.io/badge/PocketPort-0.3.8-28f58d">
</p>

PocketPort scans desktop-first Linux projects for Android / Termux incompatibilities, chooses the least painful execution path, and applies only conservative patches when the fix is unambiguous.

It does **not** pretend every Linux repository is magically Android-native.

## What it decides

| Strategy | Meaning |
| --- | --- |
| **native** | Run directly in Termux |
| **hybrid** | Patch safe assumptions and keep a PRoot fallback |
| **proot** | Use a rootless Linux userland when desktop Linux assumptions are real |

## Quick start

```bash
pkg update -y
pkg install -y git python
git clone https://github.com/levomm/pocketport
cd pocketport
python -m pip install -e .
```

Check the phone:

```bash
pocketport doctor
```

Scan a repository:

```bash
pocketport scan https://github.com/owner/repo
pocketport scan https://github.com/owner/repo --json
```

Prepare and run a public GitHub repository:

```bash
pocketport run https://github.com/owner/repo
```

PocketPort prepares an isolated workspace, applies only conservative patches, builds the execution plan, and asks before executing third-party code in Termux.

Prepare a local project:

```bash
pocketport prepare .
```

Preview patches before touching anything:

```bash
pocketport patch . --dry-run -v
```

## Reference proof: DeepSeek Harness

PocketPort has been tested end-to-end against [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) on **Android 16 / aarch64 Termux**.

Validated:

- npm installation
- Web UI startup
- a real model / agent turn
- shell execution
- session persistence
- native filesystem write + read
- direct Termux execution with a narrow PocketPort runtime shim
- no PRoot required for the tested flow

Current limitation: the Harness `workspace-write` sandbox backend was not usable on the tested Android host, so Android-specific confinement / approval remains an active area.

Full notes: [experiments/deepseek-harness.md](experiments/deepseek-harness.md)

## What PocketPort scans

- Node, Python, Rust and Go projects
- Docker / Docker Compose assumptions
- CUDA / NVIDIA dependencies
- systemd / `systemctl`
- glibc and distro package-manager assumptions
- hard-coded `/usr/bin` and `/bin/bash`
- x86-only assumptions
- common native Node modules
- common heavy / native Python dependencies

## Conservative patching

Current safe rewrites include:

- desktop bash shebangs -> Termux bash
- narrow `sudo` removal before known external commands
- `xdg-open` -> `termux-open`
- simple `apt`, `dnf`, `yum`, `apk` install/update commands -> `pkg`
- common package-name translations
- unambiguous npm script rewrites

PocketPort leaves ambiguous shell forms, unknown commands, pipes, command substitutions and complex chained expressions untouched.

> A patcher that confidently destroys working projects is not automation, it is vandalism with branding.

Patch details are written to:

```text
.pocketport/patch-report.json
```

## One-command preparation

```bash
pocketport prepare .
```

This performs:

1. scan
2. safe patch
3. rescan
4. execution-plan generation
5. `termux-install.sh` generation

Generated artifacts include:

```text
.pocketport/report.json
.pocketport/execution-plan.json
termux-install.sh
termux-run.sh   # when a trustworthy run command exists
```

## Local phone bridge

PocketPort can expose a localhost-only bridge for the web UI and the planned APK:

```bash
pocketport serve
```

The bridge can build local execution plans and prepare PocketPort-owned workspaces. When the bridge is connected, the web UI exposes **Run in Termux**: it prepares the repository locally, copies the exact generated install/run command, and opens Termux. The user still pastes and confirms the command in Termux, so the web page never silently executes shell code.

The web UI does not invent compatibility results; PocketPort Core remains the source of truth.

Web: https://pocketport.vercel.app/

## GitHub release assets

Pick the best release asset for the phone architecture:

```bash
pocketport asset owner/repo
pocketport asset owner/repo --tag v1.2.3
```

PocketPort prefers Android / Termux and matching `arm64` / `aarch64` artifacts, rejects foreign OS / architecture builds, and filters checksums and source archives.

## Project map

```text
GitHub repo
   |
   v
scan -> semantics -> component analysis
   |                    |
   +---- strategy ------+
            |
      native / hybrid / proot
            |
       safe patching
            |
      execution plan
            |
       Termux runtime
```

See [Architecture](docs/ARCHITECTURE.md) and [Roadmap](docs/ROADMAP.md).

## Current focus

PocketPort 0.3.x is focused on:

- repo-aware execution
- isolated prepared workspaces
- failure classification
- runtime-aware scoring
- safer Android approval / confinement
- APK companion UI
- public compatibility proof and reports

## Non-goals

PocketPort will not:

- make CUDA software run on a phone GPU
- emulate unavailable kernel features
- silently rewrite complicated shell logic
- claim a repository works when it has not actually been proven

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT.
