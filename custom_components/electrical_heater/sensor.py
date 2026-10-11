"""The combined temperature and humidity sensors.

They show the values the heater actually uses (the average of all fresh
sensors), which is handy for history graphs.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElectricalHeaterConfigEntry
from .const import (
    ATTR_ACTIVE_HUMIDITY_SENSORS,
    ATTR_ACTIVE_SENSORS,
    ATTR_STALE_HUMIDITY_SENSORS,
    ATTR_STALE_SENSORS,
    ATTR_UNAVAILABLE_HUMIDITY_SENSORS,
    ATTR_UNAVAILABLE_SENSORS,
    DOMAIN,
)
from .controller import HeaterController
from .entity import ElectricalHeaterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectricalHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the combined sensors for this heater.

    The humidity sensor only exists when humidity sensors are configured.
    If they were removed in the options, the old entity is deleted too, so
    it doesn't linger as "unavailable".
    """
    controller = entry.runtime_data
    entities: list[SensorEntity] = [ElectricalHeaterTemperature(controller)]

    if controller.humidity_sensors:
        entities.append(ElectricalHeaterHumidity(controller))
    else:
        registry = er.async_get(hass)
        if entity_id := registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{entry.entry_id}_humidity"
        ):
            registry.async_remove(entity_id)

    async_add_entities(entities)


class ElectricalHeaterTemperature(ElectricalHeaterEntity, SensorEntity):
    """Average temperature of all usable temperature sensors."""

    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, controller: HeaterController) -> None:
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
            ATTR_UNAVAILABLE_SENSORS: self.controller.temperature.unavailable,
        }


class ElectricalHeaterHumidity(ElectricalHeaterEntity, SensorEntity):
    """Average humidity of all usable humidity sensors."""

    _attr_translation_key = "humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0

    def __init__(self, controller: HeaterController) -> None:
        """Register with the controller under the key "humidity"."""
        super().__init__(controller, "humidity")

    @property
    def native_value(self) -> float | None:
        """The averaged humidity, or None (unknown) if no sensor is usable."""
        return self.controller.humidity_reading.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which sensors were used and which were ignored."""
        return {
            ATTR_ACTIVE_HUMIDITY_SENSORS: self.controller.humidity_reading.active,
            ATTR_STALE_HUMIDITY_SENSORS: self.controller.humidity_reading.stale,
            ATTR_UNAVAILABLE_HUMIDITY_SENSORS: self.controller.humidity_reading.unavailable,
        }
