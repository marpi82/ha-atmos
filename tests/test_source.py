"""Source selection: serial when it is fresh, otherwise the configured fallback."""

from __future__ import annotations

import pytest

from custom_components.atmos.source import ActiveSource, SourceConfig, choose_source


def _at(
    *,
    serial: bool,
    wg1000: bool,
    serial_open: bool,
    gateway_open: bool,
    last_serial_update: float | None,
    now: float = 100.0,
) -> ActiveSource:
    """Evaluate one row of the source table."""
    config = SourceConfig(serial=serial, wg1000=wg1000, fallback_after=10)
    return choose_source(
        config,
        now=now,
        last_serial_update=last_serial_update,
        serial_open=serial_open,
        gateway_open=gateway_open,
    )


def test_window_must_be_positive() -> None:
    """A zero window would flip source on every sample."""
    with pytest.raises(ValueError, match="fallback window"):
        SourceConfig(serial=True, wg1000=True, fallback_after=0)


def test_serial_only_ignores_the_gateway() -> None:
    """A gateway the user did not configure is not a fallback."""
    assert _at(serial=True, wg1000=False, serial_open=True, gateway_open=True, last_serial_update=None) is ActiveSource.SERIAL
    assert _at(serial=True, wg1000=False, serial_open=False, gateway_open=True, last_serial_update=None) is ActiveSource.NONE


def test_gateway_only_ignores_serial() -> None:
    """Serial hardware is not used unless the user configured it."""
    assert _at(serial=False, wg1000=True, serial_open=True, gateway_open=True, last_serial_update=100.0) is ActiveSource.WG1000
    assert _at(serial=False, wg1000=True, serial_open=False, gateway_open=False, last_serial_update=None) is ActiveSource.NONE


def test_both_prefers_a_fresh_serial_sample() -> None:
    """Decoded serial data inside the window hides the poll."""
    assert _at(serial=True, wg1000=True, serial_open=True, gateway_open=True, last_serial_update=100.0) is ActiveSource.SERIAL


def test_both_falls_back_when_serial_has_no_decoded_sample() -> None:
    """Bytes on the wire are not a sample. With no decode, WG1000 stays active."""
    assert _at(serial=True, wg1000=True, serial_open=True, gateway_open=True, last_serial_update=None) is ActiveSource.WG1000


def test_both_keeps_serial_when_the_gateway_is_down() -> None:
    """A quiet serial port is still the only path when the gateway session is down."""
    assert _at(serial=True, wg1000=True, serial_open=True, gateway_open=False, last_serial_update=None) is ActiveSource.SERIAL


def test_exact_window_is_already_stale() -> None:
    """The sample is fresh only while it is strictly inside the window."""
    chosen = _at(
        serial=True,
        wg1000=True,
        serial_open=True,
        gateway_open=True,
        last_serial_update=100.0,
        now=110.0,
    )
    assert chosen is ActiveSource.WG1000


def test_nothing_configured_selects_nothing() -> None:
    """An empty draft cannot become a source."""
    assert _at(serial=False, wg1000=False, serial_open=False, gateway_open=False, last_serial_update=None) is ActiveSource.NONE
