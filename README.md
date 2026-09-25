# ATMOS

Home Assistant custom integration for an ATMOS boiler. It can use a passive
RS485 listen (`py-atmos-serial`), the local WG1000 WebSocket
(`py-atmos-wg1000`), or both.

**Status:** sketch. RS485 framing is not reverse-engineered, and the WG1000
register map used by this integration is empty. The config flow, the source
switch, and three diagnostic entities are in place. There are no boiler
sensors yet.

## How the two paths combine

| Configured | What runs | Entity values |
| --- | --- | --- |
| RS485 only | Passive listen (push). The port is read continuously. | Serial, once a frame decodes. Today that never happens. |
| WG1000 only | Login, then poll (pull). The gateway does not push. | WG1000, once register ids exist. The poll loop is idle until then. |
| Both | Listen and stay logged in to the gateway. | Serial while a **decoded** sample is newer than the fallback window (default 120 s). Otherwise WG1000. |

Raw bytes do not make serial "fresh". Until the codec exists, a dual setup
stays on WG1000 whenever that session is up. Options → fallback window is
shown only when both paths are configured.

Diagnostic entities (no register map yet):

* **Active source** — `serial`, `wg1000`, or `none`
* **RS485 link** — the port is open
* **RS485 bytes seen** — bytes read, including bytes that were not decoded

## Layout

`custom_components/atmos/` is the integration. `source.py` and `runtime.py`
do not import Home Assistant, so the switch can be tested on its own.
`wiring.py` opens the port and the gateway.

## Local install

Neither library has to be on PyPI for this sketch. From a Home Assistant
environment that can see both checkouts:

```bash
uv pip install -e ../py-atmos-serial -e ../py-atmos-wg1000
```

`manifest.json` lists `py-atmos-serial` and `py-atmos-wg1000`. Home Assistant
will try to install them on startup. Until they are published, install the
editable checkouts into the same environment and skip that pip step.

Python matches the sibling integration: Home Assistant `2026.3.0` or newer.

```bash
uv run --group dev --group test poe test
```
