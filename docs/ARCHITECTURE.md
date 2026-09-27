# PocketPort architecture

PocketPort is an Android-first compatibility layer for desktop-first GitHub projects.

## Current shape

```text
GitHub repository
      |
      v
+------------------------+
| PocketPort Core        |
|------------------------|
| scanner                |
| semantic classifier    |
| component assessment   |
| conservative patcher   |
| execution planner      |
| workspace preparation  |
| runtime compatibility  |
+-----------+------------+
            |
      +-----+------+
      |            |
      v            v
   Termux        PRoot
   native       fallback
      |
      v
 project runtime
```

The browser UI is deliberately not the source of compatibility truth. It renders Core output.

## Repository layout

```text
pocketport/
├── pocketport/              # Python core and CLI
│   ├── scanner.py           # static compatibility detection
│   ├── semantics.py         # artifact / project interpretation
│   ├── components.py        # runnable-surface analysis
│   ├── patcher.py           # conservative safe rewrites
│   ├── execution.py         # execution-plan construction
│   ├── workspace.py         # prepared local workspaces
│   ├── runtime.py           # Termux runtime compatibility
│   ├── doctor.py            # device / capability probes
│   ├── release.py           # release asset selection
│   ├── bridge.py            # localhost bridge for the web / APK
│   └── cli.py               # CLI entry point
├── api/
│   └── scan.py              # hosted scan API
├── web/                     # mobile-first browser UI
│   ├── index.html
│   ├── app.js
│   ├── adapter.js
│   └── bridge-probe.js
├── experiments/             # validated real-project reports
│   ├── deepseek-harness.md
│   └── plandex.md
├── tests/                   # regression coverage
├── assets/                  # brand assets
├── docs/                    # architecture / roadmap
└── .github/workflows/       # CI and smoke tests
```

## Android companion layer

```text
android/
└── app/
    ├── ui/
    │   ├── dashboard
    │   ├── scan
    │   ├── report
    │   ├── terminal
    │   └── settings
    ├── bridge/
    │   ├── PocketPortClient
    │   └── TermuxIntent
    └── model/
        └── CompatibilityReport
```

The APK should initially talk to `pocketport serve` on localhost. This keeps one compatibility engine instead of creating two implementations that slowly disagree with each other, because apparently one source of truth is already a luxury in software.

## Strategy model

### native

Run directly in Termux with no Linux userland fallback.

### hybrid

Use safe Android / Termux patches where confidence is high, while retaining a PRoot fallback for parts that still expect desktop Linux.

### proot

Run in a rootless Linux userland when the repository genuinely depends on glibc, distro layout, or other desktop assumptions.

## Safety rule

PocketPort must prefer a visible failure over a destructive guess.

Automatic rewrites are allowed only when the transformation is narrow and testable. Ambiguous shell expressions stay untouched and are surfaced in the compatibility report.
