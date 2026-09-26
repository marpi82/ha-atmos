"""Shared device identity for ATMOS entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .runtime import AtmosRuntime


def atmos_hub_device_info(entry: ConfigEntry, runtime: AtmosRuntime) -> DeviceInfo:
    """Return the gateway hub device for this config entry.

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


def atmos_group_device_info(
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    *,
    skupina: int,
    title: str,
) -> DeviceInfo:
    """Return a child device for one Info page group.

    Args:
        entry: ATMOS config entry.
        runtime: Live source selection for that entry.
        skupina: Info group id from the gateway.
        title: Localized group title.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_g{skupina}")},
        manufacturer="ATMOS",
        model="WG1000 Info",
        name=title,
        via_device=(DOMAIN, entry.entry_id),
    )


# Backwards-compatible alias used by diagnostic entities.
def atmos_device_info(entry: ConfigEntry, runtime: AtmosRuntime) -> DeviceInfo:
    """Return the hub device (alias for :func:`atmos_hub_device_info`)."""
    return atmos_hub_device_info(entry, runtime)
