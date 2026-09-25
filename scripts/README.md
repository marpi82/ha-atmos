# Scripts

- `check_patch_coverage.sh` — pre-push gate: 80% project coverage and 100% patch coverage against `origin/main`. Home Assistant platform modules are omitted until they have a Home Assistant test harness.
- `release.sh` — create an annotated CalVer tag for HACS after bumping `manifest.json` `"version"` to the same string. Pre-releases: `./scripts/release.sh 2026.x.y alpha` (or `beta` / `rc`). Stable only from `main` after a live HACS smoke.
- `apply_github_hardening.sh` — repository settings, secret scanning, vulnerability alerts, and rulesets (including `HACS Validation` as a required check). Requires `gh` with admin rights. This repo does not enable GitHub Pages.

```bash
scripts/apply_github_hardening.sh
```
