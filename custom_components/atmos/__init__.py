"""ATMOS Home Assistant integration.

Setup imports Home Assistant only when a config entry is loaded, so the
source-selection modules can be tested without Home Assistant installed.
"""

from __future__ import annotations

from .const import DOMAIN, PLATFORMS

__all__ = ["DOMAIN", "PLATFORMS", "async_setup_entry", "async_unload_entry"]


async def async_setup_entry(hass: object, entry: object) -> bool:
    """Set up ATMOS from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
    """
    from .wiring import async_setup_entry as setup

    # Wiring is annotated with Home Assistant types. They are not imported
    # here, so this package can be imported without Home Assistant installed.
    return await setup(hass, entry)  # type: ignore[arg-type]


async def async_unload_entry(hass: object, entry: object) -> bool:
    """Unload ATMOS and close its transports.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
    """
    from .wiring import async_unload_entry as unload

    return await unload(hass, entry)  # type: ignore[arg-type]
