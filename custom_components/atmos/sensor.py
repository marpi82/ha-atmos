"""Diagnostic and WG1000 value sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyatmos_wg1000.protocol import decode_acd_quantity, decode_acd_temperature, decode_packed_setpoints

from .entity import atmos_device_info
from .registers import (
    HUMIDITY_SENSORS,
    SETPOINT_SENSORS,
    TEMPERATURE_SENSORS,
    HumiditySensorSpec,
    SetpointSensorSpec,
    TemperatureSensorSpec,
)
from .runtime import AtmosRuntime
from .source import ActiveSource
from .wiring import runtime_for

_SCAN = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create diagnostic and WG1000 sensors for this entry.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        async_add_entities: Home Assistant entity registrar.
    """
    runtime = runtime_for(hass, entry)
    entities: list[SensorEntity] = [AtmosActiveSourceSensor(entry, runtime)]
    entities.extend(AtmosTemperatureSensor(entry, runtime, spec) for spec in TEMPERATURE_SENSORS)
    entities.extend(AtmosHumiditySensor(entry, runtime, spec) for spec in HUMIDITY_SENSORS)
    entities.extend(AtmosSetpointSensor(entry, runtime, spec) for spec in SETPOINT_SENSORS)
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


class AtmosTemperatureSensor(SensorEntity):
    """One ACD temperature register, decoded the way the WG1000 UI does."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, entry: ConfigEntry, runtime: AtmosRuntime, spec: TemperatureSensorSpec) -> None:
        """Bind one HOD16 temperature to this config entry."""
        self._runtime = runtime
        self._register_id = spec.register_id
        self._attr_translation_key = spec.key
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_device_info = atmos_device_info(entry, runtime)

    @property
    def available(self) -> bool:
        """Available while an active transport owns values."""
        return self._runtime.active_source() is not ActiveSource.NONE

    @property
    def native_value(self) -> float | None:
        """Return degrees Celsius, or ``None`` when the reading is absent."""
        word = self._runtime.value(self._register_id)
        if word is None:
            return None
        return decode_acd_temperature(word)

    async def async_added_to_hass(self) -> None:
        """Refresh when the runtime stores a new sample."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()


class AtmosHumiditySensor(SensorEntity):
    """One ACD humidity register, decoded the way the WG1000 UI does."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 1

    def __init__(self, entry: ConfigEntry, runtime: AtmosRuntime, spec: HumiditySensorSpec) -> None:
        """Bind one HOD16 humidity register to this config entry."""
        self._runtime = runtime
        self._register_id = spec.register_id
        self._attr_translation_key = spec.key
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_device_info = atmos_device_info(entry, runtime)

    @property
    def available(self) -> bool:
        """Available while an active transport owns values."""
        return self._runtime.active_source() is not ActiveSource.NONE

    @property
    def native_value(self) -> float | None:
        """Return relative humidity, or ``None`` when the reading is absent."""
        word = self._runtime.value(self._register_id)
        if word is None:
            return None
        return decode_acd_quantity(word)

    async def async_added_to_hass(self) -> None:
        """Refresh when the runtime stores a new sample."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()


class AtmosSetpointSensor(SensorEntity):
    """Comfort or reduced setpoint from a packed ``*_TEPLOTY`` word."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, entry: ConfigEntry, runtime: AtmosRuntime, spec: SetpointSensorSpec) -> None:
        """Bind one setpoint half to this config entry."""
        self._runtime = runtime
        self._register_id = spec.register_id
        self._half = spec.half
        self._attr_translation_key = spec.key
        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_device_info = atmos_device_info(entry, runtime)

    @property
    def available(self) -> bool:
        """Available while an active transport owns values."""
        return self._runtime.active_source() is not ActiveSource.NONE

    @property
    def native_value(self) -> float | None:
        """Return the selected setpoint half in degrees Celsius."""
        word = self._runtime.value(self._register_id)
        if word is None:
            return None
        pair = decode_packed_setpoints(word)
        if self._half == "comfort":
            return pair.comfort_c
        return pair.reduced_c

    async def async_added_to_hass(self) -> None:
        """Refresh when the runtime stores a new sample."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()


class AtmosSerialBytesSensor(SensorEntity):
    """How many raw RS485 bytes have been read since setup.

    The counter moves when the port is alive. It does not mean a register
    was decoded.

    TODO(rs485): expose again when the config flow re-offers serial listen.
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
