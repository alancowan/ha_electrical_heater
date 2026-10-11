"""The boost slider (number entity).

Moving the slider to e.g. 30 runs the heater for 30 minutes, whatever the
temperature or mode. The slider then counts down as time passes; setting it
back to 0 cancels the boost.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElectricalHeaterConfigEntry
from .entity import ElectricalHeaterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectricalHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the boost slider for this heater."""
    async_add_entities([ElectricalHeaterBoost(entry.runtime_data)])


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
