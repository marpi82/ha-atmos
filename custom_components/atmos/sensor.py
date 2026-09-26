"""Diagnostic and WG1000 Info value sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyatmos_wg1000.protocol import InfoRowType, InfoValueKind

from .entity import atmos_group_device_info, atmos_hub_device_info, ensure_group_device, ensure_hub_device
from .info_map import MappedInfoPart, map_info_row
from .runtime import AtmosRuntime
from .source import ActiveSource
from .wiring import runtime_for

_SCAN = timedelta(seconds=30)
_VALUE_TYPES = {int(InfoRowType.LONG), int(InfoRowType.SHORT)}
_VALVE_OPTIONS = ["open", "stop", "close"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create diagnostic and Info sensors for this entry.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        async_add_entities: Home Assistant entity registrar.
    """
    runtime = runtime_for(hass, entry)
    hub = ensure_hub_device(hass, entry, runtime)
    entities: list[SensorEntity] = [AtmosActiveSourceSensor(entry, runtime)]
    if runtime.config.serial:
        entities.append(AtmosSerialBytesSensor(entry, runtime))

    known: set[tuple[int, int, int]] = set()
    known_groups: set[int] = set()
    _register_info_groups(hass, entry, runtime, hub, known_groups)
    entities.extend(_info_sensors(hass, entry, runtime, hub, known))
    async_add_entities(entities)

    @callback
    def _discover() -> None:
        _register_info_groups(hass, entry, runtime, hub, known_groups)
        added = _info_sensors(hass, entry, runtime, hub, known)
        if added:
            async_add_entities(added)

    entry.async_on_unload(runtime.add_listener(_discover))


def _register_info_groups(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    hub: object,
    known_groups: set[int],
) -> None:
    """Ensure every Info ``skupina`` has a child device, even without value rows."""
    for group in runtime.info_groups:
        ensure_group_device(
            hass,
            entry,
            runtime,
            skupina=group.skupina,
            title=group.title,
            hub=hub,  # type: ignore[arg-type]
        )
        known_groups.add(group.skupina)


def _info_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    hub: object,
    known: set[tuple[int, int, int]],
) -> list[SensorEntity]:
    """Build new typed Info sensors for parts not yet registered."""
    registry = er.async_get(hass)
    added: list[SensorEntity] = []
    for group in runtime.info_groups:
        for row in group.rows:
            if row.typ not in _VALUE_TYPES:
                continue
            mapped = map_info_row(row)
            if len(mapped) > 1:
                old_uid = f"{entry.entry_id}_g{row.skupina}_c{row.caption_id}"
                if (entity_id := registry.async_get_entity_id("sensor", "atmos", old_uid)) is not None:
                    registry.async_remove(entity_id)
            for part in mapped:
                if part.part.kind is InfoValueKind.BINARY:
                    continue
                key = (part.skupina, part.caption_id, part.part_index)
                if key in known:
                    continue
                known.add(key)
                added.append(
                    AtmosInfoValueSensor(
                        entry,
                        runtime,
                        mapped=part,
                        group_title=group.title,
                        via_device_id=hub.id,  # type: ignore[attr-defined]
                    )
                )
    return added


class AtmosActiveSourceSensor(SensorEntity):
    """Which transport currently owns entity state."""

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
        self._attr_device_info = atmos_hub_device_info(entry, runtime)

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


class AtmosInfoValueSensor(SensorEntity):
    """One typed part of an Info page value row."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: AtmosRuntime,
        *,
        mapped: MappedInfoPart,
        group_title: str,
        via_device_id: str,
    ) -> None:
        """Bind one Info value part to this config entry."""
        self._entry = entry
        self._runtime = runtime
        self._mapped = mapped
        self._via_device_id = via_device_id
        self._attr_name = mapped.part.name
        self._attr_unique_id = f"{entry.entry_id}_{mapped.unique_suffix}"
        self._attr_device_info = atmos_group_device_info(
            entry,
            runtime,
            skupina=mapped.skupina,
            title=group_title,
            via_device_id=via_device_id,
        )
        self._apply_typing(mapped)

    def _apply_typing(self, mapped: MappedInfoPart) -> None:
        part = mapped.part
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_options = None
        if part.kind is InfoValueKind.VALVE:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(_VALVE_OPTIONS)
            return
        if part.kind in (InfoValueKind.NUMBER, InfoValueKind.MISSING):
            unit = part.unit_token
            if unit == "°C":
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
                self._attr_state_class = SensorStateClass.MEASUREMENT
            elif unit == "%":
                self._attr_native_unit_of_measurement = PERCENTAGE
                self._attr_state_class = SensorStateClass.MEASUREMENT
                if mapped.humidity_hint:
                    self._attr_device_class = SensorDeviceClass.HUMIDITY
            elif unit == "h":
                self._attr_device_class = SensorDeviceClass.DURATION
                self._attr_native_unit_of_measurement = UnitOfTime.HOURS
                self._attr_state_class = SensorStateClass.MEASUREMENT
            elif unit == "min":
                self._attr_device_class = SensorDeviceClass.DURATION
                self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
                self._attr_state_class = SensorStateClass.MEASUREMENT
            elif unit == "x":
                self._attr_state_class = SensorStateClass.MEASUREMENT

    def _current(self) -> MappedInfoPart | None:
        row = self._runtime.info_row(self._mapped.skupina, self._mapped.caption_id)
        if row is None:
            return None
        parts = map_info_row(row)
        if self._mapped.part_index >= len(parts):
            return None
        return parts[self._mapped.part_index]

    @property
    def available(self) -> bool:
        """Available while WG1000 owns state and this part exists."""
        if self._runtime.active_source() is not ActiveSource.WG1000:
            return False
        return self._current() is not None

    @property
    def native_value(self) -> float | str | None:
        """Return the typed value, or ``None`` when missing (``---``)."""
        current = self._current()
        if current is None:
            return None
        part = current.part
        if part.kind is InfoValueKind.MISSING:
            return None
        if part.kind is InfoValueKind.NUMBER:
            return part.number
        if part.kind is InfoValueKind.VALVE:
            return part.valve
        return part.text if part.text is not None else part.raw

    async def async_added_to_hass(self) -> None:
        """Refresh when the runtime stores a new Info dump."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        title = self._runtime.group_title(self._mapped.skupina)
        if title is not None:
            self._attr_device_info = atmos_group_device_info(
                self._entry,
                self._runtime,
                skupina=self._mapped.skupina,
                title=title,
                via_device_id=self._via_device_id,
            )
        current = self._current()
        if current is not None:
            self._mapped = current
            self._attr_name = current.part.name
            self._apply_typing(current)
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
        self._attr_device_info = atmos_hub_device_info(entry, runtime)

    @property
    def available(self) -> bool:
        """Available while the serial port is open."""
        return self._runtime.serial_open

    @property
    def native_value(self) -> int:
        """Return the running byte count."""
        return self._runtime.serial_bytes_seen
