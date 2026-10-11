"""Base class shared by every entity of this integration.

It does two things so the individual entities don't have to (plus a
helper, remove_unused_entity, for entities a heater no longer needs):

* puts all entities on one device (named after the heater), and
* refreshes the entity whenever the controller reports a change.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import HeaterController


class ElectricalHeaterEntity(Entity):
    """Common behaviour for climate, number, sensor and binary_sensor."""

    # Entity names are combined with the device name, e.g. "Office heater Boost".
    _attr_has_entity_name = True
    # The controller pushes updates; Home Assistant doesn't need to poll.
    _attr_should_poll = False

    def __init__(self, controller: HeaterController, key: str) -> None:
        """Link the entity to its controller and give it a stable unique id.

        ``key`` distinguishes the entities of one heater (e.g. "boost").
        """
        self.controller = controller
        entry = controller.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Electrical Heater",
            model="Virtual thermostat",
        )

    async def async_added_to_hass(self) -> None:
        """Start listening to the controller once the entity exists in HA."""
        await super().async_added_to_hass()
        # async_on_remove makes sure the listener is removed with the entity.
        self.async_on_remove(self.controller.async_add_listener(self.async_write_ha_state))


def remove_unused_entity(
    hass: HomeAssistant, entry: ConfigEntry, platform: Platform, key: str
) -> None:
    """Delete an entity this heater no longer creates.

    Used when optional sensors are removed in the options (e.g. no more
    humidity sensors), so the old entity doesn't linger as "unavailable".
    ``key`` is the same key the entity was created with.
    """
    registry = er.async_get(hass)
    if entity_id := registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}"):
        registry.async_remove(entity_id)
