<p align="center">
  <img src="./assets/pocketport-logo.svg" alt="PocketPort" width="720">
</p>

<p align="center">
  <strong>Run more GitHub tools on Android.</strong><br>
  PocketPort scans desktop-first repositories, finds the assumptions that break on phones, chooses the safest Termux / hybrid / PRoot path, and prepares an explicit local execution plan.
</p>

<p align="center">
  <a href="https://pocketport.vercel.app/"><strong>Try the web scanner</strong></a>
  ·
  <a href="./docs/ROADMAP.md">Roadmap</a>
  ·
  <a href="./docs/ARCHITECTURE.md">Architecture</a>
  ·
  <a href="./experiments/deepseek-harness.md">DeepSeek Harness proof</a>
</p>

<p align="center">
  <img alt="status: public alpha" src="https://img.shields.io/badge/status-public%20alpha-f0b429">
  <a href="https://github.com/levomm/pocketport/actions/workflows/tests.yml"><img alt="tests" src="https://github.com/levomm/pocketport/actions/workflows/tests.yml/badge.svg"></a>
  <img alt="Android + Termux" src="https://img.shields.io/badge/Android-Termux-19c37d">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
  <img alt="license: MIT" src="https://img.shields.io/badge/license-MIT-8affc1">
</p>

<p align="center">
  <img src="./assets/pocketport-github-showcase.jpg" alt="PocketPort on Android" width="780">
</p>

> **Public alpha.** The compatibility engine and reference Android flow are real and testable today. The native companion is still being finished, the UX is moving quickly, and breaking changes are expected before the first stable release.

## The problem

Useful developer tools keep assuming there is a laptop somewhere nearby.

They expect Docker, systemd, glibc, distro package managers, fixed Linux paths, x86 binaries, desktop browser launchers, CUDA, or native modules that were never built for Android.

PocketPort asks a narrower question:

> **What would it take to run this repository locally on an Android phone without pretending Android is desktop Linux?**

It scans first, chooses a strategy, applies only conservative fixes, and keeps the final execution visible.

## What works today

| Area | Current state |
| --- | --- |
| Repository scanning | Working |
| Desktop / Linux assumption detection | Working |
| Native / hybrid / PRoot strategy selection | Working |
| Conservative compatibility rewrites | Working |
| Execution-plan generation | Working |
| Isolated workspace preparation | Working |
| Localhost phone bridge | Working |
| Web scanner | Working |
| DeepSeek Harness reference flow | Validated on Android 16 / aarch64 |
| Native Android companion | In active development |
| Stable APK release | Not published yet |
| Compatibility registry | Planned |

PocketPort is intentionally **not** presented as finished. The goal right now is to make the engine trustworthy before polishing the last 10% of the app shell into a very convincing lie. Software has enough of those already.

## How PocketPort decides

PocketPort chooses one of three execution paths:

| Strategy | Meaning |
| --- | --- |
| **native** | Run directly in Termux |
| **hybrid** | Apply narrow Android-safe fixes while retaining a PRoot fallback |
| **proot** | Use a rootless Linux userland when the project genuinely depends on desktop Linux assumptions |

The important rule is simple:

**visible failure > destructive guess**

If PocketPort cannot confidently rewrite something, it leaves it alone and reports the problem.

## Android flow

```text
GitHub repository
       |
       v
     scan
       |
       v
compatibility report
       |
       v
native / hybrid / proot
       |
       v
 safe patch + execution plan
       |
       v
 prepared local workspace
       |
       v
PocketPort companion -> Termux
```

The APK is a control surface. Termux remains the execution environment.

That keeps one compatibility engine instead of duplicating behavior in Kotlin and Python and then spending the rest of human history debugging why they disagree.

## Quick start

PocketPort currently targets Android + Termux.

```bash
pkg update -y
pkg install -y git python

git clone https://github.com/levomm/pocketport
cd pocketport

python -m pip install -e .
pocketport doctor
```

Start the local bridge:

```bash
pocketport serve
```

Scan a repository:

```bash
pocketport scan https://github.com/owner/repo
```

Prepare the current repository:

```bash
pocketport prepare .
```

Or let PocketPort create an isolated workspace for a public repository:

```bash
pocketport run https://github.com/owner/repo
```

## DeepSeek Harness reference proof

PocketPort has been used as a real Android compatibility layer for [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness).

Tested on **Android 16 / aarch64 / Termux**:

- dependency installation
- Web UI startup
- real model / agent turn
- shell execution
- session persistence
- filesystem write + read
- direct Termux execution with a narrow runtime shim
- no PRoot required for the tested path

This proves the current compatibility path. It does **not** mean every repository or every future Harness version is automatically supported.

Full notes: [experiments/deepseek-harness.md](./experiments/deepseek-harness.md)

## What PocketPort scans for

Common Android failure points include:

- Docker and Docker Compose assumptions
- systemd / `systemctl`
- distro package managers
- hard-coded `/usr/bin` and `/bin/bash`
- glibc-only binaries
- CUDA / NVIDIA dependencies
- x86-only assumptions
- native Node modules
- native / heavy Python dependencies
- browser / desktop launch assumptions
- runtime capability mismatches

## Conservative patching

Safe rewrites currently include:

- desktop bash shebangs -> Termux bash
- narrow `sudo` removal before known external commands
- `xdg-open` -> `termux-open`
- simple distro package install/update commands -> `pkg`
- common package-name translations
- unambiguous npm script rewrites

Ambiguous shell logic stays untouched.

Generated artifacts are kept visible:

```text
.pocketport/report.json
.pocketport/execution-plan.json
.pocketport/patch-report.json
termux-install.sh
termux-run.sh
```

## Project layout

```text
pocketport/
├── pocketport/          Python core + CLI
├── android-companion/   native Android companion
├── api/                 hosted scan API
├── web/                 mobile-first web scanner
├── experiments/         real compatibility reports
├── tests/               regression coverage
├── docs/                architecture, roadmap, launch notes
└── assets/              PocketPort brand assets
```

For the deeper model, see [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Road to the first stable release

The current work is focused on:

1. finishing and validating the native Android companion
2. installing the generated APK on the reference Android 16 device
3. adding native report / log views
4. publishing a tagged GitHub release with the APK attached
5. adding a second reference project with a different stack
6. recording a short end-to-end demo
7. tightening web metadata and public compatibility reporting

Track the actual checklist in [docs/ROADMAP.md](./docs/ROADMAP.md).

## Contributing

PocketPort needs ugly real-world repositories more than theoretical compatibility claims.

Useful contributions include:

- repositories that fail in Termux
- exact failure logs
- Android version + architecture
- native Termux vs PRoot results
- narrow reproducible compatibility patches
- regression tests for previously broken behavior

Start with [CONTRIBUTING.md](./CONTRIBUTING.md).

## Security

PocketPort executes locally and may prepare commands derived from third-party repositories. Treat untrusted repositories as untrusted code.

Security policy and reporting guidance: [SECURITY.md](./SECURITY.md).

## License

MIT. See [LICENSE](./LICENSE).
