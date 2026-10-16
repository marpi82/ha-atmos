"""Homepage circuit snapshot from HOD16 PARAM registers (HA-free)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from pyatmos_wg1000.protocol import (
    CircuitRegime,
    Hod16,
    ParamRecord,
    TextLookup,
    decode_acd_quantity,
    decode_acd_temperature,
    decode_circuit_general,
    decode_circuit_regime,
    decode_packed_setpoints,
    encode_circuit_regime,
    encode_regime_end_date,
    encode_regime_end_time,
    hod16_id,
    regime_preset_index,
)

# O1..O4 then TUV — matches Pages.js homepage circuit order.
CIRCUIT_COUNT = 5
CIRCUIT_TUV = 4
# texty_brana id 94: CES=TUV, ENG=DHW, POL=CWU (and peers).
TUV_CATALOG_KEY = "T16_94"

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
TIMED_PRESETS = ("holiday", "absence", "visit")
WEEK_PROGRAM_PRESETS = ("auto", "summer")
WEEK_PROGRAMS = ("a", "b", "c")


class RegimeRequestError(ValueError):
    """Invalid regime request. ``key`` is the translation key."""

    def __init__(self, key: str) -> None:
        """Init with a translation key."""
        super().__init__(key)
        self.key = key


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
    regime: CircuitRegime | None = None

    @property
    def active_setpoint_c(self) -> float | None:
        """Return the setpoint that matches the current temp icon type."""
        if self.temp_type == _TEMP_TYPE_REDUCED:
            return self.reduced_c
        return self.comfort_c


def regime_word(
    preset: str,
    *,
    now: datetime,
    until: datetime | None = None,
    week_program: str | None = None,
    current: CircuitRegime | None = None,
) -> int:
    """Build the ``O*_REZIM`` word to write.

    Absence/visit only store a time of day, so ``until`` has to be later today.
    Auto/summer keep the current week program unless one is given.
    """
    if preset not in SIMPLE_PRESETS:
        raise RegimeRequestError("unknown_preset")
    if week_program is not None and (preset not in WEEK_PROGRAM_PRESETS or week_program not in WEEK_PROGRAMS):
        raise RegimeRequestError("week_program_not_supported")
    if preset not in TIMED_PRESETS:
        if until is not None:
            raise RegimeRequestError("until_not_supported")
        week_prog = 0
        if week_program is not None:
            week_prog = WEEK_PROGRAMS.index(week_program)
        elif preset in WEEK_PROGRAM_PRESETS and current is not None and current.preset in WEEK_PROGRAM_PRESETS:
            week_prog = current.week_prog
        return encode_circuit_regime(regime_preset_index(preset), week_prog=week_prog)

    if until is None:
        raise RegimeRequestError("until_required")
    end = until.astimezone(now.tzinfo)
    if preset == "holiday":
        if end.date() < now.date():
            raise RegimeRequestError("until_in_past")
        date_time = encode_regime_end_date(end.date())
    else:
        end = end.replace(second=0, microsecond=0)
        if end <= now:
            raise RegimeRequestError("until_in_past")
        if end.date() != now.date():
            raise RegimeRequestError("until_not_today")
        date_time = encode_regime_end_time(end.time())
    return encode_circuit_regime(regime_preset_index(preset), date_time=date_time)


def regime_attributes(regime: CircuitRegime | None) -> dict[str, str]:
    """Climate attributes for the regime end and week program."""
    if regime is None:
        return {}
    attributes: dict[str, str] = {}
    if regime.end_time is not None:
        attributes["regime_end_time"] = regime.end_time.strftime("%H:%M")
    if regime.end_date is not None:
        attributes["regime_end_date"] = regime.end_date.isoformat()
    if regime.preset in WEEK_PROGRAM_PRESETS and regime.week_prog < len(WEEK_PROGRAMS):
        attributes["week_program"] = WEEK_PROGRAMS[regime.week_prog]
    return attributes


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


def resolve_circuit_name(
    index: int,
    own_text: Sequence[str],
    catalog: TextLookup | None = None,
) -> str:
    """Name a circuit from OwnText, then the catalog DHW label, then TUV.

    Args:
        index: Circuit index 0..4.
        own_text: OwnText slots from the gateway.
        catalog: Language tables; used for empty OwnText[4] (``T16_94``).
    """
    if 0 <= index < len(own_text) and own_text[index]:
        return own_text[index]
    if index == CIRCUIT_TUV:
        if catalog is not None:
            label = catalog.text(TUV_CATALOG_KEY)
            if label:
                return label
        return "TUV"
    return f"Circuit {index + 1}"


def circuits_from_records(
    records: Sequence[ParamRecord],
    *,
    own_text: Sequence[str] = (),
    catalog: TextLookup | None = None,
    device_ac16: int = 1,
) -> tuple[CircuitState, ...]:
    """Build circuit snapshots from a PARAM read response.

    Args:
        records: Decoded parameter records.
        own_text: OwnText slots for circuit names.
        catalog: Language tables for empty TUV/CWU OwnText.
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
        rezim_word = by_id.get(hod16_id(_REZIM[index], device=device))
        regime = decode_circuit_regime(rezim_word) if rezim_word is not None else None
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
                name=resolve_circuit_name(index, own_text, catalog),
                active=general.active,
                humidity_supported=general.humidity,
                temp_type=general.temp_type,
                preset=regime.preset if regime is not None else None,
                current_c=decode_acd_temperature(temp_word) if temp_word is not None else None,
                humidity=(decode_acd_quantity(humid_word) if general.humidity and humid_word is not None else None),
                comfort_c=comfort,
                reduced_c=reduced,
                regime=regime,
            )
        )
    return tuple(states)


def records_by_id(records: Sequence[ParamRecord]) -> Mapping[int, int]:
    """Map register id → raw value for present readings."""
    return {record.register_id: record.value for record in records if record.value is not None}


def merge_register_words(
    words: dict[int, int],
    records: Sequence[ParamRecord],
) -> bool:
    """Update ``words`` from ``records``. Return whether anything changed.

    Args:
        words: Mutable id → raw value cache across partial polls.
        records: Fresh PARAM read response.
    """
    changed = False
    for record in records:
        if record.value is None:
            continue
        if words.get(record.register_id) != record.value:
            words[record.register_id] = record.value
            changed = True
    return changed


def circuits_from_words(
    words: Mapping[int, int],
    *,
    own_text: Sequence[str] = (),
    catalog: TextLookup | None = None,
    device_ac16: int = 1,
) -> tuple[CircuitState, ...]:
    """Build circuit snapshots from a register-word cache.

    Args:
        words: id → raw value (may be a partial poll merged over time).
        own_text: OwnText slots for circuit names.
        catalog: Language tables for empty TUV/CWU OwnText.
        device_ac16: Device nibble used when packing ids.
    """
    from pyatmos_wg1000.protocol import ParamType

    records = tuple(
        ParamRecord(register_id=register_id, kind=ParamType.READ_ONLY, value=value) for register_id, value in words.items()
    )
    return circuits_from_records(
        records,
        own_text=own_text,
        catalog=catalog,
        device_ac16=device_ac16,
    )


__all__ = [
    "CIRCUIT_COUNT",
    "CIRCUIT_TUV",
    "SIMPLE_PRESETS",
    "TIMED_PRESETS",
    "TUV_CATALOG_KEY",
    "WEEK_PROGRAMS",
    "WEEK_PROGRAM_PRESETS",
    "CircuitState",
    "RegimeRequestError",
    "circuit_register_ids",
    "circuits_from_records",
    "circuits_from_words",
    "merge_register_words",
    "records_by_id",
    "regime_attributes",
    "regime_word",
    "resolve_circuit_name",
]
