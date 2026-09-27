# PocketPort roadmap

PocketPort is moving from a strong CLI prototype into a polished Android-first product.

The order below is intentional: prove the engine, make the flow obvious, then wrap it in an APK. No decorative app shell should outrun the core compatibility logic.

## 0. Stabilize current core work

- [ ] Resolve the two command-position rewrite findings in PR #26.
- [ ] Run the full Python test matrix.
- [ ] Run DeepSeek Harness smoke checks.
- [ ] Merge only after the patcher remains conservative.

## 1. GitHub / project polish

- [x] Add PocketPort brand assets.
- [x] Tighten the README around the actual product.
- [x] Add architecture and roadmap docs.
- [ ] Add screenshots / short demo GIF.
- [ ] Add SECURITY.md and issue templates.
- [ ] Publish a tagged release matching the package version.

## 2. Compatibility proof

DeepSeek Harness is the reference project.

- [x] Android 16 / aarch64 Termux validation.
- [x] npm install, Web UI, real model/agent turn.
- [x] shell execution.
- [x] session persistence.
- [x] native filesystem read/write.
- [ ] Publish a compact compatibility report in the README.
- [ ] Capture a 10-15 second end-to-end demo.
- [ ] Add another reference project with a different stack.

## 3. One-command repo flow

Target UX:

```bash
pocketport run https://github.com/owner/repo
```

Pipeline:

1. normalize repository
2. fetch / clone
3. scan
4. choose native / hybrid / proot
5. apply only safe patches
6. build execution plan
7. prepare workspace
8. show the exact install and run commands
9. execute only after explicit user approval

## 4. Phone bridge

The web UI should become a control surface for PocketPort Core already running in Termux.

- [x] localhost bridge
- [x] local execution plan
- [x] local workspace preparation
- [ ] clearer bridge onboarding
- [ ] one-tap copy of install / run commands
- [ ] Android deep-link / intent handoff where practical
- [ ] explicit bridge health and capability panel

## 5. PocketPort APK

First APK is a companion, not a replacement for Termux.

```text
PocketPort APK
  -> repo URL
  -> scan
  -> compatibility report
  -> native / hybrid / proot strategy
  -> Run in Termux
  -> View logs / report
```

Suggested first implementation:

- Kotlin + Jetpack Compose
- PocketPort Core remains Python in Termux
- loopback bridge for local planning / preparation
- Android intents for handoff
- no root requirement

Later, stable parts of the scanner can move into a native shared core if that becomes useful.

## 6. Web polish

- [ ] use final PocketPort branding
- [ ] visible proof / example result before first scan
- [ ] install / Termux action after scan
- [ ] Open Graph image and social metadata
- [ ] structured metadata
- [ ] lightweight analytics for scan / copy / install actions

## 7. Compatibility registry

Later, once the scanner behavior is stable:

- public compatibility registry
- repository badges
- per-repo recipes
- community reports
- known-good Android / architecture combinations
