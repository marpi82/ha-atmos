"""Shared device identity for ATMOS entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .runtime import AtmosRuntime


def ensure_hub_device(
    hass: object,
    entry: ConfigEntry,
    runtime: AtmosRuntime,
) -> dr.DeviceEntry:
    """Create or update the gateway hub device and return it.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        runtime: Live source selection for that entry.
    """
    registry = dr.async_get(hass)  # type: ignore[arg-type]
    return registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **atmos_hub_device_info(entry, runtime),
    )


def ensure_group_device(
    hass: object,
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    *,
    skupina: int,
    title: str,
    hub: dr.DeviceEntry,
) -> dr.DeviceEntry:
    """Create or update an Info group child device under ``hub``.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        runtime: Live source selection for that entry.
        skupina: Info group id from the gateway.
        title: Localized group title.
        hub: Parent hub device (provides ``via_device_id``).
    """
    registry = dr.async_get(hass)  # type: ignore[arg-type]
    return registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_g{skupina}")},
        manufacturer="ATMOS",
        model="WG1000 Info",
        name=title,
        via_device_id=hub.id,
    )


def ensure_circuit_device(
    hass: object,
    entry: ConfigEntry,
    *,
    circuit: int,
    name: str,
    hub: dr.DeviceEntry,
) -> dr.DeviceEntry:
    """Create or update a homepage circuit device under ``hub``.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        circuit: Circuit index 0..4 (O1..O4, TUV).
        name: Display name (OwnText or TUV).
        hub: Parent hub device.
    """
    registry = dr.async_get(hass)  # type: ignore[arg-type]
    return registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_circ{circuit}")},
        manufacturer="ATMOS",
        model="WG1000 Circuit",
        name=name,
        via_device_id=hub.id,
    )


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
    via_device_id: str,
) -> DeviceInfo:
    """Return a child device for one Info page group.

    Args:
        entry: ATMOS config entry.
        runtime: Live source selection for that entry.
        skupina: Info group id from the gateway.
        title: Localized group title.
        via_device_id: Hub device id from the device registry.
    """
    del runtime  # unused; kept for call-site symmetry with hub helper
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_g{skupina}")},
        manufacturer="ATMOS",
        model="WG1000 Info",
        name=title,
        via_device_id=via_device_id,
    )


def atmos_circuit_device_info(
    entry: ConfigEntry,
    *,
    circuit: int,
    name: str,
    via_device_id: str,
) -> DeviceInfo:
    """Return a child device for one homepage circuit.

    Args:
        entry: ATMOS config entry.
        circuit: Circuit index 0..4.
        name: Display name.
        via_device_id: Hub device id.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_circ{circuit}")},
        manufacturer="ATMOS",
        model="WG1000 Circuit",
        name=name,
        via_device_id=via_device_id,
    )


# Backwards-compatible alias used by diagnostic entities.
def atmos_device_info(entry: ConfigEntry, runtime: AtmosRuntime) -> DeviceInfo:
    """Return the hub device (alias for :func:`atmos_hub_device_info`)."""
    return atmos_hub_device_info(entry, runtime)
