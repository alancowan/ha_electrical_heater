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

    1. Serve ``frontend/electrical-heater-card.js`` at ``CARD_URL``, with
       long-lived cache headers (the URL changes with every version).
    2. Add it to the dashboard resources (Settings > Dashboards > Resources),
       the same way HACS adds cards. ``?v=<version>`` makes browsers fetch the
       new file after an update instead of using an old cached copy.

    Why resources and not ``add_extra_js_url``: extra JS is loaded as soon as
    the page opens. When a phone or tablet wakes up, the app reopens the page
    from its offline copy before the network is back, that download fails and
    the browser won't retry it, so every card shows "Custom element doesn't
    exist". Dashboard resources are loaded only once the connection to Home
    Assistant is up. ``add_extra_js_url`` is kept as a fallback for setups
    whose resources are managed in YAML.
    """
    if hass.http is None:
        # No web server running (e.g. during tests), so nothing to serve.
        return

    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), cache_headers=True)]
    )

    integration = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_URL}?v={integration.version}"

    if await _async_add_card_resource(hass, url):
        return
    if "frontend" in hass.config.components:
        _LOGGER.info(
            "Dashboard resources are managed in YAML; add %s as a module resource "
            "for the card to load reliably on phones",
            url,
        )
        add_extra_js_url(hass, url)


def _card_resources(hass: HomeAssistant) -> Any:
    """The dashboard resources collection, if it can be edited (storage mode).

    Returns None when Lovelace isn't loaded or resources are kept in YAML.
    """
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None
    # A dataclass in recent Home Assistant versions, a dict in older ones.
    resources = (
        lovelace.get("resources") if isinstance(lovelace, dict) else getattr(lovelace, "resources", None)
    )
    if resources is None or not hasattr(resources, "async_create_item"):
        return None  # YAML resources: read-only
    return resources


async def _async_add_card_resource(hass: HomeAssistant, url: str) -> bool:
    """Add (or update to this version) the card's dashboard resource.

    Returns False if resources can't be edited, so the caller can fall back.
    """
    if (resources := _card_resources(hass)) is None:
        return False
    await resources.async_get_info()  # makes sure the stored list is loaded

    ours = [r for r in resources.async_items() if r["url"].startswith(CARD_URL)]
    if not ours:
        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.debug("Added dashboard resource %s", url)
        return True

    # Keep one entry, pointing at the current version; drop any duplicates.
    first, *extra = ours
    if first["url"] != url:
        await resources.async_update_item(first["id"], {"res_type": "module", "url": url})
    for item in extra:
        await resources.async_delete_item(item["id"])
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """When the last heater is deleted, remove the card's dashboard resource."""
    remaining = [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]
    if remaining or (resources := _card_resources(hass)) is None:
        return
    await resources.async_get_info()
    for item in list(resources.async_items()):
        if item["url"].startswith(CARD_URL):
            await resources.async_delete_item(item["id"])


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
