"""Diagnostic sensors for the active transport."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import atmos_device_info
from .runtime import AtmosRuntime
from .source import ActiveSource
from .wiring import runtime_for

_SCAN = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the active-source sensor and, when RS485 is configured, the byte counter.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        async_add_entities: Home Assistant entity registrar.
    """
    runtime = runtime_for(hass, entry)
    entities: list[SensorEntity] = [AtmosActiveSourceSensor(entry, runtime)]
    if runtime.config.serial:
        entities.append(AtmosSerialBytesSensor(entry, runtime))
    async_add_entities(entities)


class AtmosActiveSourceSensor(SensorEntity):
    """Which transport currently owns register values."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "active_source"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [
        ActiveSource.SERIAL.value,
        ActiveSource.WG1000.value,
        ActiveSource.NONE.value,
    ]

    def __init__(self, entry: ConfigEntry, runtime: AtmosRuntime) -> None:
        """Bind the sensor to one config entry."""
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_active_source"
        self._attr_device_info = atmos_device_info(entry, runtime)

    @property
    def available(self) -> bool:
        """Unavailable when every configured transport is down."""
        return self._runtime.active_source() is not ActiveSource.NONE

    @property
    def native_value(self) -> str:
        """Return ``serial``, ``wg1000``, or ``none``."""
        return self._runtime.active_source().value

    async def async_added_to_hass(self) -> None:
        """Refresh when the runtime changes source or values."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()


class AtmosSerialBytesSensor(SensorEntity):
    """How many raw RS485 bytes have been read since setup.

    The counter moves when the port is alive. It does not mean a register
    was decoded.
    """

    _attr_has_entity_name = True
    _attr_should_poll = True
    _attr_scan_interval = _SCAN
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "serial_bytes"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "B"
    _attr_suggested_display_precision = 0

    def __init__(self, entry: ConfigEntry, runtime: AtmosRuntime) -> None:
        """Bind the counter to one config entry."""
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_serial_bytes"
        self._attr_device_info = atmos_device_info(entry, runtime)

    @property
    def available(self) -> bool:
        """Available while the serial port is open."""
        return self._runtime.serial_open

    @property
    def native_value(self) -> int:
        """Return the running byte count."""
        return self._runtime.serial_bytes_seen
