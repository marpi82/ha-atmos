# Changelog

## [Unreleased]

### Fixed

- WG1000 WebSocket drops no longer leave the integration dead until reload;
  the poll task re-logins with backoff and resumes Info/circuit updates.

## [2026.9.0a6] - 2026-09-26

### Changed

- Require `py-atmos-wg1000==2026.9.0b10`.
- Info value ``unique_id`` values always use ``_p{i}``; once a dual part has
  appeared it is recreated after restart and stays unavailable when the live
  dump has fewer halves.

### Fixed

- Mixed Info duals (``°C / Tryb letni``) keep both entities under the panel
  caption instead of ``Tryb letni: Tryb letni``.
- Transition from one to two Info parts no longer drops the first entity
  (``known`` + legacy bare ``unique_id``).

## [2026.9.0a5] - 2026-09-26

### Changed

- Require Home Assistant `>=2026.8.0` (`via_device_id` only; no `via_device` fallback).
- Split Info display strings into typed sensors / binary sensors / valve enums; `---` → unknown.
- Add homepage circuit `climate` + comfort/reduced `number` entities (PARAM HOD16 read/write).
- Expose all eight `Regime_menu` climate presets (holiday…standby) with gateway-language translations.
- Require `py-atmos-wg1000==2026.9.0b9`.

### Fixed

- Info mode rows: device title shows effective regime (``Komfort`` / ``Standby``),
  ``Tryb`` holds the selection (``Auto`` or the same bare value); TextA wins over
  OwnText circuit captions.
- Clear stale entity-registry name overrides so renamed Info parts (e.g. frozen
  ``Tryb (1)``) pick up library names after update.
- Single-word statuses (``Dozwolone``) stay under the panel caption; binary duals
  keep the caption (no entity named ``OFF``).
- Dashed captions keep the full panel head; empty OwnText[4] / TUV titles use
  LanguageCatalog ``T16_94`` (``CWU`` / ``DHW`` / ``TUV``) before a hardcoded
  ``TUV`` fallback.

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
