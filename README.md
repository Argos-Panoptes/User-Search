# User Search

Product source for longitudinal profiling and cross-platform identity resolution.

**Harness docs (specs, platform notes):** `mission-control-harness/harness-dashboard/docs/products/user-search/`

## Layout (suggested)

```text
orchestrator/   # 12h cycle fan-out, identity resolver
api/            # FastAPI service
platforms/      # per-platform collectors (telegram, signal, …)
```

Copy your existing code into the folders above, then commit and push here.

## Remote

```bash
git remote add origin https://github.com/Argos-Panoptes/User-Search.git
git push -u origin main
```
