---
applyTo: "custom_components/atmos/**"
---

# Integration core

- English only. Ruff line length 130. Google docstrings.
- `source.py` and `runtime.py` must not import Home Assistant.
- Serial is the push source. WG1000 is the pull fallback.
- Do not invent a frame layout or a register map here.
