"""Binary sensors: "Heating" and "Temperature sensor problem".

* Heating - on while the power sensor shows the heater drawing power.
* Temperature sensor problem - on when any temperature sensor is stale or
  unavailable, so you can build an alert automation on it. Only exists
  when temperature sensors are configured.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElectricalHeaterConfigEntry
from .entity import ElectricalHeaterEntity, remove_unused_entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectricalHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the binary sensors for this heater."""
    controller = entry.runtime_data
    entities: list[BinarySensorEntity] = [ElectricalHeaterHeating(controller)]

    if controller.temp_sensors:
        entities.append(ElectricalHeaterSensorProblem(controller))
    else:
        remove_unused_entity(hass, entry, Platform.BINARY_SENSOR, "sensor_problem")

    async_add_entities(entities)


class ElectricalHeaterHeating(ElectricalHeaterEntity, BinarySensorEntity):
    """On when the heater is really heating (power above threshold)."""

    _attr_translation_key = "heating"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, controller) -> None:
        """Register with the controller under the key "heating"."""
        super().__init__(controller, "heating")

    @property
    def is_on(self) -> bool:
        """True while power consumption is above the threshold."""
        return self.controller.is_heating


class ElectricalHeaterSensorProblem(ElectricalHeaterEntity, BinarySensorEntity):
    """On when one or more temperature sensors are stale or unavailable."""

    _attr_translation_key = "sensor_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, controller) -> None:
        """Register with the controller under the key "sensor_problem"."""
        super().__init__(controller, "sensor_problem")

    @property
    def is_on(self) -> bool:
        """True if any temperature sensor is being ignored."""
        reading = self.controller.temperature
        return bool(reading.stale or reading.unavailable)
