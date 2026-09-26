"""Tests for Info dump resolution helpers."""

from __future__ import annotations

from pyatmos_wg1000.protocol import InfoDump, InfoItem

from custom_components.atmos.info import gateway_language_for_hass, resolve_info_dump


class _Catalog:
    def text(self, key: str) -> str | None:
        return {
            "T16_1011": "Temperatury",
            "T16_1014": "AF - temp. zewnętrz.",
            "T16_1575": "AF",
        }.get(key)


def test_gateway_language_maps_hass_locale() -> None:
    """Polish Home Assistant language selects the POL column when present."""
    assert gateway_language_for_hass("pl", ("ENG", "POL", "CES")) == "POL"
    assert gateway_language_for_hass("en-GB", ("ENG", "POL")) == "ENG"
    assert gateway_language_for_hass("xx", ("ENG", "POL")) is None


def test_resolve_info_dump_builds_groups() -> None:
    """Title rows become group names; value rows keep expanded strings."""
    dump = InfoDump(
        ac16=0,
        items=(
            InfoItem(typ=0, vzhled=0, skupina=1, text_a=1011, text_b=1614, caption=1614, value=b"\x00"),
            InfoItem(
                typ=2,
                vzhled=0,
                skupina=1,
                text_a=1575,
                text_b=1614,
                caption=1014,
                value=b"25,9 \xc2\xb0C\x00",
            ),
            InfoItem(typ=0, vzhled=0, skupina=12, text_a=0x8000, text_b=1614, caption=1614, value=b"\x00"),
        ),
    )
    groups = resolve_info_dump(dump, _Catalog(), ("Dom", "Poddasze"))
    assert len(groups) == 2
    assert groups[0].title == "Temperatury"
    assert groups[0].rows[0].caption == "AF - temp. zewnętrz."
    assert groups[0].rows[0].value == "25,9 °C"
    assert groups[1].title == "Dom"
    assert groups[1].rows == ()


def test_resolve_info_dump_empty_own_text_tuv_title() -> None:
    """Empty OwnText[4] becomes TUV instead of Group 11."""
    dump = InfoDump(
        ac16=0,
        items=(InfoItem(typ=0, vzhled=0, skupina=11, text_a=0x8004, text_b=1614, caption=1614, value=b"\x00"),),
    )
    groups = resolve_info_dump(dump, _Catalog(), ("Dom", "Poddasze"))
    assert groups[0].title == "TUV"


def test_resolve_info_dump_empty_own_text_circuit_title() -> None:
    """Empty OwnText slots other than TUV fall back to Circuit N."""
    dump = InfoDump(
        ac16=0,
        items=(InfoItem(typ=0, vzhled=0, skupina=14, text_a=0x8002, text_b=1614, caption=1614, value=b"\x00"),),
    )
    groups = resolve_info_dump(dump, _Catalog(), ("Dom", "Poddasze"))
    assert groups[0].title == "Circuit 3"


def test_resolve_info_dump_unknown_title_falls_back_to_group() -> None:
    """Non-OwnText empty titles keep the Group N fallback."""
    dump = InfoDump(
        ac16=0,
        items=(InfoItem(typ=0, vzhled=0, skupina=99, text_a=1614, text_b=1614, caption=1614, value=b"\x00"),),
    )
    groups = resolve_info_dump(dump, _Catalog(), ())
    assert groups[0].title == "Group 99"
