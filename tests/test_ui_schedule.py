"""Homepage circuit poll buckets derived from Pages.js (parser is in the library)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pyatmos_wg1000.protocol import Hod16, hod16_id

from custom_components.atmos.ui_schedule import circuit_schedule_from_pages

_FIXTURE = Path(__file__).parent / "fixtures" / "pages_circuit_schedule.js"


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
