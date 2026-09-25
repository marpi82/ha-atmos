# AGENTS.md — ha-atmos

Home Assistant custom integration for ATMOS boilers. Today the live path is the local WG1000 WebSocket poll (`py-atmos-wg1000`). Distributed via **HACS** (custom repository) and GitHub Releases.

## Project shape

- **Domain**: `atmos`, package `custom_components/atmos/`.
- **Libraries**: `py-atmos-wg1000` (pull, poll) is active. `py-atmos-serial` stays pinned for a future RS485 listen path but is not offered in the config flow yet.
- **Home Assistant**: `2026.3.0` (`hacs.json`).
- **iot_class**: `local_push`. WG1000 still polls inside the integration; entities themselves do not poll, except the RS485 byte counter when serial is configured.
- **HACS**: `hacs.json` + `hacs/action` workflow. Releases: `scripts/release.sh` tags the current branch; GitHub Actions builds `ha-atmos-hacs.zip` via `.github/workflows/release.yml`. Bump `manifest.json` `"version"` to the exact tag before tagging.

## Source selection

Serial is primary when both are configured, and only after `decode_frames` emits a register update inside `fallback_after` seconds (default 120). Raw bytes do not count. WG1000 is used when serial is not configured, or when it is configured but not fresh and the gateway session is up.

`pull_register_ids()` returns the HOD16 wire ids from `registers.py` (temperatures, humidity, packed setpoints). Do not invent RS485 framing or WG1000 register ids in this repository — import them from `pyatmos_wg1000.protocol`.

## TODO(rs485)

Parked on purpose so WG1000 can ship first:

- Config flow goes straight to the gateway form; `serial_only` / `both` steps remain but are not in the user menu.
- `wiring.py` lazy-imports `pyatmos_serial` only when an entry still has `serial_port`.
- Dual-path policy in `source.py` / `runtime.py` stays.
- Re-enable the menu and serial diagnostics when the codec exists.

## Commands

```bash
uv sync --locked --group dev --group test
uv run --group dev --group test poe validate
```

CI uploads `coverage.xml` to Codecov when `CODECOV_TOKEN` is set. Repository rulesets are applied with `scripts/apply_github_hardening.sh`. Required checks on `main`: `secrets (gitleaks)`, `security (pip-audit)`, `quality (lint + typecheck)`, `tests (3.13)`, `hassfest`, `HACS Validation`, `build`.

`source.py`, `runtime.py`, and `registers.py` must stay free of Home Assistant imports so pytest can run without `homeassistant` installed.

Keep `manifest.json` library pins aligned with `pyproject.toml`, and `hacs.json` HA minimum aligned with docs (manifest has no HA version field).

## Conventions

English only. Ruff line length 130, Google docstrings. Entities use `should_poll = False` and `runtime.add_listener()`, except the byte counter. Diagnostic `unique_id` values are `{entry_id}_active_source`, `{entry_id}_serial_bytes`, and `{entry_id}_serial_link`. Value sensors use `{entry_id}_{translation_key}` from `registers.py`.
