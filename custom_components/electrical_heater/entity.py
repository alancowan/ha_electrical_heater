"""Base class shared by every entity of this integration.

It does two things so the individual entities don't have to:

* puts all entities on one device (named after the heater), and
* refreshes the entity whenever the controller reports a change.
"""

from __future__ import annotations

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
