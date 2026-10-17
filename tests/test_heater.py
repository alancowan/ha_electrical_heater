"""Tests for the Electrical Heater integration."""

from datetime import timedelta

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.electrical_heater.const import DOMAIN

SWITCH = "input_boolean.heater"
TEMP1 = "sensor.temp1"
TEMP2 = "sensor.temp2"
POWER = "sensor.power"
HUMIDITY = "sensor.humidity"
HUMIDITY2 = "sensor.humidity2"
CLIMATE = "climate.office_heater"
BOOST = "number.office_heater_boost"

SETTINGS = {
    "min_temp": 7.0,
    "max_temp": 30.0,
    "temp_step": "0.5",
    "default_target_temp": 20.0,
    "cold_tolerance": 0.3,
    "hot_tolerance": 0.3,
    "power_threshold": 10.0,
    "stale_hours": 2.0,
    "min_cycle_minutes": 0.0,
    "max_boost_minutes": 60.0,
}


async def _setup(hass: HomeAssistant, temps=(18.0, 18.0), **settings) -> MockConfigEntry:
    """Create the component entities and a configured heater."""
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "input_boolean", {"input_boolean": {"heater": None}})
    hass.states.async_set(TEMP1, str(temps[0]))
    hass.states.async_set(TEMP2, str(temps[1]))
    hass.states.async_set(POWER, "0")
    hass.states.async_set(HUMIDITY, "45")
    hass.states.async_set(HUMIDITY2, "55")

    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Office heater",
        data={
            "heater_switch": SWITCH,
            "temperature_sensors": [TEMP1, TEMP2],
            "power_sensor": POWER,
            "humidity_sensors": [HUMIDITY, HUMIDITY2],
            "co2_sensor": None,
            **SETTINGS,
            **settings,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _set_mode(hass, mode):
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": mode}, blocking=True
    )
    await hass.async_block_till_done()


async def test_config_flow(hass: HomeAssistant) -> None:
    """The two-step setup creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Office heater", "heater_switch": SWITCH,
         "temperature_sensors": [TEMP1], "power_sensor": POWER},
    )
    assert result["step_id"] == "settings"
    bad = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SETTINGS, "min_temp": 31.0}
    )
    assert bad["errors"] == {"max_temp": "max_below_min"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SETTINGS)
    assert result["type"] == "create_entry"
    assert result["title"] == "Office heater"
    assert result["data"]["humidity_sensors"] == []
    assert result["data"]["co2_sensor"] is None


async def test_entities_and_hysteresis(hass: HomeAssistant) -> None:
    """Heater turns on below target - cold tol, off at target + hot tol."""
    await _setup(hass)
    state = hass.states.get(CLIMATE)
    assert state.state == "off"
    assert state.attributes["current_temperature"] == 18.0
    assert state.attributes["current_humidity"] == 50.0  # average of 45 and 55
    assert state.attributes["hvac_modes"] == ["heat", "off"]
    assert hass.states.get(BOOST).state == "0"

    await _set_mode(hass, "heat")
    assert hass.states.get(SWITCH).state == "on"

    # 20.2 is inside the hysteresis band: stays on
    hass.states.async_set(TEMP1, "20.2"); hass.states.async_set(TEMP2, "20.2")
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "on"

    # 20.3 reaches target + hot tolerance: off
    hass.states.async_set(TEMP1, "20.3"); hass.states.async_set(TEMP2, "20.3")
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"

    # 19.8 is inside the band: stays off; 19.7 turns on
    hass.states.async_set(TEMP1, "19.8"); hass.states.async_set(TEMP2, "19.8")
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"
    hass.states.async_set(TEMP1, "19.7"); hass.states.async_set(TEMP2, "19.7")
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "on"

    # Power sensor drives hvac_action
    hass.states.async_set(POWER, "1500")
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["hvac_action"] == "heating"
    assert hass.states.get("binary_sensor.office_heater_heating").state == "on"

    await _set_mode(hass, "off")
    assert hass.states.get(SWITCH).state == "off"


async def test_average_unavailable_and_stale(hass: HomeAssistant, freezer) -> None:
    """Average of good sensors; unavailable and stale ones are ignored."""
    await _setup(hass, temps=(18.0, 20.0))
    assert hass.states.get(CLIMATE).attributes["current_temperature"] == 19.0

    hass.states.async_set(TEMP2, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["current_temperature"] == 18.0
    assert hass.states.get("binary_sensor.office_heater_temperature_sensor_problem").state == "on"

    hass.states.async_set(TEMP2, "20.0")
    await hass.async_block_till_done()
    # Let 3 hours pass, but keep TEMP1 reporting (same value) -> TEMP2 goes stale
    freezer.tick(timedelta(hours=3))
    hass.states.async_set(TEMP1, "18.0")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(CLIMATE)
    assert state.attributes["current_temperature"] == 18.0
    assert state.attributes["stale_temperature_sensors"] == [TEMP2]

    # Both stale while in heat mode -> safety off
    await _set_mode(hass, "heat")
    assert hass.states.get(SWITCH).state == "on"
    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["current_temperature"] is None
    assert hass.states.get(SWITCH).state == "off"


async def test_boost(hass: HomeAssistant, freezer) -> None:
    """Boost runs the heater in OFF mode and stops when time is up."""
    await _setup(hass, temps=(25.0, 25.0))
    await hass.services.async_call(
        "number", "set_value", {"entity_id": BOOST, "value": 10}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "on"
    assert hass.states.get(BOOST).state == "10"

    freezer.tick(timedelta(minutes=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(BOOST).state == "6"
    assert hass.states.get(SWITCH).state == "on"

    freezer.tick(timedelta(minutes=6, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(BOOST).state == "0"
    assert hass.states.get(SWITCH).state == "off"

    # Cancel with 0
    await hass.services.async_call(
        "number", "set_value", {"entity_id": BOOST, "value": 30}, blocking=True
    )
    assert hass.states.get(SWITCH).state == "on"
    await hass.services.async_call(
        "number", "set_value", {"entity_id": BOOST, "value": 0}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"


async def test_options_flow_removes_humidity(hass: HomeAssistant) -> None:
    """Clearing the humidity sensors in the options removes them."""
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"heater_switch": SWITCH, "temperature_sensors": [TEMP1], "power_sensor": POWER},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**SETTINGS, "max_temp": 25.0}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    state = hass.states.get(CLIMATE)
    assert state.attributes.get("current_humidity") is None
    assert hass.states.get("sensor.office_heater_humidity") is None
    assert state.attributes["max_temp"] == 25.0


async def test_humidity_average_and_stale(hass: HomeAssistant, freezer) -> None:
    """Humidity sensors are averaged and use the same stale check."""
    await _setup(hass)
    assert hass.states.get("sensor.office_heater_humidity").state == "50.0"

    hass.states.async_set(HUMIDITY2, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(CLIMATE).attributes["current_humidity"] == 45.0

    hass.states.async_set(HUMIDITY2, "55")
    await hass.async_block_till_done()
    # 3 hours pass (stale time is 2 h); only HUMIDITY keeps reporting
    freezer.tick(timedelta(hours=3))
    hass.states.async_set(HUMIDITY, "45")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(CLIMATE)
    assert state.attributes["current_humidity"] == 45.0
    assert state.attributes["stale_humidity_sensors"] == [HUMIDITY2]


async def test_migrate_v1_single_humidity(hass: HomeAssistant) -> None:
    """Version 1 entries with one humidity sensor are upgraded to a list."""
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "input_boolean", {"input_boolean": {"heater": None}})
    hass.states.async_set(TEMP1, "18")
    hass.states.async_set(HUMIDITY, "40")
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Office heater",
        data={"heater_switch": SWITCH, "temperature_sensors": [TEMP1],
              "power_sensor": POWER, "humidity_sensor": HUMIDITY,
              "co2_sensor": None, **SETTINGS},
        options={"heater_switch": SWITCH, "temperature_sensors": [TEMP1],
                 "power_sensor": POWER, "humidity_sensor": None,
                 "co2_sensor": None, **SETTINGS},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.data["humidity_sensors"] == [HUMIDITY]
    assert "humidity_sensor" not in entry.data
    # The options had cleared the humidity sensor; that must stay cleared.
    assert entry.options["humidity_sensors"] == []
    assert hass.states.get(CLIMATE).attributes.get("current_humidity") is None


async def test_card_is_served(hass: HomeAssistant, hass_client) -> None:
    """The dashboard card's JavaScript is served by Home Assistant."""
    await async_setup_component(hass, "http", {})
    await _setup(hass)
    client = await hass_client()
    resp = await client.get("/electrical_heater/electrical-heater-card.js")
    assert resp.status == 200
    assert "customElements.define(\"electrical-heater-card\"" in await resp.text()
    # Cached by the browser, so the card still loads when a phone wakes up
    # without network.
    assert "max-age" in resp.headers.get("Cache-Control", "")


async def _resources(hass: HomeAssistant) -> list[dict]:
    """The dashboard resources as stored by Home Assistant."""
    resources = hass.data["lovelace"].resources
    await resources.async_get_info()
    return resources.async_items()


async def test_card_added_as_dashboard_resource(hass: HomeAssistant) -> None:
    """The card is a dashboard resource (loads after the app reconnects)."""
    from unittest.mock import patch

    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "lovelace", {})
    hass.config.components.add("frontend")
    with patch("custom_components.electrical_heater.add_extra_js_url") as add_js:
        entry = await _setup(hass)
    add_js.assert_not_called()  # not loaded on page open as well

    items = await _resources(hass)
    assert len(items) == 1
    assert items[0]["type"] == "module"
    assert items[0]["url"].startswith("/electrical_heater/electrical-heater-card.js?v=")

    # Deleting the last heater removes the resource again.
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert await _resources(hass) == []


async def test_card_resource_updated_to_new_version(hass: HomeAssistant) -> None:
    """An old version's resource is updated instead of added twice."""
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "lovelace", {})
    resources = hass.data["lovelace"].resources
    await resources.async_get_info()
    await resources.async_create_item(
        {"res_type": "module", "url": "/electrical_heater/electrical-heater-card.js?v=0.0.1"}
    )
    await _setup(hass)

    items = await _resources(hass)
    assert len(items) == 1
    assert not items[0]["url"].endswith("v=0.0.1")


async def test_card_yaml_resources_fallback(hass: HomeAssistant) -> None:
    """With resources in YAML (read-only), the card is loaded as extra JS."""
    from unittest.mock import patch

    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "lovelace", {"lovelace": {"resource_mode": "yaml"}})
    hass.config.components.add("frontend")
    with patch("custom_components.electrical_heater.add_extra_js_url") as add_js:
        await _setup(hass)
    add_js.assert_called_once()
    assert add_js.call_args.args[1].startswith("/electrical_heater/electrical-heater-card.js?v=")


async def test_brand_icon_detected(hass: HomeAssistant) -> None:
    """Home Assistant finds the integration's own logo in brand/."""
    from homeassistant.loader import async_get_integration

    integration = await async_get_integration(hass, DOMAIN)
    assert integration.has_branding


async def _setup_boost_only(hass: HomeAssistant, **settings) -> MockConfigEntry:
    """A heater without temperature sensors (boost only)."""
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "input_boolean", {"input_boolean": {"heater": None}})
    hass.states.async_set(POWER, "0")
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="Office heater",
        data={
            "heater_switch": SWITCH,
            "temperature_sensors": [],
            "power_sensor": POWER,
            "humidity_sensors": [],
            "co2_sensor": None,
            **{**SETTINGS, **settings},
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow_without_temperature_sensor(hass: HomeAssistant) -> None:
    """The temperature sensor can be left empty; 24 h boost is allowed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Office heater", "heater_switch": SWITCH, "power_sensor": POWER},
    )
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SETTINGS, "max_boost_minutes": 1440.0}
    )
    assert result["type"] == "create_entry"
    assert result["data"]["temperature_sensors"] == []
    assert result["data"]["max_boost_minutes"] == 1440.0


async def test_settings_form_defaults(hass: HomeAssistant) -> None:
    """New heaters default to a 10 °C target and a 60 min boost limit."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Office heater", "heater_switch": SWITCH, "power_sensor": POWER},
    )
    defaults = {
        str(key): key.default() for key in result["data_schema"].schema if callable(key.default)
    }
    assert defaults["default_target_temp"] == 10.0
    assert defaults["max_boost_minutes"] == 60


async def test_boost_only_heater(hass: HomeAssistant, freezer) -> None:
    """Without temperature sensors only OFF exists and boost runs the heater."""
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    await _setup_boost_only(hass, max_boost_minutes=1440.0)
    state = hass.states.get(CLIMATE)
    assert state.state == "off"
    assert state.attributes["hvac_modes"] == ["off"]
    assert state.attributes.get("temperature") is None
    assert hass.states.get("sensor.office_heater_temperature") is None
    assert hass.states.get("binary_sensor.office_heater_temperature_sensor_problem") is None

    # HEAT is not offered
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate", "set_hvac_mode", {"entity_id": CLIMATE, "hvac_mode": "heat"}, blocking=True
        )

    # Boost slider goes up to 24 h in 5-minute steps
    boost = hass.states.get(BOOST)
    assert boost.attributes["max"] == 1440
    assert boost.attributes["step"] == 5

    await hass.services.async_call(
        "number", "set_value", {"entity_id": BOOST, "value": 120}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "on"

    freezer.tick(timedelta(minutes=120, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"


async def test_options_remove_temperature_sensors(hass: HomeAssistant) -> None:
    """Removing all temperature sensors turns a heating thermostat off."""
    entry = await _setup(hass)
    await _set_mode(hass, "heat")
    assert hass.states.get(SWITCH).state == "on"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"heater_switch": SWITCH, "power_sensor": POWER}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], SETTINGS)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    state = hass.states.get(CLIMATE)
    assert state.state == "off"
    assert state.attributes["hvac_modes"] == ["off"]
    # The heater must not keep running without a thermostat.
    assert hass.states.get(SWITCH).state == "off"
    assert hass.states.get("sensor.office_heater_temperature") is None
    assert hass.states.get("binary_sensor.office_heater_temperature_sensor_problem") is None


async def _flip_by_hand(hass: HomeAssistant, state: str) -> None:
    """Simulate the switch being turned on/off at the device itself."""
    hass.states.async_set(SWITCH, state)
    await hass.async_block_till_done()


async def test_manual_switch_disabled_keeps_old_behaviour(hass: HomeAssistant) -> None:
    """Without manual boost the thermostat still overrules a hand-switched heater."""
    await _setup(hass, temps=(25.0, 25.0))
    await _set_mode(hass, "heat")
    await _flip_by_hand(hass, "on")
    assert hass.states.get(SWITCH).state == "off"  # warm enough: turned off again
    assert hass.states.get(BOOST).state == "0"


async def test_manual_switch_starts_and_cancels_boost(hass: HomeAssistant, freezer) -> None:
    """Switching on by hand starts a boost; switching off cancels it."""
    await _setup(hass, temps=(25.0, 25.0), manual_boost_minutes=30.0)
    await _set_mode(hass, "heat")

    # On by hand: boost of 30 min, heater stays on although it's warm.
    await _flip_by_hand(hass, "on")
    assert hass.states.get(SWITCH).state == "on"
    assert hass.states.get(BOOST).state == "30"

    # Off by hand: boost cancelled, mode off, heater stays off.
    await _flip_by_hand(hass, "off")
    assert hass.states.get(SWITCH).state == "off"
    assert hass.states.get(BOOST).state == "0"
    assert hass.states.get(CLIMATE).state == "off"

    # On by hand again (mode off): boost runs and switches off when it ends.
    await _flip_by_hand(hass, "on")
    assert hass.states.get(BOOST).state == "30"
    freezer.tick(timedelta(minutes=30, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"
    assert hass.states.get(BOOST).state == "0"
    # Our own "off" was not mistaken for a hand switch: mode untouched, no boost.
    assert hass.states.get(CLIMATE).state == "off"


async def test_manual_switch_ignores_own_commands(hass: HomeAssistant) -> None:
    """The thermostat switching the heater doesn't start a boost."""
    await _setup(hass, temps=(18.0, 18.0), manual_boost_minutes=30.0)
    await _set_mode(hass, "heat")
    assert hass.states.get(SWITCH).state == "on"
    assert hass.states.get(BOOST).state == "0"
    hass.states.async_set(TEMP1, "21"); hass.states.async_set(TEMP2, "21")
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"
    assert hass.states.get(CLIMATE).state == "heat"


async def test_manual_boost_longer_than_max_rejected(hass: HomeAssistant) -> None:
    """The hand-switch boost can't exceed the maximum boost time."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Office heater", "heater_switch": SWITCH, "power_sensor": POWER},
    )
    bad = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SETTINGS, "manual_boost_minutes": 90.0}
    )
    assert bad["errors"] == {"manual_boost_minutes": "manual_boost_above_max"}
