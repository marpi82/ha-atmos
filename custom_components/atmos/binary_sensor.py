"""RS485 link diagnostic."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import atmos_device_info
from .runtime import AtmosRuntime
from .wiring import runtime_for


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the RS485 link sensor when serial is configured.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        async_add_entities: Home Assistant entity registrar.
    """
    runtime = runtime_for(hass, entry)
    if not runtime.config.serial:
        return
    async_add_entities([AtmosSerialLinkSensor(entry, runtime)])


class AtmosSerialLinkSensor(BinarySensorEntity):
    """On when the serial port is open.

    This is the adapter, not a decoded boiler frame.

    TODO(rs485): create again when the config flow re-offers serial listen.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "serial_link"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, entry: ConfigEntry, runtime: AtmosRuntime) -> None:
        """Bind the link sensor to one config entry."""
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_serial_link"
        self._attr_device_info = atmos_device_info(entry, runtime)

    @property
    def is_on(self) -> bool:
        """Return whether the port is open."""
        return self._runtime.serial_open

    async def async_added_to_hass(self) -> None:
        """Refresh when the port opens or closes."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()
