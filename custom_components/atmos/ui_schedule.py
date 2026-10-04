"""Homepage circuit PARAM poll buckets from stock ``Pages.js``.

HOD16 interval extraction lives in :mod:`pyatmos_wg1000.protocol.pages`. This
module keeps only the circuit-register filter and the captured fallback used
when the UI bundle cannot be downloaded.
"""

from __future__ import annotations

import logging

from pyatmos_wg1000.protocol import Hod16, hod16_id, parse_pages_js_hod16_intervals

LOGGER = logging.getLogger(__name__)

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
]
