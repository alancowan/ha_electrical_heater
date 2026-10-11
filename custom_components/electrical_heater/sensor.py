"""The combined temperature sensor.

Shows the temperature the thermostat actually uses (the average of all
fresh temperature sensors), which is handy for history graphs.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElectricalHeaterConfigEntry
from .const import ATTR_ACTIVE_SENSORS, ATTR_STALE_SENSORS
from .entity import ElectricalHeaterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectricalHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the combined temperature sensor for this heater."""
    async_add_entities([ElectricalHeaterTemperature(entry.runtime_data)])


class ElectricalHeaterTemperature(ElectricalHeaterEntity, SensorEntity):
    """Average temperature of all usable temperature sensors."""

    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, controller) -> None:
        """Use the system temperature unit (°C or °F)."""
        super().__init__(controller, "temperature")
        self._attr_native_unit_of_measurement = controller.hass.config.units.temperature_unit

    @property
    def native_value(self) -> float | None:
        """The averaged temperature, or None (unknown) if no sensor is usable."""
        return self.controller.temperature.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which sensors were used and which were ignored."""
        return {
            ATTR_ACTIVE_SENSORS: self.controller.temperature.active,
            ATTR_STALE_SENSORS: self.controller.temperature.stale,
            "unavailable_temperature_sensors": self.controller.temperature.unavailable,
        }
