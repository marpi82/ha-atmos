## Summary

<!-- What does this PR change and why? -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature / enhancement (non-breaking)
- [ ] Breaking change (`unique_id`, config entry keys, or source-selection rules)
- [ ] Docs only
- [ ] Tests / CI / tooling / chore

## Checklist

- [ ] English only in code, comments, and docs
- [ ] Source selection still prefers decoded RS485 and falls back to WG1000
- [ ] No invented frame layout or register ids
- [ ] `strings.json` matches `translations/en.json` when UI strings change
- [ ] `uv run --group dev --group test poe test` passes

## Test plan

```bash
uv run --group dev ruff check .
uv run --group dev mypy
uv run --group test pytest -q
```
