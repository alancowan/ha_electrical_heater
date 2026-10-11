"""The climate (thermostat) entity.

This is what the thermostat card shows: current temperature, target
temperature with + / - buttons, and the HEAT / OFF mode.
The decisions are made by the controller; this entity just shows them.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import ElectricalHeaterConfigEntry
from .const import (
    ATTR_ACTIVE_HUMIDITY_SENSORS,
    ATTR_ACTIVE_SENSORS,
    ATTR_BOOST_ACTIVE,
    ATTR_BOOST_REMAINING,
    ATTR_CO2,
    ATTR_POWER,
    ATTR_STALE_HUMIDITY_SENSORS,
    ATTR_STALE_SENSORS,
)
from .entity import ElectricalHeaterEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectricalHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the climate entity for this heater."""
    async_add_entities([ElectricalHeaterClimate(entry.runtime_data)])


class ElectricalHeaterClimate(ElectricalHeaterEntity, ClimateEntity, RestoreEntity):
    """Thermostat for one electrical heater."""

    # name=None: the entity is simply called after the device (e.g. "Office heater").
    _attr_name = None
    _attr_translation_key = "heater"
    # Only heating and off, as requested.
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    # TARGET_TEMPERATURE gives the + / - buttons on the card.
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, controller) -> None:
        """Set up the entity and copy the fixed limits from the configuration."""
        super().__init__(controller, "climate")
        if not controller.has_thermostat:
            # No temperature sensors: no HEAT mode and no target temperature
            # (so no + / -). The heater only runs via the boost slider.
            self._attr_hvac_modes = [HVACMode.OFF]
            self._attr_supported_features = ClimateEntityFeature.TURN_OFF
        self._attr_temperature_unit = controller.hass.config.units.temperature_unit
        self._attr_min_temp = controller.min_temp
        self._attr_max_temp = controller.max_temp
        self._attr_target_temperature_step = controller.temp_step

    async def async_added_to_hass(self) -> None:
        """Restore the mode and target temperature from before a restart."""
        await super().async_added_to_hass()

        hvac_mode: HVACMode | None = None
        target: float | None = None
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in (HVACMode.HEAT, HVACMode.OFF):
                hvac_mode = HVACMode(last_state.state)
            if (last_target := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                try:
                    target = float(last_target)
                except (TypeError, ValueError):
                    target = None

        # Always call restore, even with nothing saved: it tells the controller
        # it may now start switching the heater.
        self.controller.async_restore(hvac_mode, target)

    # ---- Values shown on the card ---------------------------------------

    @property
    def hvac_mode(self) -> HVACMode:
        """The selected mode: HEAT or OFF."""
        return self.controller.hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """What the heater is doing right now, based on the power sensor.

        * HEATING - drawing power (also during a boost)
        * IDLE    - mode is HEAT but the heater isn't drawing power
        * OFF     - mode is OFF and nothing is running
        """
        if self.controller.is_heating:
            return HVACAction.HEATING
        if self.controller.hvac_mode == HVACMode.HEAT or self.controller.boost_active:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def current_temperature(self) -> float | None:
        """The combined (average) room temperature."""
        return self.controller.temperature.value

    @property
    def target_temperature(self) -> float | None:
        """The temperature the thermostat is aiming for (None without sensors)."""
        if not self.controller.has_thermostat:
            return None
        return self.controller.target_temperature

    @property
    def current_humidity(self) -> float | None:
        """Average humidity of the optional humidity sensors (shown on the card)."""
        return self.controller.humidity

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra information shown in the entity's attributes."""
        attrs: dict[str, Any] = {
            ATTR_BOOST_ACTIVE: self.controller.boost_active,
            ATTR_BOOST_REMAINING: self.controller.boost_remaining_minutes,
            ATTR_POWER: self.controller.power,
            ATTR_ACTIVE_SENSORS: self.controller.temperature.active,
            ATTR_STALE_SENSORS: self.controller.temperature.stale,
        }
        if self.controller.humidity_sensors:
            attrs[ATTR_ACTIVE_HUMIDITY_SENSORS] = self.controller.humidity_reading.active
            attrs[ATTR_STALE_HUMIDITY_SENSORS] = self.controller.humidity_reading.stale
        if self.controller.co2_sensor:
            attrs[ATTR_CO2] = self.controller.co2
        return attrs

    # ---- Actions from the card / services -------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Called when the user picks HEAT or OFF."""
        await self.controller.async_set_hvac_mode(hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Called when the user presses + / - or sets a temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.controller.async_set_target_temperature(float(temperature))

    async def async_turn_on(self) -> None:
        """climate.turn_on: same as choosing HEAT."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """climate.turn_off: same as choosing OFF."""
        await self.async_set_hvac_mode(HVACMode.OFF)
