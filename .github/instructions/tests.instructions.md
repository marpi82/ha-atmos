---
applyTo: "tests/**"
---

# Tests

Import `custom_components.atmos.source` and `runtime` only. Do not import `wiring`, `config_flow`, or `sensor` here; those need Home Assistant.

Cover the source table: serial only, gateway only, both with a fresh decode, both with no decode, and the exact fallback boundary.
