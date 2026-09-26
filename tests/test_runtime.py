"""Runtime keeps Info groups and flips when serial goes stale."""

from __future__ import annotations

import asyncio
import sys

from custom_components.atmos.info import InfoGroup, InfoRow
from custom_components.atmos.runtime import AtmosRuntime
from custom_components.atmos.source import ActiveSource, SourceConfig


def test_import_does_not_load_home_assistant() -> None:
    """Unit tests cover the policy without the Home Assistant package."""
    assert "homeassistant" not in sys.modules
    assert "custom_components.atmos.wiring" not in sys.modules


def test_info_rows_are_indexed_by_group_and_caption() -> None:
    """WG1000 Info sensors look up the last dump by stable ids."""
    runtime = AtmosRuntime(SourceConfig(serial=False, wg1000=True, fallback_after=10))
    runtime.set_gateway_open(True)
    row = InfoRow(
        skupina=1,
        caption_id=1014,
        text_a_id=1575,
        text_b_id=1614,
        typ=2,
        caption="AF",
        text_a="AF",
        text_b="",
        value="25,9 °C",
        is_alarm=False,
    )
    runtime.note_info_groups([InfoGroup(skupina=1, title="Temperatury", rows=(row,))])
    assert runtime.group_title(1) == "Temperatury"
    assert runtime.info_row(1, 1014) == row
    assert runtime.active_source() is ActiveSource.WG1000


def test_serial_only_never_reads_info_as_active_when_closed() -> None:
    """A serial-only entry stays unavailable until the port opens."""
    runtime = AtmosRuntime(SourceConfig(serial=True, wg1000=False, fallback_after=10))
    assert runtime.active_source() is ActiveSource.NONE
    runtime.set_serial_open(True)
    runtime.note_serial_update(1, 9, now=100.0)
    assert runtime.value(1, now=100.0) == 9


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
    assert watch.done()
    assert ActiveSource.WG1000 in seen


async def test_circuit_snapshot_and_write_registers() -> None:
    """Homepage circuits are stored and writes go through the bound client."""
    from custom_components.atmos.circuit import CircuitState

    runtime = AtmosRuntime(SourceConfig(serial=False, wg1000=True, fallback_after=10))
    state = CircuitState(
        index=0,
        name="Dom",
        active=True,
        humidity_supported=False,
        temp_type=1,
        preset="comfort",
        current_c=21.0,
        humidity=None,
        comfort_c=21.0,
        reduced_c=18.0,
    )
    runtime.note_circuits([state])
    assert runtime.circuits == (state,)
    assert runtime.circuit(0) is state
    assert runtime.circuit(9) is None

    written: list[tuple[int, int]] = []

    async def _write(pairs: object) -> None:
        written.extend(pairs)  # type: ignore[arg-type]

    runtime.bind_write_registers(_write)
    await runtime.write_registers([(1, 2)])
    assert written == [(1, 2)]
    runtime.bind_write_registers(None)
    try:
        await runtime.write_registers([(3, 4)])
    except RuntimeError as exc:
        assert "write path" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
