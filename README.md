<p align="center">
  <img src="./assets/pocketport-logo.svg" alt="PocketPort" width="720">
</p>

<p align="center">
  <strong>Run more GitHub tools on Android.</strong><br>
  Scan a repository, choose the safest Termux path, prepare the workspace, and hand off the exact command to your phone.
</p>

<p align="center">
  <a href="https://pocketport.vercel.app/">Web scanner</a> ·
  <a href="./docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="./experiments/deepseek-harness.md">DeepSeek Harness proof</a> ·
  <a href="./docs/LAUNCH.md">Launch kit</a>
</p>

<p align="center">
  <img src="./assets/pocketport-github-showcase.jpg" alt="PocketPort on Android" width="760">
</p>

<p align="center">
  <a href="https://github.com/levomm/pocketport/actions/workflows/tests.yml"><img alt="tests" src="https://github.com/levomm/pocketport/actions/workflows/tests.yml/badge.svg"></a>
  <img alt="Android + Termux" src="https://img.shields.io/badge/Android-Termux-19c37d">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
  <img alt="MIT" src="https://img.shields.io/badge/license-MIT-8affc1">
</p>

## Why PocketPort

A lot of useful GitHub projects assume a desktop Linux machine. PocketPort checks those assumptions and tells you what can actually run on Android.

It chooses one of three paths:

| Path | What it means |
| --- | --- |
| **native** | Run directly in Termux |
| **hybrid** | Apply conservative fixes and keep a PRoot fallback |
| **proot** | Use a rootless Linux userland when desktop-Linux assumptions are real |

PocketPort does **not** claim every repo magically works on Android. It scans first, patches only when the change is unambiguous, and keeps execution explicit.

## Android flow

**01 Scan repo → 02 Connect phone → 03 Run in Termux**

The native Android companion talks to PocketPort Core on localhost. The APK is the control surface; Termux remains the execution environment.

Current companion flow:

- scan a GitHub repository
- inspect compatibility and execution strategy
- show fixes and plan details
- prepare a local PocketPort workspace
- open the repo on GitHub
- copy the generated command
- hand off to Termux with **Run in Termux**

## Quick start

```bash
pkg update -y
pkg install -y git python
git clone https://github.com/levomm/pocketport
cd pocketport
python -m pip install -e .
pocketport doctor
```

Start the phone bridge:

```bash
pocketport serve
```

Scan and prepare:

```bash
pocketport scan https://github.com/owner/repo
pocketport prepare .
```

Or let PocketPort prepare an isolated workspace for a public repository:

```bash
pocketport run https://github.com/owner/repo
```

## DeepSeek Harness proof

PocketPort has been tested end-to-end against [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) on **Android 16 / aarch64 Termux**.

Validated in the tested flow:

- installation
- Web UI startup
- real model / agent turn
- shell execution
- session persistence
- filesystem write + read
- direct Termux execution with a narrow PocketPort runtime shim
- no PRoot required for the tested path

Detailed notes: [experiments/deepseek-harness.md](experiments/deepseek-harness.md)

## What it scans

PocketPort looks for things that usually break desktop-first projects on Android:

- Docker / Docker Compose assumptions
- systemd / `systemctl`
- distro package managers
- hard-coded `/usr/bin` and `/bin/bash`
- CUDA / NVIDIA dependencies
- x86-only assumptions
- native Node modules
- native / heavy Python dependencies
- runtime capability mismatches

## Conservative patching

Safe rewrites currently include:

- desktop bash shebangs → Termux bash
- narrow `sudo` removal before known external commands
- `xdg-open` → `termux-open`
- simple distro package install/update commands → `pkg`
- common package-name translations
- unambiguous npm script rewrites

Ambiguous shell logic is left alone.

> A patcher that confidently destroys working projects is not automation. It is vandalism with branding.

## Generated files

```text
.pocketport/report.json
.pocketport/execution-plan.json
.pocketport/patch-report.json
termux-install.sh
termux-run.sh
```

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
       Android companion
            |
         Termux
```

## Status

PocketPort is still early and moving quickly. The current focus is repo-aware execution, safer Android handoff, isolated prepared workspaces, compatibility proof, and a polished native companion.

Contributions, test repos, failure reports, and Android edge cases are useful.

## License

MIT.
