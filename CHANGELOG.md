# Changelog

## Unreleased

### Added

- Sketch integration: RS485 listen as the primary push source, WG1000 poll as the fallback.
- CI, HACS validation, Codecov upload, and repository hardening script.
- HACS release path: `scripts/release.sh`, release drafter, and GitHub Release zip (`ha-atmos-hacs.zip`).
- Pin `py-atmos-serial==2026.9.0a1` and `py-atmos-wg1000==2026.9.0b1` in `manifest.json` for HassOS installs.
