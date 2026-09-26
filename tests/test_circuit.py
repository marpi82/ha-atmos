"""Tests for homepage circuit register decoding helpers."""

from __future__ import annotations

from pyatmos_wg1000.protocol import (
    Hod16,
    ParamRecord,
    ParamType,
    encode_circuit_regime,
    encode_packed_setpoints,
    hod16_id,
    regime_preset_index,
)

from custom_components.atmos.circuit import (
    circuit_register_ids,
    circuits_from_records,
    resolve_circuit_name,
)


def test_resolve_circuit_name_own_text_and_tuv() -> None:
    """OwnText names circuits; TUV is a fixed label."""
    assert resolve_circuit_name(0, ("Dom", "Poddasze")) == "Dom"
    assert resolve_circuit_name(4, ("Dom",)) == "TUV"
    assert resolve_circuit_name(2, ()) == "Circuit 3"


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
