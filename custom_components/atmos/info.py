"""Resolve WG1000 Info dumps into named groups and rows for Home Assistant."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pyatmos_wg1000.protocol import (
    AC16_OWN_TEXT_OFFSET,
    InfoDump,
    InfoItem,
    TextLookup,
    expand_info_value,
    resolve_text_id,
)

# Home Assistant language codes → gateway table column codes.
_HA_TO_GATEWAY: dict[str, str] = {
    "cs": "CES",
    "da": "DAN",
    "de": "DEU",
    "en": "ENG",
    "et": "EST",
    "es": "SPA",
    "fr": "FRA",
    "hu": "HUN",
    "it": "ITA",
    "pl": "POL",
    "pt": "POR",
    "ro": "RON",
    "ru": "RUS",
    "sl": "SLV",
    "sv": "SWE",
}


@dataclass(frozen=True)
class InfoRow:
    """One non-title Info row with expanded labels and value."""

    skupina: int
    caption_id: int
    text_a_id: int
    text_b_id: int
    typ: int
    caption: str
    text_a: str
    text_b: str
    value: str
    is_alarm: bool


@dataclass(frozen=True)
class InfoGroup:
    """One Info page group (``skupina``) with its title and value rows."""

    skupina: int
    title: str
    rows: tuple[InfoRow, ...]


def gateway_language_for_hass(hass_language: str | None, available: Sequence[str]) -> str | None:
    """Map a Home Assistant language code onto a gateway column when present.

    Args:
        hass_language: ``hass.config.language`` (for example ``pl``).
        available: Gateway language codes from the catalog.

    Returns:
        A gateway code from ``available``, or ``None`` when nothing matches.
    """
    if not hass_language:
        return None
    primary = hass_language.split("-", 1)[0].lower()
    code = _HA_TO_GATEWAY.get(primary)
    if code is not None and code in available:
        return code
    upper = hass_language.upper()
    if upper in available:
        return upper
    return None


def resolve_info_dump(
    dump: InfoDump,
    catalog: TextLookup,
    own_text: Sequence[str],
) -> tuple[InfoGroup, ...]:
    """Turn a raw Info dump into ordered groups with expanded strings.

    Args:
        dump: Assembled Info rows from the gateway.
        catalog: Language tables for the selected column.
        own_text: Custom names from OwnText.

    Returns:
        Groups in first-seen ``skupina`` order. Title-only groups are kept.
        Alarm rows (``typ=3``) are included in their ``skupina`` for later
        diagnostic entities; they are not dropped.
    """
    order: list[int] = []
    titles: dict[int, str] = {}
    rows: dict[int, list[InfoRow]] = {}

    for item in dump.items:
        if item.is_title:
            if item.skupina not in titles:
                order.append(item.skupina)
                titles[item.skupina] = _title_for(item, catalog, own_text)
                rows.setdefault(item.skupina, [])
            continue
        if item.skupina not in rows:
            order.append(item.skupina)
            titles.setdefault(item.skupina, f"Group {item.skupina}")
            rows[item.skupina] = []
        rows[item.skupina].append(_row_for(item, catalog, own_text))

    return tuple(
        InfoGroup(skupina=skupina, title=titles.get(skupina, f"Group {skupina}"), rows=tuple(rows.get(skupina, ())))
        for skupina in order
    )


def _title_for(item: InfoItem, catalog: TextLookup, own_text: Sequence[str]) -> str:
    left = resolve_text_id(item.text_a, catalog, own_text)
    right = resolve_text_id(item.text_b, catalog, own_text)
    if left and right:
        return f"{left} {right}".strip()
    if left or right:
        return left or right
    # Title rows for circuits/TUV often use OwnText only; empty slots must not
    # become "Group N" in Home Assistant (CWU is OwnText[4] → TUV).
    if item.text_a >= AC16_OWN_TEXT_OFFSET:
        slot = item.text_a - AC16_OWN_TEXT_OFFSET
        if slot == 4:
            return "TUV"
        return f"Circuit {slot + 1}"
    return f"Group {item.skupina}"


def _row_for(item: InfoItem, catalog: TextLookup, own_text: Sequence[str]) -> InfoRow:
    return InfoRow(
        skupina=item.skupina,
        caption_id=item.caption,
        text_a_id=item.text_a,
        text_b_id=item.text_b,
        typ=item.typ,
        caption=resolve_text_id(item.caption, catalog, own_text),
        text_a=resolve_text_id(item.text_a, catalog, own_text),
        text_b=resolve_text_id(item.text_b, catalog, own_text),
        value=expand_info_value(item.value, catalog),
        is_alarm=item.is_alarm,
    )
