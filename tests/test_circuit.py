"""Tests for homepage circuit register decoding helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from pyatmos_wg1000.protocol import (
    Hod16,
    ParamRecord,
    ParamType,
    decode_circuit_regime,
    encode_circuit_regime,
    encode_packed_setpoints,
    hod16_id,
    regime_preset_index,
)

from custom_components.atmos.circuit import (
    RegimeRequestError,
    circuit_register_ids,
    circuits_from_records,
    circuits_from_words,
    merge_register_words,
    regime_attributes,
    regime_word,
    resolve_circuit_name,
)


def test_resolve_circuit_name_own_text_and_tuv() -> None:
    """OwnText names circuits; empty TUV slot uses catalog then TUV."""

    class Catalog:
        def text(self, key: str) -> str | None:
            return {"T16_94": "CWU"}.get(key)

    class EmptyCatalog:
        def text(self, key: str) -> str | None:
            return None

    assert resolve_circuit_name(0, ("Dom", "Poddasze")) == "Dom"
    assert resolve_circuit_name(4, ("Dom",), Catalog()) == "CWU"
    assert resolve_circuit_name(4, ("Dom", "Poddasze", "", "", "Bojler"), Catalog()) == "Bojler"
    assert resolve_circuit_name(4, (), EmptyCatalog()) == "TUV"
    assert resolve_circuit_name(4, ("Dom",)) == "TUV"
    assert resolve_circuit_name(2, ()) == "Circuit 3"


def test_circuits_from_records_tuv_uses_catalog() -> None:
    """Active TUV circuit picks CWU from the language catalog."""

    class Catalog:
        def text(self, key: str) -> str | None:
            return {"T16_94": "CWU"}.get(key)

    records = [
        ParamRecord(register_id=hod16_id(Hod16.TUV_OBECNE), kind=ParamType.READ_ONLY, value=0x01),
    ]
    circ = circuits_from_records(records, catalog=Catalog())[0]
    assert circ.index == 4
    assert circ.name == "CWU"


def test_circuits_from_records_active_comfort() -> None:
    """Active circuit with packed setpoints and comfort regime."""
    general = 0x01 | (1 << 1)  # active, temp_type comfort
    records = [
        ParamRecord(register_id=hod16_id(Hod16.O1_OBECNE), kind=ParamType.READ_ONLY, value=general),
        ParamRecord(
            register_id=hod16_id(Hod16.O1_REZIM),
            kind=ParamType.READ_ONLY,
            value=encode_circuit_regime(regime_preset_index("comfort")),
        ),
        ParamRecord(register_id=hod16_id(Hod16.O1_TEPLOTA), kind=ParamType.READ_ONLY, value=0x80001F00),
        ParamRecord(
            register_id=hod16_id(Hod16.O1_TEPLOTY),
            kind=ParamType.READ_ONLY,
            value=encode_packed_setpoints(21.0, 18.0),
        ),
    ]
    circuits = circuits_from_records(records, own_text=("Dom",))
    assert len(circuits) == 1
    circ = circuits[0]
    assert circ.name == "Dom"
    assert circ.active is True
    assert circ.preset == "comfort"
    assert circ.comfort_c == 21.0
    assert circ.reduced_c == 18.0
    assert circ.active_setpoint_c == 21.0


def test_circuits_from_records_reduced_setpoint_and_humidity() -> None:
    """temp_type reduced selects the reduced half; humidity quantity is kept."""
    general = 0x01 | (2 << 1) | (1 << 4)  # active, reduced, humidity
    records = [
        ParamRecord(register_id=hod16_id(Hod16.O1_OBECNE), kind=ParamType.READ_ONLY, value=general),
        ParamRecord(register_id=hod16_id(Hod16.O1_VLHKOST), kind=ParamType.READ_ONLY, value=0x80001900),
        ParamRecord(
            register_id=hod16_id(Hod16.O1_TEPLOTY),
            kind=ParamType.READ_ONLY,
            value=encode_packed_setpoints(21.0, 18.0),
        ),
        ParamRecord(register_id=hod16_id(Hod16.O2_OBECNE), kind=ParamType.READ_ONLY, value=None),
    ]
    circ = circuits_from_records(records)[0]
    assert circ.temp_type == 2
    assert circ.active_setpoint_c == 18.0
    assert circ.humidity_supported is True
    assert circ.humidity is not None


def test_circuits_from_records_without_setpoints() -> None:
    """Active circuit with no TEPLOTY word leaves setpoints unset."""
    records = [
        ParamRecord(register_id=hod16_id(Hod16.O1_OBECNE), kind=ParamType.READ_ONLY, value=0x01),
    ]
    circ = circuits_from_records(records)[0]
    assert circ.comfort_c is None
    assert circ.reduced_c is None
    assert circ.active_setpoint_c is None


def test_records_by_id_skips_missing_values() -> None:
    """Helper drops records without a value."""
    from custom_components.atmos.circuit import records_by_id

    filled = ParamRecord(register_id=1, kind=ParamType.READ_ONLY, value=9)
    empty = ParamRecord(register_id=2, kind=ParamType.READ_ONLY, value=None)
    assert records_by_id([filled, empty]) == {1: 9}


def test_circuits_from_records_holiday_and_summer_presets() -> None:
    """Timed and summer regime indices map to preset names."""
    records = [
        ParamRecord(register_id=hod16_id(Hod16.O1_OBECNE), kind=ParamType.READ_ONLY, value=0x01),
        ParamRecord(
            register_id=hod16_id(Hod16.O1_REZIM),
            kind=ParamType.READ_ONLY,
            value=encode_circuit_regime(regime_preset_index("holiday")),
        ),
    ]
    assert circuits_from_records(records)[0].preset == "holiday"
    summer_records = [
        ParamRecord(register_id=hod16_id(Hod16.O1_OBECNE), kind=ParamType.READ_ONLY, value=0x01),
        ParamRecord(
            register_id=hod16_id(Hod16.O1_REZIM),
            kind=ParamType.READ_ONLY,
            value=encode_circuit_regime(regime_preset_index("summer")),
        ),
    ]
    assert circuits_from_records(summer_records)[0].preset == "summer"


def test_simple_presets_match_regime_menu_order() -> None:
    """Homepage climate exposes every Regime_menu permanent/timed mode."""
    from custom_components.atmos.circuit import SIMPLE_PRESETS

    assert SIMPLE_PRESETS == (
        "holiday",
        "absence",
        "visit",
        "auto",
        "summer",
        "comfort",
        "reduced",
        "standby",
    )
    for name in SIMPLE_PRESETS:
        assert regime_preset_index(name) >= 0


def test_circuit_register_ids_count() -> None:
    """Five circuits times five register families."""
    assert len(circuit_register_ids()) == 25


def test_merge_register_words_and_circuits_from_words() -> None:
    """Partial polls accumulate into a full circuit snapshot."""
    words: dict[int, int] = {}
    general = 0x01
    first = [
        ParamRecord(register_id=hod16_id(Hod16.O1_OBECNE), kind=ParamType.READ_ONLY, value=general),
        ParamRecord(
            register_id=hod16_id(Hod16.O1_REZIM),
            kind=ParamType.READ_ONLY,
            value=encode_circuit_regime(regime_preset_index("auto")),
        ),
        ParamRecord(register_id=hod16_id(Hod16.O2_OBECNE), kind=ParamType.READ_ONLY, value=None),
    ]
    assert merge_register_words(words, first) is True
    assert merge_register_words(words, first) is False
    assert hod16_id(Hod16.O2_OBECNE) not in words

    second = [
        ParamRecord(register_id=hod16_id(Hod16.O1_TEPLOTA), kind=ParamType.READ_ONLY, value=0x80001F00),
    ]
    assert merge_register_words(words, second) is True
    states = circuits_from_words(words)
    assert len(states) == 1
    assert states[0].preset == "auto"
    assert states[0].current_c is not None


_PRAGUE = ZoneInfo("Europe/Prague")
_NOW = datetime(2026, 10, 14, 18, 30, 15, tzinfo=_PRAGUE)


def test_regime_word_visit_until_tonight() -> None:
    """Visit until 22:00 packs a BCD end time and keeps no week program."""
    word = regime_word("visit", now=_NOW, until=_NOW.replace(hour=22, minute=0, second=40))
    assert word == 0x88002
    regime = decode_circuit_regime(word)
    assert regime.preset == "visit"
    assert regime.end_time == time(22, 0)
    assert regime_attributes(regime) == {"regime_end_time": "22:00"}


def test_regime_word_converts_until_to_local_time() -> None:
    """An end given in UTC is stored as local wall-clock time."""
    word = regime_word("absence", now=_NOW, until=datetime(2026, 10, 14, 19, 45, tzinfo=UTC))
    assert decode_circuit_regime(word).end_time == time(21, 45)


def test_regime_word_rejects_bad_visit_ends() -> None:
    """Absence/visit need an end later today; the controller has no date for them."""
    cases = [
        ({}, "until_required"),
        ({"until": _NOW.replace(hour=18, minute=30, second=59)}, "until_in_past"),
        ({"until": _NOW.replace(hour=9)}, "until_in_past"),
        ({"until": _NOW + timedelta(days=1)}, "until_not_today"),
        ({"until": _NOW.replace(hour=22), "week_program": "b"}, "week_program_not_supported"),
    ]
    for kwargs, key in cases:
        with pytest.raises(RegimeRequestError) as err:
            regime_word("visit", now=_NOW, **kwargs)  # type: ignore[arg-type]
        assert err.value.key == key


def test_regime_word_holiday_until_date() -> None:
    """Holiday keeps the date of ``until``, today included."""
    word = regime_word("holiday", now=_NOW, until=datetime(2026, 10, 20, tzinfo=_PRAGUE))
    regime = decode_circuit_regime(word)
    assert regime.end_date == date(2026, 10, 20)
    assert regime_attributes(regime) == {"regime_end_date": "2026-10-20"}
    assert decode_circuit_regime(regime_word("holiday", now=_NOW, until=_NOW.replace(hour=0))).end_date == date(2026, 10, 14)
    with pytest.raises(RegimeRequestError, match="until_in_past"):
        regime_word("holiday", now=_NOW, until=_NOW - timedelta(days=1))


def test_regime_word_auto_keeps_current_week_program() -> None:
    """Auto keeps the running week program instead of falling back to A."""
    running_b = decode_circuit_regime(encode_circuit_regime(regime_preset_index("auto"), week_prog=1))
    assert decode_circuit_regime(regime_word("auto", now=_NOW, current=running_b)).week_prog == 1
    assert decode_circuit_regime(regime_word("summer", now=_NOW, current=running_b)).week_prog == 1
    assert decode_circuit_regime(regime_word("auto", now=_NOW, current=running_b, week_program="c")).week_prog == 2
    assert regime_attributes(running_b) == {"week_program": "b"}

    visiting = decode_circuit_regime(regime_word("visit", now=_NOW, until=_NOW.replace(hour=22)))
    assert decode_circuit_regime(regime_word("auto", now=_NOW, current=visiting)).week_prog == 0
    assert decode_circuit_regime(regime_word("auto", now=_NOW)).week_prog == 0


def test_regime_word_permanent_presets() -> None:
    """Comfort and friends take neither an end nor a week program."""
    assert regime_word("comfort", now=_NOW) == encode_circuit_regime(regime_preset_index("comfort"))
    assert regime_attributes(decode_circuit_regime(regime_word("standby", now=_NOW))) == {}
    assert regime_attributes(None) == {}
    with pytest.raises(RegimeRequestError, match="until_not_supported"):
        regime_word("comfort", now=_NOW, until=_NOW.replace(hour=22))
    with pytest.raises(RegimeRequestError, match="week_program_not_supported"):
        regime_word("comfort", now=_NOW, week_program="a")
    with pytest.raises(RegimeRequestError, match="week_program_not_supported"):
        regime_word("auto", now=_NOW, week_program="d")
    with pytest.raises(RegimeRequestError, match="unknown_preset"):
        regime_word("party", now=_NOW)


def test_circuits_from_records_keep_regime_end() -> None:
    """The circuit snapshot carries the decoded regime word."""
    records = [
        ParamRecord(register_id=hod16_id(Hod16.O1_OBECNE), kind=ParamType.READ_ONLY, value=0x01),
        ParamRecord(register_id=hod16_id(Hod16.O1_REZIM), kind=ParamType.READ_ONLY, value=0x88002),
    ]
    circ = circuits_from_records(records)[0]
    assert circ.preset == "visit"
    assert circ.regime is not None
    assert circ.regime.end_time == time(22, 0)
