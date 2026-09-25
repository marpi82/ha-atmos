"""Runtime keeps the two value maps apart and flips when serial goes stale."""

from __future__ import annotations

import asyncio
import sys

from custom_components.atmos.runtime import AtmosRuntime
from custom_components.atmos.source import ActiveSource, SourceConfig


def test_import_does_not_load_home_assistant() -> None:
    """Unit tests cover the policy without the Home Assistant package."""
    assert "homeassistant" not in sys.modules
    assert "custom_components.atmos.wiring" not in sys.modules


def test_values_follow_the_active_map() -> None:
    """A fresh serial word wins, then the polled word wins after the window."""
    runtime = AtmosRuntime(SourceConfig(serial=True, wg1000=True, fallback_after=10))
    runtime.set_serial_open(True)
    runtime.set_gateway_open(True)
    runtime.note_serial_bytes(40)
    runtime.note_gateway_update(1, 5)
    runtime.note_serial_update(1, 9, now=100.0)

    assert runtime.serial_bytes_seen == 40
    assert runtime.value(1, now=100.0) == 9
    assert runtime.active_source(now=109.9) is ActiveSource.SERIAL
    assert runtime.value(1, now=110.0) == 5


def test_serial_only_never_reads_the_gateway_map() -> None:
    """Gateway samples are stored only as a fallback the user asked for."""
    runtime = AtmosRuntime(SourceConfig(serial=True, wg1000=False, fallback_after=10))
    runtime.set_serial_open(True)
    runtime.note_gateway_update(1, 5)
    runtime.note_serial_update(1, 9, now=100.0)
    assert runtime.value(1, now=1000.0) == 9


def test_unsubscribe_stops_callbacks() -> None:
    """Entity removal drops the listener."""
    runtime = AtmosRuntime(SourceConfig(serial=True, wg1000=False, fallback_after=10))
    seen: list[int] = []
    remove = runtime.add_listener(lambda: seen.append(1))
    runtime.set_serial_open(True)
    remove()
    runtime.set_serial_open(False)
    assert seen == [1]


async def test_watch_notifies_once_when_the_window_expires() -> None:
    """Entities refresh after the last decoded serial sample ages out."""
    runtime = AtmosRuntime(SourceConfig(serial=True, wg1000=True, fallback_after=0.05))
    runtime.set_serial_open(True)
    runtime.set_gateway_open(True)
    seen: list[ActiveSource] = []
    runtime.add_listener(lambda: seen.append(runtime.active_source()))
    runtime.note_serial_update(1, 3, now=asyncio.get_running_loop().time())
    stop = asyncio.Event()
    watch = asyncio.create_task(runtime.watch_fallback(stop))
    await asyncio.sleep(0.15)
    stop.set()
    await watch
    assert ActiveSource.WG1000 in seen
