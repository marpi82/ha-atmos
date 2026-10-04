"""Pages.js PrmID bucket parsing for circuit poll cadence."""

from __future__ import annotations

from pathlib import Path

import pytest
from pyatmos_wg1000.protocol import Hod16, hod16_id

from custom_components.atmos.ui_schedule import (
    circuit_schedule_from_pages,
    parse_pages_js_hod16_intervals,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "pages_circuit_schedule.js"


def test_parse_pages_js_assigns_stock_buckets() -> None:
    """Homepage temps are 30 s; regime/general/setpoints are 5 s."""
    source = _FIXTURE.read_text(encoding="utf-8")
    intervals = parse_pages_js_hod16_intervals(source)

    assert intervals[Hod16.O1_TEPLOTA] == 30.0
    assert intervals[Hod16.TUV_VLHKOST] == 30.0
    assert intervals[Hod16.O1_OBECNE] == 5.0
    assert intervals[Hod16.TUV_REZIM] == 5.0
    assert intervals[Hod16.O1_TEPLOTY] == 5.0
    assert intervals[Hod16.TUV_TEPLOTY] == 5.0
    # Not used by climate entities; still parsed from the page.
    assert intervals[Hod16.O1_TRVALY_REZIM] == 30.0


def test_circuit_schedule_from_pages_filters_and_packs_ids() -> None:
    """Only climate-related locals become wire ids; TRVALY is dropped."""
    source = _FIXTURE.read_text(encoding="utf-8")
    schedule = circuit_schedule_from_pages(source)

    assert set(schedule) == {5.0, 30.0}
    assert hod16_id(Hod16.O1_OBECNE) in schedule[5.0]
    assert hod16_id(Hod16.O1_TEPLOTY) in schedule[5.0]
    assert hod16_id(Hod16.O1_TEPLOTA) in schedule[30.0]
    assert hod16_id(Hod16.O1_TRVALY_REZIM) not in schedule[30.0]


def test_circuit_schedule_fallback_without_pages() -> None:
    """Missing Pages.js still covers every homepage circuit local."""
    schedule = circuit_schedule_from_pages(None)
    assert set(schedule) == {5.0, 30.0}
    packed = {register_id for ids in schedule.values() for register_id in ids}
    for local in (
        Hod16.O1_OBECNE,
        Hod16.O1_REZIM,
        Hod16.O1_TEPLOTA,
        Hod16.O1_VLHKOST,
        Hod16.O1_TEPLOTY,
        Hod16.TUV_TEPLOTY,
    ):
        assert hod16_id(local) in packed


def test_parse_pages_js_keeps_shortest_interval_and_skips_unknown() -> None:
    """Duplicate bindings keep the faster bucket; unknown HOD16 names are ignored."""
    source = """
    <span ${Atribut.PrmID5s}="[${HOD16.O1_TEPLOTA}]"></span>
    <span ${Atribut.PrmID30s}="[${HOD16.O1_TEPLOTA}]"></span>
    <span ${Atribut.PrmID1s}="[${HOD16.NOT_A_REAL_REGISTER}]"></span>
    """
    intervals = parse_pages_js_hod16_intervals(source)
    assert intervals[Hod16.O1_TEPLOTA] == 5.0
    assert Hod16.O1_TEPLOTY not in intervals


def test_circuit_schedule_from_empty_pages_uses_fallback(caplog: pytest.LogCaptureFixture) -> None:
    """Pages.js without circuit PrmID bindings falls back and warns."""
    import logging

    with caplog.at_level(logging.WARNING):
        schedule = circuit_schedule_from_pages("const nothing = 1;")
    assert set(schedule) == {5.0, 30.0}
    assert any("no circuit PrmID bindings" in message for message in caplog.messages)


def test_circuit_schedule_fills_missing_locals_from_fallback() -> None:
    """Parsed Pages.js keeps page intervals and fills gaps from the fallback."""
    source = '<span ${Atribut.PrmID1s}="[${HOD16.O1_TEPLOTA}]"></span>'
    schedule = circuit_schedule_from_pages(source)
    assert hod16_id(Hod16.O1_TEPLOTA) in schedule[1.0]
    assert hod16_id(Hod16.O1_OBECNE) in schedule[5.0]
    assert hod16_id(Hod16.O1_VLHKOST) in schedule[30.0]
