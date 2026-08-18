# PocketPort Web

Mobile-first interface for PocketPort Core.

This first pass is intentionally dependency-free and can be hosted as a static site. PocketPort Core remains the sole source of compatibility truth.

## Data modes

- `service`: set `window.__POCKETPORT_CONFIG__.scanUrl` before `adapter.js` to call a future hosted PocketPort scan endpoint.
- `recorded`: exact JSON captured from the current PocketPort CLI for explicitly supported public repositories.
- `unavailable`: unknown repositories show no fabricated verdict.

## Local preview

```bash
cd web
python -m http.server 8080
```

Then open `http://localhost:8080`.
