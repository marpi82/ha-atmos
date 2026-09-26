"""Map Info value parts to Home Assistant entity metadata (no HA imports)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pyatmos_wg1000.protocol import InfoValueKind, InfoValuePart, parse_info_row, part_names

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

    @property
    def unique_suffix(self) -> str:
        """Return the unique_id suffix after ``{entry_id}_`` (always ``_p{i}``)."""
        return info_part_uid_suffix(self.skupina, self.caption_id, self.part_index)


def info_part_uid_suffix(skupina: int, caption_id: int, part_index: int) -> str:
    """Stable Info part unique_id suffix (``g{skupina}_c{caption}_p{i}``)."""
    return f"g{skupina}_c{caption_id}_p{part_index}"


def info_part_uid_bare(skupina: int, caption_id: int) -> str:
    """Legacy single-part suffix without ``_p`` (pre-a6)."""
    return f"g{skupina}_c{caption_id}"


def part_indices_from_unique_ids(
    entry_id: str,
    skupina: int,
    caption_id: int,
    unique_ids: Iterable[str],
) -> set[int]:
    """Parse Info part indices from entity unique_ids for one row.

    Args:
        entry_id: Config entry id prefix.
        skupina: Info group id.
        caption_id: Caption text id.
        unique_ids: Candidate ``unique_id`` strings (any domain).

    Returns:
        Zero-based part indices found (legacy bare uid counts as ``0``).
    """
    bare = f"{entry_id}_{info_part_uid_bare(skupina, caption_id)}"
    prefix = f"{entry_id}_g{skupina}_c{caption_id}_p"
    found: set[int] = set()
    for uid in unique_ids:
        if uid == bare:
            found.add(0)
            continue
        if uid.startswith(prefix):
            tail = uid[len(prefix) :]
            if tail.isdigit():
                found.add(int(tail))
    return found


def desired_part_slots(live_count: int, registered_indices: Iterable[int]) -> int:
    """How many part slots to keep for a row (live dump plus registry memory).

    Args:
        live_count: Parts in the current value string.
        registered_indices: Part indices already present in the entity registry.

    Returns:
        ``max(live_count, max(registered)+1)``, or ``live_count`` when none registered.
    """
    registered = list(registered_indices)
    if not registered:
        return live_count
    return max(live_count, max(registered) + 1)


def stub_mapped_part(row: InfoRow, part_index: int, *, total_parts: int) -> MappedInfoPart:
    """Build an unavailable placeholder for a part slot missing from the live value.

    Args:
        row: Current Info row (caption used for the entity name).
        part_index: Zero-based slot.
        total_parts: Total slots kept for this row (for ``Caption (2)`` style names).
    """
    names = part_names(
        caption=row.caption,
        text_a=row.text_a,
        text_b=row.text_b,
        n_parts=max(total_parts, part_index + 1),
    )
    if part_index < len(names):
        name = names[part_index]
    else:
        base = row.caption or "Info"
        name = base if part_index == 0 else f"{base} ({part_index + 1})"
    part = InfoValuePart(kind=InfoValueKind.MISSING, raw="", name=name)
    return MappedInfoPart(
        skupina=row.skupina,
        caption_id=row.caption_id,
        part_index=part_index,
        part=part,
        humidity_hint=False,
    )


def map_info_row(row: InfoRow) -> tuple[MappedInfoPart, ...]:
    """Parse one Info row into named, typed parts.

    Args:
        row: Resolved Info value row.

    Returns:
        One or two mapped parts. Parenthetical second halves are marked as
        humidity when the unit is ``%``. Unique ids always use ``_p{i}``.
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
            )
        )
    return tuple(mapped)


def map_info_groups(rows: list[InfoRow] | tuple[InfoRow, ...]) -> tuple[MappedInfoPart, ...]:
    """Map every value row in ``rows``."""
    out: list[MappedInfoPart] = []
    for row in rows:
        out.extend(map_info_row(row))
    return tuple(out)


__all__ = [
    "MappedInfoPart",
    "desired_part_slots",
    "info_part_uid_bare",
    "info_part_uid_suffix",
    "map_info_groups",
    "map_info_row",
    "part_indices_from_unique_ids",
    "stub_mapped_part",
]
