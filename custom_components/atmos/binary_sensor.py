"""RS485 link diagnostic and Info ON/OFF binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyatmos_wg1000.protocol import InfoRowType, InfoValueKind

from .entity import atmos_device_info, atmos_group_device_info, ensure_group_device, ensure_hub_device
from .info_map import MappedInfoPart, map_info_row
from .runtime import AtmosRuntime
from .source import ActiveSource
from .wiring import runtime_for

_VALUE_TYPES = {int(InfoRowType.LONG), int(InfoRowType.SHORT)}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create RS485 link and Info binary sensors.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
        async_add_entities: Home Assistant entity registrar.
    """
    runtime = runtime_for(hass, entry)
    entities: list[BinarySensorEntity] = []
    if runtime.config.serial:
        entities.append(AtmosSerialLinkSensor(entry, runtime))

    hub = ensure_hub_device(hass, entry, runtime)
    known: set[tuple[int, int, int]] = set()
    entities.extend(_info_binary_sensors(entry, runtime, hub.id, known))
    if entities:
        async_add_entities(entities)

    @callback
    def _discover() -> None:
        for group in runtime.info_groups:
            ensure_group_device(
                hass,
                entry,
                runtime,
                skupina=group.skupina,
                title=group.title,
                hub=hub,
            )
        added = _info_binary_sensors(entry, runtime, hub.id, known)
        if added:
            async_add_entities(added)

    entry.async_on_unload(runtime.add_listener(_discover))


def _info_binary_sensors(
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    via_device_id: str,
    known: set[tuple[int, int, int]],
) -> list[BinarySensorEntity]:
    """Build ON/OFF Info parts not yet registered."""
    added: list[BinarySensorEntity] = []
    titles = {group.skupina: group.title for group in runtime.info_groups}
    for group in runtime.info_groups:
        for row in group.rows:
            if row.typ not in _VALUE_TYPES:
                continue
            for part in map_info_row(row):
                if part.part.kind is not InfoValueKind.BINARY:
                    continue
                key = (part.skupina, part.caption_id, part.part_index)
                if key in known:
                    continue
                known.add(key)
                added.append(
                    AtmosInfoBinarySensor(
                        entry,
                        runtime,
                        mapped=part,
                        group_title=titles.get(part.skupina, group.title),
                        via_device_id=via_device_id,
                    )
                )
    return added


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


class AtmosInfoBinarySensor(BinarySensorEntity):
    """ON/OFF Info value part (pumps, fans, outputs)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: AtmosRuntime,
        *,
        mapped: MappedInfoPart,
        group_title: str,
        via_device_id: str,
    ) -> None:
        """Bind one binary Info part."""
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

    def _current(self) -> MappedInfoPart | None:
        row = self._runtime.info_row(self._mapped.skupina, self._mapped.caption_id)
        if row is None:
            return None
        parts = map_info_row(row)
        if self._mapped.part_index >= len(parts):
            return None
        part = parts[self._mapped.part_index]
        if part.part.kind is not InfoValueKind.BINARY:
            return None
        return part

    @property
    def available(self) -> bool:
        """Available while WG1000 owns state and this part is binary."""
        if self._runtime.active_source() is not ActiveSource.WG1000:
            return False
        return self._current() is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the output is ON."""
        current = self._current()
        if current is None:
            return None
        return current.part.binary_on

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
        self.async_write_ha_state()
