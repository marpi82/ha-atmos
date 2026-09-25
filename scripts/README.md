# Scripts

- `check_patch_coverage.sh` — pre-push gate: 80% project coverage and 100% patch coverage against `origin/main`. Home Assistant platform modules are omitted until they have a Home Assistant test harness.
- `apply_github_hardening.sh` — repository settings, secret scanning, vulnerability alerts, and rulesets. Requires `gh` with admin rights. This repo does not enable GitHub Pages.

```bash
scripts/apply_github_hardening.sh
```
