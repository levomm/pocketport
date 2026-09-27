# Security Policy

PocketPort modifies and prepares third-party repositories for Android / Termux. Treat every scanned or prepared project as untrusted code.

## Supported versions

Security fixes are applied to the latest development line unless a release note says otherwise.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose users to arbitrary command execution, unsafe patching, path traversal, credential exposure, or bridge abuse.

Use GitHub's private vulnerability reporting for this repository when available.

Include:

- affected PocketPort version / commit
- Android and Termux version
- minimal reproduction
- repository or fixture that triggers the issue
- whether the problem occurs during scan, patch, prepare, bridge, or runtime execution
- expected and actual behavior

## Security boundaries

PocketPort intentionally follows these rules:

- scanning should not execute target repository code
- automatic patching must remain conservative and reviewable
- prepared workspaces should stay inside PocketPort-owned directories
- localhost bridge endpoints must not silently execute installers or project commands
- explicit user approval is required before execution
- ambiguous shell logic should be reported, not guessed at
- credentials and tokens must not be copied into generated reports

## Android / Termux note

Android sandbox behavior differs from desktop Linux. PocketPort does not claim that Termux, PRoot, or a compatibility shim provides the same confinement guarantees as a desktop sandbox.
