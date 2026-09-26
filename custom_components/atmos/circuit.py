"""Homepage circuit snapshot from HOD16 PARAM registers (HA-free)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pyatmos_wg1000.protocol import (
    Hod16,
    ParamRecord,
    decode_acd_quantity,
    decode_acd_temperature,
    decode_circuit_general,
    decode_circuit_regime,
    decode_packed_setpoints,
    hod16_id,
)

# O1..O4 then TUV — matches Pages.js homepage circuit order.
CIRCUIT_COUNT = 5
CIRCUIT_TUV = 4

_OBECNE = (Hod16.O1_OBECNE, Hod16.O2_OBECNE, Hod16.O3_OBECNE, Hod16.O4_OBECNE, Hod16.TUV_OBECNE)
_REZIM = (Hod16.O1_REZIM, Hod16.O2_REZIM, Hod16.O3_REZIM, Hod16.O4_REZIM, Hod16.TUV_REZIM)
_TEPLOTA = (Hod16.O1_TEPLOTA, Hod16.O2_TEPLOTA, Hod16.O3_TEPLOTA, Hod16.O4_TEPLOTA, Hod16.TUV_TEPLOTA)
_VLHKOST = (Hod16.O1_VLHKOST, Hod16.O2_VLHKOST, Hod16.O3_VLHKOST, Hod16.O4_VLHKOST, Hod16.TUV_VLHKOST)
_TEPLOTY = (Hod16.O1_TEPLOTY, Hod16.O2_TEPLOTY, Hod16.O3_TEPLOTY, Hod16.O4_TEPLOTY, Hod16.TUV_TEPLOTY)

# tempType from OBECNE: 2 = reduced (útlum); else treat comfort as active target.
_TEMP_TYPE_REDUCED = 2

SIMPLE_PRESETS = (
    "holiday",
    "absence",
    "visit",
    "auto",
    "summer",
    "comfort",
    "reduced",
    "standby",
)


@dataclass(frozen=True)
class CircuitState:
    """One homepage circuit (O1..O4 or TUV)."""

    index: int
    name: str
    active: bool
    humidity_supported: bool
    temp_type: int
    preset: str | None
    current_c: float | None
    humidity: float | None
    comfort_c: float | None
    reduced_c: float | None

    @property
    def active_setpoint_c(self) -> float | None:
        """Return the setpoint that matches the current temp icon type."""
        if self.temp_type == _TEMP_TYPE_REDUCED:
            return self.reduced_c
        return self.comfort_c


def circuit_register_ids(*, device_ac16: int = 1) -> tuple[int, ...]:
    """Return wire ids for all homepage circuit registers.

    Args:
        device_ac16: Device nibble for ``hod16_id`` (``Device.AC16_1`` = 1).
    """
    from pyatmos_wg1000.protocol import Device

    device = Device(device_ac16)
    ids: list[int] = []
    for local in (*_OBECNE, *_REZIM, *_TEPLOTA, *_VLHKOST, *_TEPLOTY):
        ids.append(hod16_id(local, device=device))
    return tuple(ids)


def resolve_circuit_name(index: int, own_text: Sequence[str]) -> str:
    """Name a circuit from OwnText slots or a TUV fallback.

    Args:
        index: Circuit index 0..4.
        own_text: OwnText slots from the gateway.
    """
    if index == CIRCUIT_TUV:
        return "TUV"
    if 0 <= index < len(own_text) and own_text[index]:
        return own_text[index]
    return f"Circuit {index + 1}"


def circuits_from_records(
    records: Sequence[ParamRecord],
    *,
    own_text: Sequence[str] = (),
    device_ac16: int = 1,
) -> tuple[CircuitState, ...]:
    """Build circuit snapshots from a PARAM read response.

    Args:
        records: Decoded parameter records.
        own_text: OwnText slots for circuit names.
        device_ac16: Device nibble used when packing ids.
    """
    from pyatmos_wg1000.protocol import Device

    device = Device(device_ac16)
    by_id: dict[int, int] = {}
    for record in records:
        if record.value is not None:
            by_id[record.register_id] = record.value

    states: list[CircuitState] = []
    for index in range(CIRCUIT_COUNT):
        general_word = by_id.get(hod16_id(_OBECNE[index], device=device))
        if general_word is None:
            continue
        general = decode_circuit_general(general_word)
        regime_word = by_id.get(hod16_id(_REZIM[index], device=device))
        preset = decode_circuit_regime(regime_word).preset if regime_word is not None else None
        temp_word = by_id.get(hod16_id(_TEPLOTA[index], device=device))
        humid_word = by_id.get(hod16_id(_VLHKOST[index], device=device))
        set_word = by_id.get(hod16_id(_TEPLOTY[index], device=device))
        comfort: float | None = None
        reduced: float | None = None
        if set_word is not None:
            pair = decode_packed_setpoints(set_word)
            comfort, reduced = pair.comfort_c, pair.reduced_c
        states.append(
            CircuitState(
                index=index,
                name=resolve_circuit_name(index, own_text),
                active=general.active,
                humidity_supported=general.humidity,
                temp_type=general.temp_type,
                preset=preset,
                current_c=decode_acd_temperature(temp_word) if temp_word is not None else None,
                humidity=(decode_acd_quantity(humid_word) if general.humidity and humid_word is not None else None),
                comfort_c=comfort,
                reduced_c=reduced,
            )
        )
    return tuple(states)


def records_by_id(records: Sequence[ParamRecord]) -> Mapping[int, int]:
    """Map register id → raw value for present readings."""
    return {record.register_id: record.value for record in records if record.value is not None}


__all__ = [
    "CIRCUIT_COUNT",
    "CIRCUIT_TUV",
    "SIMPLE_PRESETS",
    "CircuitState",
    "circuit_register_ids",
    "circuits_from_records",
    "records_by_id",
    "resolve_circuit_name",
]
