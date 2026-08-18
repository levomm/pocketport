# DeepSeek Harness smoke test

This experiment validates PocketPort against `deepseek-ai/deepseek-harness` without blocking the 0.2.1 hotfix.

Current focus:
- scan the upstream repository
- dry-run safe patches
- generate a Termux installer
- verify pnpm-aware install generation
- capture reports as CI artifacts

The experiment is intentionally isolated from `main` until the 0.2.1 hotfix is merged.
