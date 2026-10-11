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


async def _setup(hass: HomeAssistant, temps=(18.0, 18.0)) -> MockConfigEntry:
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
