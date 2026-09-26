"""Diagnostic and WG1000 Info value sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyatmos_wg1000.protocol import InfoRowType

from .entity import atmos_group_device_info, atmos_hub_device_info
from .info import InfoGroup
from .runtime import AtmosRuntime
from .source import ActiveSource
from .wiring import runtime_for

_SCAN = timedelta(seconds=30)
_VALUE_TYPES = {int(InfoRowType.LONG), int(InfoRowType.SHORT)}


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
    entities: list[SensorEntity] = [AtmosActiveSourceSensor(entry, runtime)]
    if runtime.config.serial:
        entities.append(AtmosSerialBytesSensor(entry, runtime))

    known: set[tuple[int, int]] = set()
    known_groups: set[int] = set()
    _register_info_groups(hass, entry, runtime, runtime.info_groups, known_groups)
    entities.extend(_info_sensors(entry, runtime, runtime.info_groups, known))
    async_add_entities(entities)

    @callback
    def _discover() -> None:
        _register_info_groups(hass, entry, runtime, runtime.info_groups, known_groups)
        added = _info_sensors(entry, runtime, runtime.info_groups, known)
        if added:
            async_add_entities(added)

    entry.async_on_unload(runtime.add_listener(_discover))


def _register_info_groups(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    groups: tuple[InfoGroup, ...] | list[InfoGroup],
    known_groups: set[int],
) -> None:
    """Ensure every Info ``skupina`` has a child device, even without value rows."""
    registry = dr.async_get(hass)
    for group in groups:
        info = atmos_group_device_info(entry, runtime, skupina=group.skupina, title=group.title)
        registry.async_get_or_create(config_entry_id=entry.entry_id, **info)
        known_groups.add(group.skupina)


def _info_sensors(
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    groups: tuple[InfoGroup, ...] | list[InfoGroup],
    known: set[tuple[int, int]],
) -> list[SensorEntity]:
    """Build new value sensors for long/short Info rows not yet registered."""
    added: list[SensorEntity] = []
    for group in groups:
        for row in group.rows:
            if row.typ not in _VALUE_TYPES:
                continue
            key = (row.skupina, row.caption_id)
            if key in known:
                continue
            known.add(key)
            added.append(
                AtmosInfoSensor(
                    entry,
                    runtime,
                    skupina=row.skupina,
                    caption_id=row.caption_id,
                    group_title=group.title,
                    name=_entity_name(row.caption, row.text_a, row.text_b),
                )
            )
    return added


def _entity_name(caption: str, text_a: str, text_b: str) -> str:
    if caption:
        return caption
    if text_a and text_b:
        return f"{text_a} / {text_b}"
    return text_a or text_b or "Info"


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


class AtmosInfoSensor(SensorEntity):
    """One Info page value row as a gateway display string."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: AtmosRuntime,
        *,
        skupina: int,
        caption_id: int,
        group_title: str,
        name: str,
    ) -> None:
        """Bind one Info row to this config entry."""
        self._entry = entry
        self._runtime = runtime
        self._skupina = skupina
        self._caption_id = caption_id
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_g{skupina}_c{caption_id}"
        self._attr_device_info = atmos_group_device_info(
            entry,
            runtime,
            skupina=skupina,
            title=group_title,
        )

    @property
    def available(self) -> bool:
        """Available while WG1000 owns state and this row exists."""
        if self._runtime.active_source() is not ActiveSource.WG1000:
            return False
        return self._runtime.info_row(self._skupina, self._caption_id) is not None

    @property
    def native_value(self) -> str | None:
        """Return the gateway display string for this row."""
        row = self._runtime.info_row(self._skupina, self._caption_id)
        return None if row is None else row.value

    async def async_added_to_hass(self) -> None:
        """Refresh when the runtime stores a new Info dump."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        title = self._runtime.group_title(self._skupina)
        if title is not None:
            self._attr_device_info = atmos_group_device_info(
                self._entry,
                self._runtime,
                skupina=self._skupina,
                title=title,
            )
        row = self._runtime.info_row(self._skupina, self._caption_id)
        if row is not None:
            self._attr_name = _entity_name(row.caption, row.text_a, row.text_b)
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
