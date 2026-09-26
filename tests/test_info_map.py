"""Tests for Info display → entity part mapping."""

from __future__ import annotations

from pyatmos_wg1000.protocol import InfoValueKind

from custom_components.atmos.info import InfoRow
from custom_components.atmos.info_map import map_info_row

_CELSIUS = "\u00b0C"
_PERCENT = "%"


def _row(**kwargs: object) -> InfoRow:
    base = {
        "skupina": 12,
        "caption_id": 1283,
        "text_a_id": 1614,
        "text_b_id": 1614,
        "typ": 1,
        "caption": "Room temperature / requirement",
        "text_a": "",
        "text_b": "",
        "value": f"19,7 / 21,3 {_CELSIUS}",
        "is_alarm": False,
    }
    base.update(kwargs)
    return InfoRow(**base)  # type: ignore[arg-type]


def test_map_slash_pair_inherits_unit_and_names() -> None:
    """Dual slash values become two numbered parts with caption names."""
    parts = map_info_row(_row())
    assert len(parts) == 2
    assert parts[0].part.kind is InfoValueKind.NUMBER
    assert parts[0].part.number == 19.7
    assert parts[0].part.unit_token == _CELSIUS
    assert parts[0].part.name == "Room temperature"
    assert parts[1].part.number == 21.3
    assert parts[0].multi is True
    assert parts[0].unique_suffix.endswith("_p0")


def test_map_missing_temperature() -> None:
    """Dashed missing reading keeps a temperature unit."""
    parts = map_info_row(_row(value=f"--- {_CELSIUS}", caption="Buffer", caption_id=1189))
    assert len(parts) == 1
    assert parts[0].part.kind is InfoValueKind.MISSING
    assert parts[0].part.unit_token == _CELSIUS
    assert parts[0].multi is False
    assert parts[0].unique_suffix == "g12_c1189"


def test_map_info_groups_flattens_rows() -> None:
    """map_info_groups concatenates parts from every row."""
    from custom_components.atmos.info_map import map_info_groups

    parts = map_info_groups([_row(), _row(value="ON", caption="Pump", caption_id=2)])
    assert len(parts) >= 3
    assert parts[-1].part.kind is InfoValueKind.BINARY


def test_map_binary_and_valve() -> None:
    """ON/OFF and STOP classify as binary/valve kinds."""
    on_parts = map_info_row(_row(value="ON", caption="Pump", caption_id=1))
    assert on_parts[0].part.kind is InfoValueKind.BINARY
    assert on_parts[0].part.binary_on is True
    valve = map_info_row(_row(value="0 % / STOP", caption="position / move", text_a="MK1A", text_b="MK1B"))
    assert valve[1].part.kind is InfoValueKind.VALVE
    assert valve[1].part.valve == "stop"


def test_paren_humidity_hint() -> None:
    """Parenthetical percent is flagged as humidity."""
    parts = map_info_row(_row(value=f"19,7 {_CELSIUS} (65,9 {_PERCENT})", caption="Dom"))
    assert parts[1].humidity_hint is True
    assert parts[1].part.unit_token == _PERCENT
