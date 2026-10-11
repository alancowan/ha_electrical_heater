"""Constants used throughout the Electrical Heater integration.

Keeping every configuration key and default value in one place means the
config flow, the controller and the entities all agree on naming.
"""

from __future__ import annotations

from homeassistant.const import Platform

# The integration domain. Must match the folder name and manifest.json "domain".
DOMAIN = "electrical_heater"

# Entity platforms this integration creates. Each one maps to a .py file.
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,  # The thermostat itself (heat / off, target temperature)
    Platform.NUMBER,  # The boost slider (0-60 minutes)
    Platform.SENSOR,  # The combined/average temperature
    Platform.BINARY_SENSOR,  # "Heating" (from power) and "Sensor problem"
]

# --- Configuration keys -----------------------------------------------------
# Component entities
CONF_HEATER_SWITCH = "heater_switch"
CONF_TEMP_SENSORS = "temperature_sensors"
CONF_POWER_SENSOR = "power_sensor"
CONF_HUMIDITY_SENSORS = "humidity_sensors"
# Old single-sensor key (config version 1). Only used to migrate old entries.
CONF_HUMIDITY_SENSOR_LEGACY = "humidity_sensor"
CONF_CO2_SENSOR = "co2_sensor"

# Behaviour settings
CONF_POWER_THRESHOLD = "power_threshold"  # Watts above which heater is "on"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TEMP_STEP = "temp_step"
CONF_DEFAULT_TARGET = "default_target_temp"
CONF_COLD_TOLERANCE = "cold_tolerance"  # Hysteresis below target before turning on
CONF_HOT_TOLERANCE = "hot_tolerance"  # Hysteresis above target before turning off
CONF_STALE_HOURS = "stale_hours"  # Hours without updates before a sensor is stale
CONF_MIN_CYCLE_MINUTES = "min_cycle_minutes"  # Minimum time between switch toggles
CONF_MAX_BOOST_MINUTES = "max_boost_minutes"  # Upper limit of the boost slider

# --- Defaults ---------------------------------------------------------------
DEFAULT_NAME = "Electrical Heater"
DEFAULT_POWER_THRESHOLD = 10.0
DEFAULT_MIN_TEMP = 7.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_TEMP_STEP = 0.5
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_COLD_TOLERANCE = 0.3
DEFAULT_HOT_TOLERANCE = 0.3
DEFAULT_STALE_HOURS = 3
DEFAULT_MIN_CYCLE_MINUTES = 0
DEFAULT_MAX_BOOST_MINUTES = 60

# Hard limits enforced by the config flow
MAX_STALE_HOURS = 24
MAX_BOOST_MINUTES = 60

# The dashboard card: file in frontend/ and the URL it is served at.
CARD_FILENAME = "electrical-heater-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"

# How often (seconds) the controller re-checks stale sensors, boost expiry and
# the thermostat logic, even when no sensor has changed.
UPDATE_INTERVAL_SECONDS = 30

# Extra state attribute names exposed on the climate entity
ATTR_CO2 = "co2"
ATTR_BOOST_REMAINING = "boost_remaining_minutes"
ATTR_BOOST_ACTIVE = "boost_active"
ATTR_POWER = "power"
ATTR_ACTIVE_SENSORS = "active_temperature_sensors"
ATTR_STALE_SENSORS = "stale_temperature_sensors"
ATTR_UNAVAILABLE_SENSORS = "unavailable_temperature_sensors"
ATTR_ACTIVE_HUMIDITY_SENSORS = "active_humidity_sensors"
ATTR_STALE_HUMIDITY_SENSORS = "stale_humidity_sensors"
ATTR_UNAVAILABLE_HUMIDITY_SENSORS = "unavailable_humidity_sensors"
