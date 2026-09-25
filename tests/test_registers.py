"""Tests for the WG1000 register map exposed to Home Assistant."""

from __future__ import annotations

from custom_components.atmos.registers import (
    HUMIDITY_SENSORS,
    SETPOINT_SENSORS,
    TEMPERATURE_SENSORS,
    pull_register_ids,
)


def test_pull_register_ids_are_unique_and_non_empty() -> None:
    """The poll list must include every mapped sensor without duplicates."""
    ids = pull_register_ids()
    assert ids
    assert len(ids) == len(set(ids))
    expected = {
        *(spec.register_id for spec in TEMPERATURE_SENSORS),
        *(spec.register_id for spec in HUMIDITY_SENSORS),
        *(spec.register_id for spec in SETPOINT_SENSORS),
    }
    assert set(ids) == expected


def test_setpoint_halves_share_one_register() -> None:
    """Comfort and reduced setpoints for a circuit share the packed word."""
    by_circuit = [spec for spec in SETPOINT_SENSORS if spec.key.startswith("circuit_1_")]
    assert len(by_circuit) == 2
    assert by_circuit[0].register_id == by_circuit[1].register_id
