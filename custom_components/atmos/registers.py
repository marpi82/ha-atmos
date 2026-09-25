"""WG1000 register map used by the Home Assistant entities.

Ids come from ``py-atmos-wg1000`` only. Do not invent wire ids here.

TODO(rs485): when the serial codec lands, decoded bus samples share the same
register ids through :meth:`AtmosRuntime.value` and become primary via
:mod:`custom_components.atmos.source`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pyatmos_wg1000.protocol import Hod16, hod16_id


@dataclass(frozen=True, slots=True)
class TemperatureSensorSpec:
    """One temperature entity backed by a HOD16 live register."""

    key: str
    local: Hod16

    @property
    def register_id(self) -> int:
        """Return the packed WG1000 wire id."""
        return hod16_id(self.local)


@dataclass(frozen=True, slots=True)
class HumiditySensorSpec:
    """One humidity entity backed by a HOD16 live register."""

    key: str
    local: Hod16

    @property
    def register_id(self) -> int:
        """Return the packed WG1000 wire id."""
        return hod16_id(self.local)


@dataclass(frozen=True, slots=True)
class SetpointSensorSpec:
    """Comfort or reduced setpoint packed in a ``*_TEPLOTY`` word."""

    key: str
    local: Hod16
    half: str  # "comfort" | "reduced"

    @property
    def register_id(self) -> int:
        """Return the packed WG1000 wire id."""
        return hod16_id(self.local)


TEMPERATURE_SENSORS: Final[tuple[TemperatureSensorSpec, ...]] = (
    TemperatureSensorSpec("outdoor_temperature", Hod16.AF),
    TemperatureSensorSpec("outdoor_temperature_min", Hod16.AF_MIN),
    TemperatureSensorSpec("outdoor_temperature_max", Hod16.AF_MAX),
    TemperatureSensorSpec("circuit_1_temperature", Hod16.O1_TEPLOTA),
    TemperatureSensorSpec("circuit_2_temperature", Hod16.O2_TEPLOTA),
    TemperatureSensorSpec("circuit_3_temperature", Hod16.O3_TEPLOTA),
    TemperatureSensorSpec("circuit_4_temperature", Hod16.O4_TEPLOTA),
    TemperatureSensorSpec("dhw_temperature", Hod16.TUV_TEPLOTA),
)

HUMIDITY_SENSORS: Final[tuple[HumiditySensorSpec, ...]] = (
    HumiditySensorSpec("circuit_1_humidity", Hod16.O1_VLHKOST),
    HumiditySensorSpec("circuit_2_humidity", Hod16.O2_VLHKOST),
    HumiditySensorSpec("circuit_3_humidity", Hod16.O3_VLHKOST),
    HumiditySensorSpec("circuit_4_humidity", Hod16.O4_VLHKOST),
    HumiditySensorSpec("dhw_humidity", Hod16.TUV_VLHKOST),
)

SETPOINT_SENSORS: Final[tuple[SetpointSensorSpec, ...]] = (
    SetpointSensorSpec("circuit_1_comfort_setpoint", Hod16.O1_TEPLOTY, "comfort"),
    SetpointSensorSpec("circuit_1_reduced_setpoint", Hod16.O1_TEPLOTY, "reduced"),
    SetpointSensorSpec("circuit_2_comfort_setpoint", Hod16.O2_TEPLOTY, "comfort"),
    SetpointSensorSpec("circuit_2_reduced_setpoint", Hod16.O2_TEPLOTY, "reduced"),
    SetpointSensorSpec("circuit_3_comfort_setpoint", Hod16.O3_TEPLOTY, "comfort"),
    SetpointSensorSpec("circuit_3_reduced_setpoint", Hod16.O3_TEPLOTY, "reduced"),
    SetpointSensorSpec("circuit_4_comfort_setpoint", Hod16.O4_TEPLOTY, "comfort"),
    SetpointSensorSpec("circuit_4_reduced_setpoint", Hod16.O4_TEPLOTY, "reduced"),
    SetpointSensorSpec("dhw_comfort_setpoint", Hod16.TUV_TEPLOTY, "comfort"),
    SetpointSensorSpec("dhw_reduced_setpoint", Hod16.TUV_TEPLOTY, "reduced"),
)


def pull_register_ids() -> tuple[int, ...]:
    """Return WG1000 register ids to poll.

    Returns:
        Unique packed wire ids for the sensors currently exposed.
    """
    ids: list[int] = []
    seen: set[int] = set()
    specs: tuple[TemperatureSensorSpec | HumiditySensorSpec | SetpointSensorSpec, ...] = (
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
        *SETPOINT_SENSORS,
    )
    for spec in specs:
        register_id = spec.register_id
        if register_id not in seen:
            seen.add(register_id)
            ids.append(register_id)
    return tuple(ids)
