# AGENTS.md — ha-atmos

Sketch of a Home Assistant integration that combines a passive ATMOS RS485 listen with the WG1000 local WebSocket.

## Project shape

- **Domain**: `atmos`, package `custom_components/atmos/`.
- **Libraries**: `py-atmos-serial` (push, listen) and `py-atmos-wg1000` (pull, poll). Protocol work stays in those libraries.
- **Home Assistant**: `2026.3.0` (`hacs.json`).
- **iot_class**: `local_push`. WG1000-only still polls inside the integration; entities themselves do not poll, except the RS485 byte counter.

## Source selection

Serial is primary when both are configured, and only after `decode_frames` emits a register update inside `fallback_after` seconds (default 120). Raw bytes do not count. WG1000 is used when serial is not configured, or when it is configured but not fresh and the gateway session is up. A transport the user left out is never selected.

`pull_register_ids()` returns `()` until the map is known, and the gateway task stays logged in without polling.

Do not invent RS485 framing or WG1000 register ids in this repository.

## Commands

```bash
uv run --group dev --group test poe test
```

`source.py` and `runtime.py` must stay free of Home Assistant imports so pytest can run without `homeassistant` installed.

## Conventions

English only. Ruff line length 130, Google docstrings. Entities use `should_poll = False` and `runtime.add_listener()`, except the byte counter. `unique_id` values are `{entry_id}_active_source`, `{entry_id}_serial_bytes`, and `{entry_id}_serial_link`.
