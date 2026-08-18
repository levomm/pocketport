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
Python: 3.14.6
Node: v22.22.0
Workspace: /data/data/com.termux/files/home/dsh-termux-test
```

The shell validation also successfully returned `uname -a`, `node --version`, and `pwd` from an agent turn.

## PocketPort scan: before and after runtime-aware scoring

The original static scanner reported:

```text
PocketPort score: 44/100
Strategy: hybrid
Stack: node, python
```

That scan correctly found desktop-oriented assumptions, but it treated runtime dependencies, lockfile metadata, CI workflows and build-only scripts too similarly.

After this experiment fed real Android evidence back into the scanner, findings gained a `scope` such as `runtime`, `optional`, `build`, `dev`, `ci` or `metadata`. CI and lockfile-only assumptions remain visible but no longer reduce runtime compatibility confidence, and native dependencies are treated as risks to validate rather than proof of failure.

The same upstream DeepSeek Harness revision now reports in CI:

```text
PocketPort score: 70/100
Strategy: native
Stack: node, python
```

Examples from the new report:

```text
MEDIUM [dev]      node-native: playwright
MEDIUM [runtime]  node-native: sharp
MEDIUM [runtime]  node-native: node-pty
MEDIUM [metadata] linux-assumption: glibc dependency [pnpm-lock.yaml]
MEDIUM [ci]       linux-assumption: Debian/Ubuntu package manager [.github/workflows/...]
MEDIUM [build]    linux-assumption: glibc dependency [native/landlock-run/scripts/build.ts]
```

The score intentionally remains below 100 because untested native runtime dependencies still represent compatibility risk. The important correction is that those risks no longer automatically force a `hybrid` strategy after the actual runtime has demonstrated that native execution works.

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

## Runtime capability doctor

The experiment feeds the discovered host assumptions back into `pocketport doctor`. The probe was executed on the real Android host and returned:

```text
native hardlink        denied - Permission denied
Node exclusive copy    ok - COPYFILE_EXCL preserves no-clobber behavior
PocketPort Node shim   ok - atomic publish works through pocketport run compatibility
sandbox confinement    project-specific
```

One additional Android-specific issue was found while validating the doctor itself: this Termux Python 3.14 build does not expose `os.link`. PocketPort now detects that and falls back to probing the host through the POSIX `ln` utility rather than crashing or mistaking the missing Python wrapper for a filesystem result.

This turns the manual hard-link and Node copy checks used during the investigation into reusable diagnostics for the next port.

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

The runtime-aware scanner now also selects `native`, matching the real Android result instead of the original `hybrid` prediction.

This is the first PocketPort case where scanner findings, real Android execution, runtime failure classification, reusable host diagnostics and a runtime compatibility shim were exercised together.

## Remaining work

- design a safer Termux approval/confinement fallback
- continue improving scope classification without hiding genuine runtime blockers
- turn validated compatibility results into reusable per-project recipes or registry entries

The experiment remains isolated from `main` until the 0.2.1 hotfix is merged.
