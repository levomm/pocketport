# PocketPort launch kit

This file is the distribution checklist and copy bank for PocketPort.

## Core angle

Do not sell PocketPort as "another Android terminal app".

The hook is:

> **Paste a GitHub repo. PocketPort tells you whether it can run on Android, chooses the Termux/PRoot path, applies only safe fixes, and prepares the handoff.**

The strongest proof point is DeepSeek Harness running on Android through PocketPort.

## Launch order

1. GitHub README + screenshots
2. GitHub Release with APK and short changelog
3. DeepSeek Harness Discussions
4. DeepSeek Harness Discord
5. r/termux monthly project thread
6. r/androiddev monthly showcase thread
7. r/opensource / r/github only where self-promotion rules allow it
8. X / Mastodon / Hacker News after the repo and APK links are stable

## DeepSeek Harness Discussions post

**Title**

PocketPort: running DeepSeek Harness on Android / Termux

**Body**

I built PocketPort to answer a simple question: can a desktop-first GitHub project actually run on an Android phone?

PocketPort scans the repository, detects Linux/desktop assumptions, chooses native Termux vs hybrid vs PRoot, applies only conservative compatibility fixes, and prepares the local execution handoff.

I used DeepSeek Harness as a real compatibility target and got the tested flow running on Android 16 / aarch64 Termux, including the Web UI, a real agent/model turn, shell execution, session persistence, and filesystem access.

Repo: https://github.com/levomm/pocketport
Web scanner: https://pocketport.vercel.app/

I would especially value feedback on Android-specific runtime assumptions, sandboxing, and cases where Harness plugins still expect desktop Linux.

## r/termux monthly project thread

PocketPort is an open-source compatibility layer and Android companion for running more GitHub projects in Termux.

You paste a repository, PocketPort scans it for desktop/Linux assumptions, chooses native Termux / hybrid / PRoot, applies conservative fixes, and generates the install/run handoff.

I have been using DeepSeek Harness as one of the real-world test targets on Android 16 / aarch64.

Repo: https://github.com/levomm/pocketport
Web scanner: https://pocketport.vercel.app/

Feedback and nasty repos that break on Android are welcome.

## r/androiddev showcase

I built PocketPort, a native Android companion + Termux compatibility engine for GitHub projects.

The Android app is the control surface: scan repo, inspect compatibility, prepare workspace, view fixes, open GitHub, then hand off the generated command to Termux.

The interesting part for me was keeping the APK thin while the actual execution stays local in Termux instead of pretending Android can directly run every Linux repo.

Open source: https://github.com/levomm/pocketport

## Short post

**Run more GitHub tools on Android.**

PocketPort scans a repo, detects desktop assumptions, chooses Termux / hybrid / PRoot, applies safe fixes, and prepares the exact handoff on your phone.

GitHub: https://github.com/levomm/pocketport
Web: https://pocketport.vercel.app/

## DeepSeek maintainer note

Hi, I have been using DeepSeek Harness as a real-world Android compatibility target for PocketPort.

PocketPort is an open-source scanner/runtime planner for adapting desktop-first GitHub projects to Android + Termux. The tested Harness path is working on Android 16 / aarch64, including Web UI startup, agent turns, shell execution, persistence, and filesystem access.

I documented the Android-specific findings here:
https://github.com/levomm/pocketport/blob/main/experiments/deepseek-harness.md

I thought this might be useful to the Harness team because it exposes which runtime assumptions become visible on a phone. I am happy to keep testing compatibility as Harness changes.

## Assets to attach

Use these in this order:

1. final APK UI screenshot
2. cinematic PocketPort intro frame
3. scan/progress screenshot
4. DeepSeek Harness proof screenshot
5. architecture image only for technical audiences

Do not lead Reddit posts with four paragraphs of architecture. Humans have thumbs and limited patience.

## Release checklist

- [ ] final APK uses the new native UI
- [ ] final intro asset is in the APK
- [ ] final icon set is in Android resources
- [ ] version bumped
- [ ] all CI green
- [ ] PR merged
- [ ] GitHub Release created
- [ ] APK attached to Release, not only Actions artifact
- [ ] README points to latest release
- [ ] one clean install test on a phone
- [ ] one DeepSeek Harness end-to-end test
- [ ] publish DeepSeek Discussion
- [ ] publish r/termux project-thread comment
- [ ] publish r/androiddev showcase entry
