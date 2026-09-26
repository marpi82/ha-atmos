"""Homepage circuit climate entities (PARAM HOD16)."""

from __future__ import annotations

from typing import ClassVar

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyatmos_wg1000.protocol import (
    Hod16,
    encode_circuit_regime,
    encode_packed_setpoints,
    hod16_id,
    regime_preset_index,
)

from .circuit import CIRCUIT_TUV, SIMPLE_PRESETS, CircuitState
from .entity import atmos_circuit_device_info, ensure_circuit_device, ensure_hub_device
from .runtime import AtmosRuntime
from .source import ActiveSource
from .wiring import runtime_for

_TEPLOTY = (Hod16.O1_TEPLOTY, Hod16.O2_TEPLOTY, Hod16.O3_TEPLOTY, Hod16.O4_TEPLOTY, Hod16.TUV_TEPLOTY)
_REZIM = (Hod16.O1_REZIM, Hod16.O2_REZIM, Hod16.O3_REZIM, Hod16.O4_REZIM, Hod16.TUV_REZIM)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create climate entities for active homepage circuits."""
    runtime = runtime_for(hass, entry)
    if not runtime.config.wg1000:
        return
    hub = ensure_hub_device(hass, entry, runtime)
    known: set[int] = set()
    entities = _climate_entities(hass, entry, runtime, hub, known)
    if entities:
        async_add_entities(entities)

    @callback
    def _discover() -> None:
        added = _climate_entities(hass, entry, runtime, hub, known)
        if added:
            async_add_entities(added)

    entry.async_on_unload(runtime.add_listener(_discover))


def _climate_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: AtmosRuntime,
    hub: object,
    known: set[int],
) -> list[AtmosCircuitClimate]:
    added: list[AtmosCircuitClimate] = []
    via_device_id = hub.id  # type: ignore[attr-defined]
    for circuit in runtime.circuits:
        if not circuit.active or circuit.index in known:
            continue
        known.add(circuit.index)
        ensure_circuit_device(hass, entry, circuit=circuit.index, name=circuit.name, hub=hub)  # type: ignore[arg-type]
        added.append(AtmosCircuitClimate(entry, runtime, circuit=circuit, via_device_id=via_device_id))
    return added


class AtmosCircuitClimate(ClimateEntity):
    """One homepage circuit as a heating climate entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = None
    _attr_translation_key = "circuit"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes: ClassVar[list[str]] = list(SIMPLE_PRESETS)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        entry: ConfigEntry,
        runtime: AtmosRuntime,
        *,
        circuit: CircuitState,
        via_device_id: str,
    ) -> None:
        """Bind one circuit climate."""
        self._entry = entry
        self._runtime = runtime
        self._index = circuit.index
        self._via_device_id = via_device_id
        self._attr_unique_id = f"{entry.entry_id}_circ{circuit.index}_climate"
        self._attr_device_info = atmos_circuit_device_info(
            entry,
            circuit=circuit.index,
            name=circuit.name,
            via_device_id=via_device_id,
        )
        if circuit.index == CIRCUIT_TUV:
            self._attr_min_temp = 10.0
            self._attr_max_temp = 90.0
            self._attr_target_temperature_step = 1.0
        else:
            self._attr_min_temp = 8.0
            self._attr_max_temp = 28.0
            self._attr_target_temperature_step = 0.1

    def _state(self) -> CircuitState | None:
        return self._runtime.circuit(self._index)

    @property
    def available(self) -> bool:
        """Available while WG1000 is active and the circuit snapshot exists."""
        if self._runtime.active_source() is not ActiveSource.WG1000:
            return False
        state = self._state()
        return state is not None and state.active

    @property
    def current_temperature(self) -> float | None:
        """Return the measured circuit temperature."""
        state = self._state()
        return None if state is None else state.current_c

    @property
    def current_humidity(self) -> float | None:
        """Return humidity when the circuit reports it."""
        state = self._state()
        return None if state is None else state.humidity

    @property
    def target_temperature(self) -> float | None:
        """Return the active setpoint for the current temp icon type."""
        state = self._state()
        return None if state is None else state.active_setpoint_c

    @property
    def hvac_mode(self) -> HVACMode:
        """HEAT while the circuit is active; OFF for standby preset."""
        state = self._state()
        if state is None or not state.active or state.preset == "standby":
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        """Return the simple regime preset when known."""
        state = self._state()
        if state is None:
            return None
        if state.preset in SIMPLE_PRESETS:
            return state.preset
        return None

    async def async_set_temperature(self, **kwargs: object) -> None:
        """Write the active half of the packed setpoint word."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if not isinstance(temperature, int | float):
            return
        state = self._state()
        if state is None or state.comfort_c is None or state.reduced_c is None:
            return
        comfort = float(temperature) if state.temp_type != 2 else state.comfort_c
        reduced = state.reduced_c if state.temp_type != 2 else float(temperature)
        word = encode_packed_setpoints(comfort, reduced)
        await self._runtime.write_registers([(hod16_id(_TEPLOTY[self._index]), word)])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Write a simple permanent regime."""
        if preset_mode not in SIMPLE_PRESETS:
            return
        word = encode_circuit_regime(regime_preset_index(preset_mode))
        await self._runtime.write_registers([(hod16_id(_REZIM[self._index]), word)])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Map OFF to standby and HEAT to comfort when switching on."""
        if hvac_mode is HVACMode.OFF:
            await self.async_set_preset_mode("standby")
        elif hvac_mode is HVACMode.HEAT:
            await self.async_set_preset_mode("comfort")

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
