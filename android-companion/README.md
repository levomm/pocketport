# PocketPort Android companion

Native Android control surface for PocketPort Core running in Termux.

## v0.1 flow

1. Start `pocketport serve` in Termux.
2. Open the PocketPort companion.
3. Confirm the local bridge is reachable.
4. Enter a public GitHub repository.
5. Build a local execution plan.
6. Prepare the repository in PocketPort's Termux workspace.
7. Copy the exact generated command and open Termux.
8. Paste and press Enter to approve execution.

The APK never runs third-party repository code silently.

## Build baseline

- Android Gradle Plugin 9.4.0
- Gradle 9.6.0
- JDK 17
- compileSdk / targetSdk 37
- Compose BOM 2026.09.00
