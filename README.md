# ATMOS

[![Release](https://img.shields.io/github/v/release/marpi82/ha-atmos?include_prereleases&label=release)](https://github.com/marpi82/ha-atmos/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/marpi82/ha-atmos/ci.yml?branch=main&label=CI)](https://github.com/marpi82/ha-atmos/actions/workflows/ci.yml)
[![HACS](https://img.shields.io/github/actions/workflow/status/marpi82/ha-atmos/hacs.yml?branch=main&label=HACS)](https://github.com/marpi82/ha-atmos/actions/workflows/hacs.yml)
[![Codecov](https://codecov.io/gh/marpi82/ha-atmos/graph/badge.svg)](https://codecov.io/gh/marpi82/ha-atmos)
[![License](https://img.shields.io/github/license/marpi82/ha-atmos)](https://github.com/marpi82/ha-atmos/blob/main/LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%E2%89%A52026.3.0-blue)](https://www.home-assistant.io/)

Home Assistant custom integration for an ATMOS boiler. It can use a passive
RS485 listen (`py-atmos-serial`), the local WG1000 WebSocket
(`py-atmos-wg1000`), or both.

**Status:** WG1000 poll path is live for outdoor / circuit / DHW temperatures,
humidity, and comfort/reduced setpoints. RS485 listen stays pinned as a
dependency but is hidden in the config flow until the serial codec exists.
There are no pump or mixing-valve entities yet (status words need more reverse
engineering in `py-atmos-wg1000`).


## How the two paths combine

| Configured | What runs | Entity values |
| --- | --- | --- |
| RS485 only | Passive listen (push). The port is read continuously. | Serial, once a frame decodes. Today that never happens. |
| WG1000 only | Login, then poll (pull). The gateway does not push. | WG1000, once register ids exist. The poll loop is idle until then. |
| Both | Listen and stay logged in to the gateway. | Serial while a **decoded** sample is newer than the fallback window (default 120 s). Otherwise WG1000. |

Raw bytes do not make serial "fresh". Until the codec exists, a dual setup
stays on WG1000 whenever that session is up. Options → fallback window is
shown only when both paths are configured.

Diagnostic entities:

* **Active source** — `serial`, `wg1000`, or `none`
* **RS485 link** / **RS485 bytes seen** — only when an entry still configures serial

WG1000 value sensors (decoded with the library helpers): outdoor and circuit/DHW
temperatures, humidity, and comfort/reduced setpoints.

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://github.com/marpi82/ha-atmos` with category **Integration**.
3. Search for **ATMOS**, install, and restart Home Assistant.
4. Settings → Devices & services → Add integration → **ATMOS**.

Testers: enable HACS **Show beta versions** to install `alpha` / `beta` / `rc`
tags before they hit the default (stable) channel. See
[DEVELOPMENT.md](DEVELOPMENT.md#publishing-releases).

### Manual installation

1. Download `ha-atmos-hacs.zip` from a
   [GitHub Release](https://github.com/marpi82/ha-atmos/releases).
2. Extract and copy `custom_components/atmos` into your Home Assistant
   `custom_components` directory.
3. Restart Home Assistant and add the integration from the UI.

Home Assistant installs the PyPI pins from `manifest.json`
(`py-atmos-serial`, `py-atmos-wg1000`) on startup.

## Layout

`custom_components/atmos/` is the integration. `source.py` and `runtime.py`
do not import Home Assistant, so the switch can be tested on its own.
`wiring.py` opens the port and the gateway.

## Local development

Editable sibling checkouts override the PyPI pins via `[tool.uv.sources]`:

```bash
uv sync --locked --group dev --group test
uv run --group dev --group test poe validate
```

Python matches the sibling libraries. Home Assistant minimum is `2026.3.0`
(`hacs.json`).

## Contributions are welcome!

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [DEVELOPMENT.md](DEVELOPMENT.md).
Use the [issue forms](https://github.com/marpi82/ha-atmos/issues/new/choose)
and the pull request template.

## Support

- GitHub Issues: https://github.com/marpi82/ha-atmos/issues/new/choose
- Home Assistant Community: https://community.home-assistant.io/

Do **not** file security issues publicly — see [SECURITY.md](SECURITY.md).

## License

MIT License — see [LICENSE](LICENSE).
