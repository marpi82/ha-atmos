# Changelog

## [Unreleased]

### Changed

- Rebuild WG1000 entities from the Info page dump (groups, OwnText names, gateway language).
- Require `py-atmos-wg1000==2026.9.0b3`.

## [2026.9.0a3] - 2026-09-25

### Added

- Config-entry reconfigure flow for WG1000 host, username, password, and TLS verify.
- Live connect + Hello + login probe during setup and reconfigure.

### Fixed

- Call `hello()` before `login()` on the gateway session.
- Strip `https://` / `wss://` prefixes from the host field.
- Avoid `return` inside a `finally` in the WG1000 pull task.
- Require `py-atmos-wg1000==2026.9.0b2` (non-blocking TLS context).

## [2026.9.0a2] - 2026-09-25

### Added

- Local HA brand images under `custom_components/atmos/brand/` (icon + logo, light/dark, @2x) from the official ATMOS mark.

## [2026.9.0a1] - 2026-09-25

### Added

- First HACS pre-release: WG1000 poll of outdoor / circuit / DHW temperatures, humidity, and packed setpoints.
- Dual-source runtime kept for a future RS485 path; serial / both are hidden in the config flow for now.
- HACS packaging (`ha-atmos-hacs.zip`) via GitHub Releases.

## Unreleased (historical notes)

### Added

- WG1000 poll of outdoor / circuit / DHW temperatures, humidity, and packed setpoints.
- Sketch dual-source runtime (RS485 primary when decoded, WG1000 fallback).
- CI, HACS validation, Codecov upload, and repository hardening script.
- HACS release path: `scripts/release.sh`, release drafter, and GitHub Release zip (`ha-atmos-hacs.zip`).
- Pin `py-atmos-serial==2026.9.0a1` and `py-atmos-wg1000==2026.9.0b1` in `manifest.json` for HassOS installs.

### Changed

- Config flow offers WG1000 only for now; serial / both steps remain for a later release.
- `wiring.py` lazy-imports `pyatmos_serial` so WG1000-only setups do not need it at import time.
