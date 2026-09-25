# ha-atmos Copilot Instructions

## Critical AI Guidelines

1. Read `AGENTS.md` before changing behavior.
2. English only in code, comments, and docstrings.
3. Protocol work belongs in `py-atmos-serial` or `py-atmos-wg1000`, not here.
4. Do not invent RS485 frames or WG1000 register ids.

## Source selection

- Serial listen is push and primary when both transports are configured.
- WG1000 is pull and is the fallback after `fallback_after` seconds without a **decoded** serial sample.
- Raw bytes do not make serial fresh.
- A transport the user did not configure is never selected.

## Do not

- Commit credentials or live bus captures.
- Add polling to entities that listen on `AtmosRuntime`. The byte counter is the exception.
- Change `unique_id` values (`{entry_id}_active_source`, `{entry_id}_serial_bytes`, `{entry_id}_serial_link`).
