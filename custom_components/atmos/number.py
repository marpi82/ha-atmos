"""Comfort and reduced setpoint number entities per circuit."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyatmos_wg1000.protocol import Hod16, encode_packed_setpoints, hod16_id

from .circuit import CIRCUIT_TUV, CircuitState
from .entity import atmos_circuit_device_info, ensure_circuit_device, ensure_hub_device
from .runtime import AtmosRuntime
from .source import ActiveSource
from .wiring import runtime_for

_TEPLOTY = (Hod16.O1_TEPLOTY, Hod16.O2_TEPLOTY, Hod16.O3_TEPLOTY, Hod16.O4_TEPLOTY, Hod16.TUV_TEPLOTY)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create comfort/reduced number entities for active circuits."""
    runtime = runtime_for(hass, entry)
    if not runtime.config.wg1000:
        return
    hub = ensure_hub_device(hass, entry, runtime)
    known: set[tuple[int, str]] = set()
    entities = _number_entities(hass, entry, runtime, hub, known)
    if entities:
        async_add_entities(entities)

    @callback
    def _discover() -> None:
        added = _number_entities(hass, entry, runtime, hub, known)
        if added:
            async_add_entities(added)

    entry.async_on_unload(runtime.add_listener(_discover))


def _number_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    hub: object,
    known: set[tuple[int, str]],
) -> list[AtmosCircuitSetpointNumber]:
    added: list[AtmosCircuitSetpointNumber] = []
    via_device_id = hub.id  # type: ignore[attr-defined]
    for circuit in runtime.circuits:
        if not circuit.active:
            continue
        ensure_circuit_device(hass, entry, circuit=circuit.index, name=circuit.name, hub=hub)  # type: ignore[arg-type]
        for kind in ("comfort", "reduced"):
            key = (circuit.index, kind)
            if key in known:
                continue
            known.add(key)
            added.append(
                AtmosCircuitSetpointNumber(
                    entry,
                    runtime,
                    circuit=circuit,
                    kind=kind,
                    via_device_id=via_device_id,
                )
            )
    return added


class AtmosCircuitSetpointNumber(NumberEntity):
    """One comfort or reduced setpoint for a homepage circuit."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: AtmosRuntime,
        *,
        circuit: CircuitState,
        kind: str,
        via_device_id: str,
    ) -> None:
        """Bind one setpoint number entity."""
        self._entry = entry
        self._runtime = runtime
        self._index = circuit.index
        self._kind = kind
        self._via_device_id = via_device_id
        self._attr_translation_key = f"setpoint_{kind}"
        self._attr_unique_id = f"{entry.entry_id}_circ{circuit.index}_{kind}"
        self._attr_device_info = atmos_circuit_device_info(
            entry,
            circuit=circuit.index,
            name=circuit.name,
            via_device_id=via_device_id,
        )
        if circuit.index == CIRCUIT_TUV:
            self._attr_native_min_value = 10.0
            self._attr_native_max_value = 90.0
            self._attr_native_step = 1.0
        else:
            self._attr_native_min_value = 8.0
            self._attr_native_max_value = 28.0
            self._attr_native_step = 0.1

    def _state(self) -> CircuitState | None:
        return self._runtime.circuit(self._index)

    @property
    def available(self) -> bool:
        """Available while WG1000 owns state and the circuit is active."""
        if self._runtime.active_source() is not ActiveSource.WG1000:
            return False
        state = self._state()
        return state is not None and state.active

    @property
    def native_value(self) -> float | None:
        """Return the comfort or reduced setpoint."""
        state = self._state()
        if state is None:
            return None
        return state.comfort_c if self._kind == "comfort" else state.reduced_c

    async def async_set_native_value(self, value: float) -> None:
        """Write both setpoints with this half updated."""
        state = self._state()
        if state is None or state.comfort_c is None or state.reduced_c is None:
            return
        comfort = value if self._kind == "comfort" else state.comfort_c
        reduced = value if self._kind == "reduced" else state.reduced_c
        word = encode_packed_setpoints(comfort, reduced)
        await self._runtime.write_registers([(hod16_id(_TEPLOTY[self._index]), word)])

    async def async_added_to_hass(self) -> None:
        """Refresh when circuit snapshots update."""
        self.async_on_remove(self._runtime.add_listener(self._refresh))

    @callback
    def _refresh(self) -> None:
        state = self._state()
        if state is not None:
            self._attr_device_info = atmos_circuit_device_info(
                self._entry,
                circuit=self._index,
                name=state.name,
                via_device_id=self._via_device_id,
            )
        self.async_write_ha_state()
