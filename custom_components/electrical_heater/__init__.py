"""Electrical Heater integration for Home Assistant.

Turns a plain switch, one or more temperature sensors and a power sensor into
a full thermostat (climate entity) with a boost timer, plus a matching
dashboard card.

This file only handles setup and teardown. The logic lives in
``controller.py``, the entities in the platform files and the card in
``frontend/electrical-heater-card.js``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import (
    CARD_FILENAME,
    CARD_URL,
    CONF_HUMIDITY_SENSOR_LEGACY,
    CONF_HUMIDITY_SENSORS,
    DOMAIN,
    PLATFORMS,
)
from .controller import HeaterController

_LOGGER = logging.getLogger(__name__)

# Heaters are only set up through the UI, never in configuration.yaml.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# A config entry whose runtime_data holds this heater's controller.
type ElectricalHeaterConfigEntry = ConfigEntry[HeaterController]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Run once when Home Assistant loads the integration (before any heater).

    Makes the dashboard card available, so nobody has to add it as a
    dashboard resource by hand.
    """
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the card's JavaScript file and load it on every dashboard.

    1. Serve ``frontend/electrical-heater-card.js`` at ``CARD_URL``.
    2. Tell the frontend to load that URL. ``?v=<version>`` makes browsers
       fetch the new file after an update instead of using an old cached copy.

    The file is served with long-lived cache headers. Without them, phones
    and tablets re-download it when the app wakes from sleep, often before
    the network is back; the download fails and the card shows an error
    until the page is reloaded. The versioned URL keeps updates working.
    """
    if hass.http is None:
        # No web server running (e.g. during tests), so nothing to serve.
        return

    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), cache_headers=True)]
    )

    if "frontend" in hass.config.components:
        integration = await async_get_integration(hass, DOMAIN)
        add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")


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
