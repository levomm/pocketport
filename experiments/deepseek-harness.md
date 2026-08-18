# DeepSeek Harness on Android/Termux

This experiment validates PocketPort against `deepseek-ai/deepseek-harness` without blocking the 0.2.1 hotfix.

## Result

**Status: working natively in Termux with a PocketPort runtime compatibility shim.**

The validation reached a real end-to-end agent run, not only installation or UI startup:

- DeepSeek Harness installed from npm directly in Termux
- the Web UI started at `http://127.0.0.1:3080`
- model requests and the agent loop worked
- shell execution worked on Android
- session persistence worked through the PocketPort Node runtime shim
- the Harness filesystem `write` tool created a file without a shell workaround
- the Harness filesystem `read` tool read the file back successfully

The final filesystem test wrote exactly:

```text
PocketPort Android atomic write test OK
```

and read the same content back through the native Harness filesystem tools.

## Validated host

```text
Android: 16
Architecture: aarch64
Kernel: Linux 6.1.157-android14-11
Node: v22.22.0
Workspace: /data/data/com.termux/files/home/dsh-termux-test
```

The shell validation also successfully returned `uname -a`, `node --version`, and `pwd` from an agent turn.

## Initial PocketPort scan

The upstream repository initially scored:

```text
PocketPort score: 44/100
Strategy: hybrid
Stack: node, python
```

The scan correctly found desktop-oriented assumptions, including native Node packages, glibc/x86 references, distro package-manager assumptions and CI/build paths.

The runtime result shows that the current score is too pessimistic for end-user execution. Several findings are development-, CI- or build-only and should not carry the same weight as a true runtime blocker. This experiment is therefore also a test case for future runtime-aware scoring.

## Runtime blocker 1: hard links in session persistence

DeepSeek Harness intentionally publishes some files with `link()` rather than `rename()` so a concurrent writer cannot silently overwrite an existing target.

On the validated Termux filesystem a direct hard-link attempt returned `Permission denied`.

PocketPort now injects a Node preload shim through `pocketport run`. For narrowly recognized atomic-publish patterns it:

1. attempts the original `link()` first
2. only handles `EACCES` / `EPERM`
3. falls back to `copyFile(..., COPYFILE_EXCL)`
4. preserves no-clobber behavior by refusing to replace an existing target
5. leaves ordinary hard-link calls untouched

The shim also calls `syncBuiltinESMExports()` because Harness imports named functions from `node:fs/promises`.

## Runtime blocker 2: filesystem guarded-create staging

The Harness filesystem provider uses another atomic guarded-create shape:

```text
.<target>.<pid>.<uuid>.tmpdir/<target>.tmp -> <target>
```

That path also publishes through a hard link. The first PocketPort shim intentionally did not match it, so the filesystem `write` tool still received `EACCES` and the agent temporarily worked around it with shell output redirection.

PocketPort was then extended to recognize this second staging pattern while keeping the fallback deliberately narrow. After reinstalling the updated experiment build, the Harness `write` and `read` tools succeeded without Bash or another shell workaround.

## Sandbox limitation

Harness `workspace-write` confinement was not usable on the validated Android/Termux host. Harness correctly failed closed and offered escalation.

The successful end-to-end test therefore used the Harness `danger-full-access` execution mode in an isolated test workspace.

That is acceptable for validation but is **not** the desired PocketPort default. A future Termux execution policy should separate these concerns:

- bypass an unavailable native confinement backend when necessary
- keep human approval enabled for risky commands
- avoid coupling unconfined execution to a `never ask` approval policy

## What this proves

For this repository, PRoot was not required for the tested user workflow. The practical strategy is currently better described as:

```text
native + runtime compatibility shim
```

rather than the original static-scan `hybrid` result.

This is the first PocketPort case where scanner findings, real Android execution, runtime failure classification and a reusable compatibility shim were exercised together.

## Remaining work

- add runtime capability probes to `pocketport doctor`
- design a safer Termux approval/confinement fallback
- distinguish runtime blockers from CI/build/dev-only findings in scanner scoring
- turn validated compatibility results into reusable per-project recipes or registry entries

The experiment remains isolated from `main` until the 0.2.1 hotfix is merged.
