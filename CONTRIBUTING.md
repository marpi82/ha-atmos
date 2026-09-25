# Contributing to ha-atmos

1. Open an issue using the [templates](https://github.com/marpi82/ha-atmos/issues/new/choose).
2. Branch from `main` and open a pull request. The [PR template](.github/PULL_REQUEST_TEMPLATE.md) applies automatically.
3. For local setup and HACS release process, see [DEVELOPMENT.md](DEVELOPMENT.md).

Do **not** file security issues publicly — see [SECURITY.md](SECURITY.md).

Protocol changes belong in `py-atmos-serial` or `py-atmos-wg1000`. Keep
`manifest.json` library pins in sync with `pyproject.toml`, and the
`hacs.json` Home Assistant minimum in sync with docs.

```bash
uv sync --locked --group dev --group test
uv run --group dev --group test poe validate
```

Branch protection: [.github/branch-protection-checklist.md](.github/branch-protection-checklist.md).
