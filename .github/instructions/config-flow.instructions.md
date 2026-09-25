---
applyTo: "custom_components/atmos/config_flow.py,custom_components/atmos/strings.json,custom_components/atmos/translations/**"
---

# Config flow

Three modes: RS485 only, WG1000 only, or both.

Both means serial listen first, WG1000 poll as fallback. The options flow exposes `fallback_after` only when both are configured.

Keep `translations/en.json` identical to `strings.json`.
