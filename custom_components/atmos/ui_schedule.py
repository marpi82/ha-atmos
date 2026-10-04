"""Derive PARAM poll intervals from the stock WG1000 ``Pages.js`` bundle.

The panel timer uses ``PrmID1s`` / ``PrmID5s`` / ``PrmID10s`` / ``PrmID30s``
attributes. Info dumps are requested every 1 s on the Informace page (and
every 5 s elsewhere); this integration always uses the Informace cadence.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from pyatmos_wg1000.protocol import Hod16, hod16_id

LOGGER = logging.getLogger(__name__)

# Stock UI bucket names → seconds (see ``TPages.Timer`` in Pages.js).
_BUCKET_SECONDS: Mapping[str, float] = {
    "PrmID1s": 1.0,
    "PrmID5s": 5.0,
    "PrmID10s": 10.0,
    "PrmID30s": 30.0,
}

_ATTR_HOD16 = re.compile(r"""Atribut\.(PrmID(?:1s|5s|10s|30s))\}?=["']\[\$\{HOD16\.([A-Z0-9_]+)\}\]["']""")
_TEPLOTY_DYNAMIC = re.compile(r"""HOD16\[`\$\{circName\}_TEPLOTY`\][\s\S]{0,400}?Atribut\.PrmID5s\}?=["']\[\$\{circID\}\]["']""")

_TEPLOTY = (
    Hod16.O1_TEPLOTY,
    Hod16.O2_TEPLOTY,
    Hod16.O3_TEPLOTY,
    Hod16.O4_TEPLOTY,
    Hod16.TUV_TEPLOTY,
)

# Locals that feed homepage climate / number entities.
_CIRCUIT_LOCALS: frozenset[Hod16] = frozenset(
    (
        Hod16.O1_OBECNE,
        Hod16.O2_OBECNE,
        Hod16.O3_OBECNE,
        Hod16.O4_OBECNE,
        Hod16.TUV_OBECNE,
        Hod16.O1_REZIM,
        Hod16.O2_REZIM,
        Hod16.O3_REZIM,
        Hod16.O4_REZIM,
        Hod16.TUV_REZIM,
        Hod16.O1_TEPLOTA,
        Hod16.O2_TEPLOTA,
        Hod16.O3_TEPLOTA,
        Hod16.O4_TEPLOTA,
        Hod16.TUV_TEPLOTA,
        Hod16.O1_VLHKOST,
        Hod16.O2_VLHKOST,
        Hod16.O3_VLHKOST,
        Hod16.O4_VLHKOST,
        Hod16.TUV_VLHKOST,
        *_TEPLOTY,
    )
)

# Captured from Pages.js when download/parse is unavailable.
FALLBACK_CIRCUIT_SCHEDULE: dict[float, tuple[Hod16, ...]] = {
    5.0: (
        Hod16.O1_OBECNE,
        Hod16.O2_OBECNE,
        Hod16.O3_OBECNE,
        Hod16.O4_OBECNE,
        Hod16.TUV_OBECNE,
        Hod16.O1_REZIM,
        Hod16.O2_REZIM,
        Hod16.O3_REZIM,
        Hod16.O4_REZIM,
        Hod16.TUV_REZIM,
        *_TEPLOTY,
    ),
    30.0: (
        Hod16.O1_TEPLOTA,
        Hod16.O2_TEPLOTA,
        Hod16.O3_TEPLOTA,
        Hod16.O4_TEPLOTA,
        Hod16.TUV_TEPLOTA,
        Hod16.O1_VLHKOST,
        Hod16.O2_VLHKOST,
        Hod16.O3_VLHKOST,
        Hod16.O4_VLHKOST,
        Hod16.TUV_VLHKOST,
    ),
}


def parse_pages_js_hod16_intervals(source: str) -> dict[Hod16, float]:
    """Return each ``HOD16`` local → poll interval in seconds.

    When the same register appears in more than one bucket, the shortest
    interval wins. Dynamic set-temp bindings (``circID`` → ``*_TEPLOTY``)
    are treated as ``PrmID5s``.

    Args:
        source: Decompressed ``Pages.js`` text from the gateway UI bundle.
    """
    best: dict[Hod16, float] = {}

    def _note(local: Hod16, interval: float) -> None:
        previous = best.get(local)
        if previous is None or interval < previous:
            best[local] = interval

    for match in _ATTR_HOD16.finditer(source):
        bucket = match.group(1)
        name = match.group(2)
        interval = _BUCKET_SECONDS.get(bucket)
        if interval is None or name not in Hod16.__members__:
            continue
        _note(Hod16[name], interval)

    if _TEPLOTY_DYNAMIC.search(source):
        for local in _TEPLOTY:
            _note(local, 5.0)

    return best


def circuit_schedule_from_pages(
    source: str | None,
    *,
    device_ac16: int = 1,
) -> dict[float, tuple[int, ...]]:
    """Build interval → wire ids for homepage circuit registers.

    Args:
        source: ``Pages.js`` text, or ``None`` to use the captured fallback.
        device_ac16: Device nibble for ``hod16_id``.
    """
    from pyatmos_wg1000.protocol import Device

    device = Device(device_ac16)
    intervals: dict[Hod16, float] = {}
    if source:
        parsed = parse_pages_js_hod16_intervals(source)
        intervals = {local: seconds for local, seconds in parsed.items() if local in _CIRCUIT_LOCALS}
        if intervals:
            LOGGER.debug(
                "Pages.js schedule: %s",
                {local.name: seconds for local, seconds in sorted(intervals.items(), key=lambda i: i[0].value)},
            )
        else:
            LOGGER.warning("Pages.js had no circuit PrmID bindings; using fallback schedule")

    if not intervals:
        for seconds, locals_ in FALLBACK_CIRCUIT_SCHEDULE.items():
            for local in locals_:
                intervals[local] = seconds
    else:
        for seconds, locals_ in FALLBACK_CIRCUIT_SCHEDULE.items():
            for local in locals_:
                intervals.setdefault(local, seconds)

    buckets: dict[float, list[int]] = {}
    for local, seconds in intervals.items():
        buckets.setdefault(seconds, []).append(hod16_id(local, device=device))
    return {seconds: tuple(sorted(ids)) for seconds, ids in sorted(buckets.items())}


__all__ = [
    "FALLBACK_CIRCUIT_SCHEDULE",
    "circuit_schedule_from_pages",
    "parse_pages_js_hod16_intervals",
]
