"""Electrical Heater integration for Home Assistant.

Turns a plain switch, one or more temperature sensors and a power sensor into
a full thermostat (climate entity) with a boost timer.

This file only handles setup and teardown. The logic lives in
``controller.py`` and the entities in the platform files.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HUMIDITY_SENSOR_LEGACY, CONF_HUMIDITY_SENSORS, PLATFORMS
from .controller import HeaterController

_LOGGER = logging.getLogger(__name__)

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Upgrade heaters created by an older version of this integration.

    Home Assistant calls this before setup when the stored entry version is
    lower than ``ElectricalHeaterConfigFlow.VERSION``.

    Version 1 -> 2: the single ``humidity_sensor`` became a list
    ``humidity_sensors``. Both the initial data and the options are converted.
    """
    if entry.version > 2:
        # Created by a newer release than this one; we can't read it.
        return False

    if entry.version == 1:

        def upgrade(conf: dict[str, Any]) -> dict[str, Any]:
            """Move the old single humidity sensor into the new list."""
            new = dict(conf)
            if CONF_HUMIDITY_SENSOR_LEGACY in new:
                old = new.pop(CONF_HUMIDITY_SENSOR_LEGACY)
                new[CONF_HUMIDITY_SENSORS] = [old] if old else []
            return new

        hass.config_entries.async_update_entry(
            entry, data=upgrade(entry.data), options=upgrade(entry.options), version=2
        )
        _LOGGER.debug("Migrated %s to config version 2", entry.title)

    return True
