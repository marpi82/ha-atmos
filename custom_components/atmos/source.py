"""Choose serial listen over a WG1000 poll, unless only one path is configured."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActiveSource(StrEnum):
    """Which transport currently owns entity state."""

    SERIAL = "serial"
    WG1000 = "wg1000"
    NONE = "none"


@dataclass(frozen=True)
class SourceConfig:
    """Which transports the user configured, and when serial stops being fresh."""

    serial: bool
    wg1000: bool
    fallback_after: float

    def __post_init__(self) -> None:
        """Reject a non-positive freshness window."""
        if self.fallback_after <= 0:
            raise ValueError("fallback window must be positive")


def choose_source(
    config: SourceConfig,
    *,
    now: float,
    last_serial_update: float | None,
    serial_open: bool,
    gateway_open: bool,
) -> ActiveSource:
    """Pick the transport that should supply register values.

    Serial is primary when both paths are configured, but only after the codec
    has emitted a register update inside ``fallback_after`` seconds. Raw bytes
    do not count. WG1000 is the pull fallback. A path the user did not
    configure is never selected.

    Args:
        config: Enabled transports and the freshness window.
        now: Monotonic clock reading.
        last_serial_update: Monotonic time of the last decoded serial value.
        serial_open: The serial port is open.
        gateway_open: The WG1000 session is logged in.

    Returns:
        The active transport, or ``NONE`` when nothing usable is up.
    """
    serial_fresh = serial_open and last_serial_update is not None and (now - last_serial_update) < config.fallback_after
    if config.serial and config.wg1000:
        if serial_fresh:
            return ActiveSource.SERIAL
        if gateway_open:
            return ActiveSource.WG1000
        if serial_open:
            return ActiveSource.SERIAL
        return ActiveSource.NONE
    if config.serial:
        return ActiveSource.SERIAL if serial_open else ActiveSource.NONE
    if config.wg1000:
        return ActiveSource.WG1000 if gateway_open else ActiveSource.NONE
    return ActiveSource.NONE
