# PocketPort Android companion

First native companion shell for PocketPort.

Current scope:

- native Jetpack Compose UI
- repository input
- opens the matching PocketPort Web scan
- copies `pocketport serve`
- opens Termux when installed
- no root requirement

Next wiring step:

1. call the localhost PocketPort bridge directly from the APK
2. show bridge health and capabilities natively
3. request a local execution plan
4. prepare the workspace
5. show the exact install/run command
6. hand off to Termux only after explicit approval

Package: `ee.osx01.pocketport`

The APK remains a companion to PocketPort Core in Termux. It does not execute arbitrary repository code itself.
