# Development — ha-atmos

Sketch Home Assistant integration. Protocol work stays in
`py-atmos-serial` and `py-atmos-wg1000`.

## Setup

```bash
uv sync --locked --group dev --group test
uv run --group dev --group test poe validate
```

Sibling libraries are editable path sources in `pyproject.toml`. CI checks
out `marpi82/py-atmos-serial` and `marpi82/py-atmos-wg1000` at `main` and
symlinks them next to the workspace the same way.

`source.py` and `runtime.py` must not import Home Assistant so unit tests run
without it.

## Field-testing library pins on HassOS

On **HassOS / HACS**, do **not** pin libraries with `git+https://…@sha` in
`manifest.json`. HACS updates overwrite local edits, and git installs are a
poor fit for HassOS.

1. Publish a library pre-release to PyPI from
   [py-atmos-serial](https://github.com/marpi82/py-atmos-serial) and/or
   [py-atmos-wg1000](https://github.com/marpi82/py-atmos-wg1000).
2. Bump the exact pins in `custom_components/atmos/manifest.json`
   `requirements` and keep `pyproject.toml` / `uv.lock` aligned.
3. Commit the pin, bump `manifest.json` `"version"` to the next integration
   tag, then cut a HACS pre-release with `scripts/release.sh`.
4. On the live HA instance: HACS → **Show beta versions** → install/update
   ATMOS.

## Publishing releases

Do **not** cut a stable HACS tag until the same version has been smoke-tested
as a HACS **pre-release** on a live Home Assistant install.

| Branch | Allowed tags |
|--------|----------------|
| `main` | Stable (`2026.x.y`) and pre (`aN` / `bN` / `rcN`) |
| `release/YYYY.M` | Pre only — `release.sh` and the release workflow refuse stable |

Bump `custom_components/atmos/manifest.json` `"version"` to the **exact** tag
string before tagging (the HACS zip embeds that file). Tags do **not** use a
`v` prefix.

```bash
# Pre-release first
./scripts/release.sh 2026.x.y alpha   # or beta / rc

# Stable — only after live smoke; only from main
./scripts/release.sh 2026.x.y stable
```

GitHub Actions (after CI succeeds on the tagged push) builds the wheel,
creates `ha-atmos-hacs.zip`, and attaches both to a GitHub Release. Pre tags
are marked prerelease so HACS keeps them on the beta channel.

Release channel rules and rulesets:
[.github/branch-protection-checklist.md](.github/branch-protection-checklist.md).
