"""Map Info value parts to Home Assistant entity metadata (no HA imports)."""

from __future__ import annotations

from dataclasses import dataclass

from pyatmos_wg1000.protocol import InfoValuePart, parse_info_row

from .info import InfoRow

PERCENT_UNIT = "%"


@dataclass(frozen=True)
class MappedInfoPart:
    """One Info value part ready for entity creation."""

    skupina: int
    caption_id: int
    part_index: int
    part: InfoValuePart
    humidity_hint: bool
    multi: bool

    @property
    def unique_suffix(self) -> str:
        """Return the unique_id suffix after ``{entry_id}_``."""
        base = f"g{self.skupina}_c{self.caption_id}"
        if self.multi:
            return f"{base}_p{self.part_index}"
        return base


def map_info_row(row: InfoRow) -> tuple[MappedInfoPart, ...]:
    """Parse one Info row into named, typed parts.

    Args:
        row: Resolved Info value row.

    Returns:
        One or two mapped parts. Parenthetical second halves are marked as
        humidity when the unit is ``%``.
    """
    parts = parse_info_row(
        value=row.value,
        caption=row.caption,
        text_a=row.text_a,
        text_b=row.text_b,
    )
    multi = len(parts) > 1
    paren_humidity = multi and "(" in row.value and ")" in row.value
    mapped: list[MappedInfoPart] = []
    for index, part in enumerate(parts):
        is_percent = part.unit_token == PERCENT_UNIT
        humidity_hint = paren_humidity and index == 1 and is_percent
        mapped.append(
            MappedInfoPart(
                skupina=row.skupina,
                caption_id=row.caption_id,
                part_index=index,
                part=part,
                humidity_hint=humidity_hint,
                multi=multi,
            )
        )
    return tuple(mapped)


def map_info_groups(rows: list[InfoRow] | tuple[InfoRow, ...]) -> tuple[MappedInfoPart, ...]:
    """Map every value row in ``rows``."""
    out: list[MappedInfoPart] = []
    for row in rows:
        out.extend(map_info_row(row))
    return tuple(out)


__all__ = ["MappedInfoPart", "map_info_groups", "map_info_row"]
