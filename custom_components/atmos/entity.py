"""Shared device identity for ATMOS entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .runtime import AtmosRuntime


def atmos_device_info(entry: ConfigEntry, runtime: AtmosRuntime) -> DeviceInfo:
    """Return the single device for this config entry.

    Args:
        entry: ATMOS config entry.
        runtime: Live source selection for that entry.
    """
    if runtime.config.serial and runtime.config.wg1000:
        model = "RS485 + WG1000"
    elif runtime.config.serial:
        model = "RS485"
    else:
        model = "WG1000"
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="ATMOS",
        model=model,
        name="ATMOS",
    )
