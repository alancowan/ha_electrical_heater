"""Electrical Heater integration for Home Assistant.

Turns a plain switch, one or more temperature sensors and a power sensor into
a full thermostat (climate entity) with a boost timer.

This file only handles setup and teardown. The logic lives in
``controller.py`` and the entities in the platform files.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .controller import HeaterController

# A config entry whose runtime_data holds this heater's controller.
type ElectricalHeaterConfigEntry = ConfigEntry[HeaterController]


async def async_setup_entry(hass: HomeAssistant, entry: ElectricalHeaterConfigEntry) -> bool:
    """Set up one heater from a config entry (one entry = one heater).

    1. Create the controller and store it on the entry so entities can find it.
    2. Create the entities (climate, number, sensor, binary_sensor).
    3. Start watching the sensors.
    4. Reload when the user changes the options.
    """
    controller = HeaterController(hass, entry)
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()

    # When the options change (via "Configure"), reload so new settings apply.
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElectricalHeaterConfigEntry) -> bool:
    """Remove the entities and stop the controller (on delete or reload)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload_on_update(hass: HomeAssistant, entry: ElectricalHeaterConfigEntry) -> None:
    """Reload the integration after the options were changed."""
    await hass.config_entries.async_reload(entry.entry_id)
