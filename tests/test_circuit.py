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


def test_circuit_register_ids_count() -> None:
    """Five circuits times five register families."""
    assert len(circuit_register_ids()) == 25
