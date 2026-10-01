# Contributing to PocketPort

PocketPort is an Android-first compatibility project. The most valuable contributions are concrete, reproducible failures and small fixes that make one class of repository behave better without breaking another.

## Good contributions

Useful reports include:

- a public repository that fails in Termux
- the exact command that failed
- the smallest useful error log
- Android version
- device architecture
- Termux package / environment details
- whether native Termux, hybrid handling, or PRoot changed the result
- a minimal patch or regression fixture when possible

A vague "doesn't work on Android" report gives everyone the rare opportunity to learn absolutely nothing.

## Before opening a PR

Run the test suite:

```bash
python -m pip install -e .
pytest
```

For scanner or patcher changes, add or update a regression test.

For runtime changes, include the device and environment used for validation.

## Design rules

PocketPort follows a few non-negotiable rules:

1. Prefer a visible failure over a destructive guess.
2. Automatic rewrites must be narrow and testable.
3. Do not silently execute generated commands.
4. Keep Android-specific behavior explicit.
5. Keep the core engine independent from the UI.
6. Do not include secrets, tokens, private repository data, or proprietary source in fixtures.

## Compatibility reports

When opening a compatibility issue, include:

```text
Repository:
Commit / tag:
Android version:
Architecture:
Termux version:
Strategy tried: native / hybrid / proot

Command:
<exact command>

Failure:
<minimal relevant output>

What changed the result:
<if known>
```

## Pull requests

Keep PRs focused. A compatibility fix should ideally solve one class of failure and contain a regression test that demonstrates why the change is safe.

The PR template asks for safety impact and Android / Termux validation. Fill those sections in rather than decorating them with optimism.

## Scope

PocketPort is not trying to emulate an entire desktop Linux distribution inside Android.

Changes fit the project when they improve one or more of these areas:

- repository compatibility detection
- execution-strategy selection
- conservative Android / Termux rewrites
- local workspace preparation
- localhost bridge behavior
- Android companion UX
- reproducible compatibility evidence
- tests, documentation, or security hardening
