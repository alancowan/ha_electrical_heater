"""UI setup for the Electrical Heater integration.

Two forms are shown both when adding a heater and when pressing
"Configure" on an existing one:

1. **Components**: which switch / sensors make up the heater.
2. **Settings**: temperatures, hysteresis, stale time, boost limit, etc.

The schema-building functions are shared so both flows show the same fields.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CO2_SENSOR,
    CONF_COLD_TOLERANCE,
    CONF_DEFAULT_TARGET,
    CONF_HEATER_SWITCH,
    CONF_HOT_TOLERANCE,
    CONF_HUMIDITY_SENSORS,
    CONF_MAX_BOOST_MINUTES,
    CONF_MAX_TEMP,
    CONF_MIN_CYCLE_MINUTES,
    CONF_MIN_TEMP,
    CONF_POWER_SENSOR,
    CONF_POWER_THRESHOLD,
    CONF_STALE_HOURS,
    CONF_TEMP_SENSORS,
    CONF_TEMP_STEP,
    DEFAULT_COLD_TOLERANCE,
    DEFAULT_HOT_TOLERANCE,
    DEFAULT_MAX_BOOST_MINUTES,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_CYCLE_MINUTES,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_POWER_THRESHOLD,
    DEFAULT_STALE_HOURS,
    DEFAULT_TARGET_TEMP,
    DEFAULT_TEMP_STEP,
    DOMAIN,
    MAX_BOOST_MINUTES,
    MAX_STALE_HOURS,
)

# Optional entities. When the user clears one of these in the options form the
# key is missing from the input, so we store an explicit "empty" value to
# remove it: an empty list for multi-select fields, None for single ones.
OPTIONAL_MULTI_ENTITIES = (CONF_TEMP_SENSORS, CONF_HUMIDITY_SENSORS)
OPTIONAL_SINGLE_ENTITIES = (CONF_CO2_SENSOR,)


def _sensor_selector(device_class: SensorDeviceClass, multiple: bool = False) -> selector.EntitySelector:
    """Entity picker limited to sensors of one device class (temperature, power, ...)."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor", device_class=device_class, multiple=multiple
        )
    )


def _number(minimum: float, maximum: float, step: float, unit: str | None = None) -> selector.NumberSelector:
    """A number input box with limits, step size and an optional unit."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def components_schema(include_name: bool) -> vol.Schema:
    """Form 1: the entities that make up the heater.

    ``include_name`` is True only on first setup (the name can't change later).
    Values are pre-filled afterwards with ``add_suggested_values_to_schema``.
    """
    fields: dict[Any, Any] = {}
    if include_name:
        fields[vol.Required(CONF_NAME, default=DEFAULT_NAME)] = selector.TextSelector()

    fields.update(
        {
            # The switch that powers the heater (switch, input_boolean or light).
            vol.Required(CONF_HEATER_SWITCH): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "input_boolean", "light"])
            ),
            # Zero or more temperature sensors; their average is used.
            # Without any, the heater can only be run with the boost slider.
            vol.Optional(CONF_TEMP_SENSORS): _sensor_selector(
                SensorDeviceClass.TEMPERATURE, multiple=True
            ),
            # Power sensor that tells whether the heater is really heating.
            vol.Required(CONF_POWER_SENSOR): _sensor_selector(SensorDeviceClass.POWER),
            # Optional extras shown on the climate entity.
            # Zero or more humidity sensors; averaged with the same stale check.
            vol.Optional(CONF_HUMIDITY_SENSORS): _sensor_selector(
                SensorDeviceClass.HUMIDITY, multiple=True
            ),
            vol.Optional(CONF_CO2_SENSOR): _sensor_selector(SensorDeviceClass.CO2),
        }
    )
    return vol.Schema(fields)


def settings_schema(current: dict[str, Any]) -> vol.Schema:
    """Form 2: behaviour settings, pre-filled with ``current`` or the defaults."""

    def default(key: str, fallback: Any) -> Any:
        return current.get(key, fallback)

    return vol.Schema(
        {
            vol.Required(CONF_MIN_TEMP, default=default(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)): _number(0, 40, 0.5, "°"),
            vol.Required(CONF_MAX_TEMP, default=default(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)): _number(5, 50, 0.5, "°"),
            vol.Required(CONF_TEMP_STEP, default=str(default(CONF_TEMP_STEP, DEFAULT_TEMP_STEP))): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["0.1", "0.5", "1.0"],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(CONF_DEFAULT_TARGET, default=default(CONF_DEFAULT_TARGET, DEFAULT_TARGET_TEMP)): _number(0, 50, 0.5, "°"),
            vol.Required(CONF_COLD_TOLERANCE, default=default(CONF_COLD_TOLERANCE, DEFAULT_COLD_TOLERANCE)): _number(0, 5, 0.1, "°"),
            vol.Required(CONF_HOT_TOLERANCE, default=default(CONF_HOT_TOLERANCE, DEFAULT_HOT_TOLERANCE)): _number(0, 5, 0.1, "°"),
            vol.Required(CONF_POWER_THRESHOLD, default=default(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD)): _number(0, 10000, 1, "W"),
            vol.Required(CONF_STALE_HOURS, default=default(CONF_STALE_HOURS, DEFAULT_STALE_HOURS)): _number(0.5, MAX_STALE_HOURS, 0.5, "h"),
            vol.Required(CONF_MIN_CYCLE_MINUTES, default=default(CONF_MIN_CYCLE_MINUTES, DEFAULT_MIN_CYCLE_MINUTES)): _number(0, 60, 1, "min"),
            vol.Required(CONF_MAX_BOOST_MINUTES, default=default(CONF_MAX_BOOST_MINUTES, DEFAULT_MAX_BOOST_MINUTES)): _number(5, MAX_BOOST_MINUTES, 5, "min"),
        }
    )


def validate_settings(user_input: dict[str, Any]) -> dict[str, str]:
    """Check that the settings make sense. Returns {field: error_key}."""
    errors: dict[str, str] = {}
    if user_input[CONF_MIN_TEMP] >= user_input[CONF_MAX_TEMP]:
        errors[CONF_MAX_TEMP] = "max_below_min"
    elif not (
        user_input[CONF_MIN_TEMP]
        <= user_input[CONF_DEFAULT_TARGET]
        <= user_input[CONF_MAX_TEMP]
    ):
        errors[CONF_DEFAULT_TARGET] = "target_out_of_range"
    return errors


def normalise_components(user_input: dict[str, Any]) -> dict[str, Any]:
    """Store cleared optional sensors as [] / None so they really get removed."""
    data = dict(user_input)
    for key in OPTIONAL_MULTI_ENTITIES:
        data[key] = list(data.get(key) or [])
    for key in OPTIONAL_SINGLE_ENTITIES:
        data[key] = data.get(key) or None
    return data


class ElectricalHeaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flow shown when adding a new Electrical Heater."""

    # Version 2: humidity changed from one sensor to a list of sensors.
    # Older entries are upgraded by async_migrate_entry in __init__.py.
    VERSION = 2

    def __init__(self) -> None:
        """Hold the answers of step 1 until step 2 is finished."""
        self._components: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: name and component entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Don't allow the same switch to be used by two heaters.
            self._async_abort_entries_match({CONF_HEATER_SWITCH: user_input[CONF_HEATER_SWITCH]})
            self._components = normalise_components(user_input)
            return await self.async_step_settings()

        schema = self.add_suggested_values_to_schema(components_schema(include_name=True), user_input or {})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 2: behaviour settings, then create the entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_settings(user_input)
            if not errors:
                data = {**self._components, **user_input}
                return self.async_create_entry(title=data.pop(CONF_NAME), data=data)

        return self.async_show_form(
            step_id="settings",
            data_schema=settings_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the flow used by the "Configure" button."""
        return ElectricalHeaterOptionsFlow()


class ElectricalHeaterOptionsFlow(OptionsFlow):
    """Flow shown when pressing "Configure" on an existing heater."""

    def __init__(self) -> None:
        """Hold the answers of step 1 until step 2 is finished."""
        self._components: dict[str, Any] = {}

    @property
    def _current(self) -> dict[str, Any]:
        """The settings in use right now (initial data + earlier changes)."""
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: change the component entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._components = normalise_components(user_input)
            return await self.async_step_settings()

        schema = self.add_suggested_values_to_schema(
            components_schema(include_name=False), user_input or self._current
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 2: change the behaviour settings and save."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_settings(user_input)
            if not errors:
                # Saving options triggers a reload (see __init__.py).
                return self.async_create_entry(data={**self._components, **user_input})

        return self.async_show_form(
            step_id="settings",
            data_schema=settings_schema(user_input or self._current),
            errors=errors,
        )
