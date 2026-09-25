---
name: code-review
description: Review checklist for ha-atmos pull requests. Use when reviewing PRs to verify source selection, that protocol stays in the libraries, async safety, and that unique_ids stay stable.
---

# Code Review — ha-atmos

## 1. Source selection

- [ ] Serial is preferred only after a decoded register update inside `fallback_after`.
- [ ] Raw byte counts do not switch the active source to serial.
- [ ] WG1000 is used when it is the only configured transport, or as fallback when serial is stale and the session is up.
- [ ] A transport left out of the config entry is never selected.

## 2. Library boundary

- [ ] No RS485 framing or WG1000 register ids invented in this repo.
- [ ] `pull_register_ids()` stays empty until a real map exists.

## 3. Home Assistant

- [ ] State entities use `should_poll = False` and `runtime.add_listener()`, except the byte counter.
- [ ] `unique_id` values are unchanged.
- [ ] `strings.json` and `translations/en.json` match.

## 4. Gates

- [ ] Ruff and mypy `--strict` on `source.py`, `runtime.py`, and `const.py`.
- [ ] Tests cover the policy without a live gateway or serial port.
