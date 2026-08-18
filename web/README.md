# PocketPort web UI

Mobile-first browser interface for PocketPort Core.

PocketPort Core remains the source of compatibility truth. The web layer presents scanner output and does not recompute score, strategy, findings, or component assessments.

## Visual direction

The current prototype uses a graphite-black base with a restrained cold-green signal accent. The home screen is intentionally compact and tool-like: repository input first, one scan action, no landing-page feature clutter. Technical values use JetBrains Mono; prose uses Work Sans.

## Current scan sources

- Future hosted PocketPort scan service through the adapter.
- Exact recorded PocketPort CLI JSON for explicitly captured repositories.
- Unknown repositories return `unavailable`; the UI never invents a verdict.

## Static preview

The directory is dependency-free and can be hosted as static files. `vercel.json` rewrites app routes to `index.html`.
