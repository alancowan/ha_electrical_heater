"""The number entities: the boost slider and the frost protection slider.

Boost: moving the slider to e.g. 30 runs the heater for 30 minutes, whatever
the temperature or mode. The slider then counts down as time passes; setting it
back to 0 cancels the boost.

Frost protection: in mode OFF the heater keeps the room at least this warm
(0 = off, max 12). Only created when there are temperature sensors.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.const import Platform, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElectricalHeaterConfigEntry
from .const import MAX_FROST_TEMP
from .entity import ElectricalHeaterEntity, remove_unused_entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectricalHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the boost slider, and frost protection if there are temperature sensors."""
    controller = entry.runtime_data
    entities: list[NumberEntity] = [ElectricalHeaterBoost(controller)]
    if controller.has_thermostat:
        entities.append(ElectricalHeaterFrostProtection(controller))
    else:
        # Temperature sensors removed: frost protection can't work any more.
        remove_unused_entity(hass, entry, Platform.NUMBER, "frost_protection")
    async_add_entities(entities)


class ElectricalHeaterBoost(ElectricalHeaterEntity, NumberEntity):
    """Slider from 0 to the max boost time (up to 24 hours)."""

    _attr_translation_key = "boost"
    _attr_icon = "mdi:fire-circle"
    _attr_mode = NumberMode.SLIDER  # show as a slider, not an input box
    _attr_native_min_value = 0
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, controller) -> None:
        """Set the slider's maximum from the configured max boost time."""
        super().__init__(controller, "boost")
        self._attr_native_max_value = controller.max_boost_minutes
        # 1-minute steps up to 2 hours; 5-minute steps for longer boosts so a
        # long slider stays easy to set.
        self._attr_native_step = 1 if controller.max_boost_minutes <= 120 else 5

    @property
    def native_value(self) -> int:
        """Minutes of boost left (0 when no boost is running)."""
        return self.controller.boost_remaining_minutes

    async def async_set_native_value(self, value: float) -> None:
        """Start a boost of ``value`` minutes, or cancel it with 0."""
        await self.controller.async_set_boost(value)


class ElectricalHeaterFrostProtection(ElectricalHeaterEntity, RestoreNumber):
    """Lowest temperature kept in mode OFF: 0 (off) to 12, kept over restarts."""

    _attr_translation_key = "frost_protection"
    _attr_icon = "mdi:snowflake-thermometer"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_FROST_TEMP
    _attr_native_step = 0.5

    def __init__(self, controller) -> None:
        """Use the same temperature unit as the thermostat."""
        super().__init__(controller, "frost_protection")
        self._attr_native_unit_of_measurement = controller.hass.config.units.temperature_unit

    async def async_added_to_hass(self) -> None:
        """Restore the value from before a restart.

        This runs while the heater is being set up, before the controller is
        allowed to switch, so the restored value is in place in time.
        """
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) is not None and (
            last.native_value is not None
        ):
            self.controller.frost_temp = self.controller._clamp_frost(last.native_value)

    @property
    def native_value(self) -> float:
        """The frost protection temperature (0 = off)."""
        return self.controller.frost_temp

    async def async_set_native_value(self, value: float) -> None:
        """Change the frost protection temperature."""
        await self.controller.async_set_frost_temp(value)
