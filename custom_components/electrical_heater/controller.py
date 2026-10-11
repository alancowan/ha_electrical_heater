"""The brain of the Electrical Heater integration.

One ``HeaterController`` exists per configured heater. It:

* watches the temperature / power / humidity / CO2 sensors and the switch,
* combines the temperature sensors into one value (average of fresh ones),
* decides whether the heater switch should be on or off (thermostat logic
  with hysteresis, boost timer, safety shut-off),
* tells all entities (climate, boost slider, sensors) when something changed.

The entities themselves hold no logic. They only display what the
controller knows and pass user actions (set temperature, start boost, ...)
back to it. This keeps all decisions in one place.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import math
from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CO2_SENSOR,
    CONF_COLD_TOLERANCE,
    CONF_DEFAULT_TARGET,
    CONF_HEATER_SWITCH,
    CONF_HOT_TOLERANCE,
    CONF_HUMIDITY_SENSOR,
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
    DEFAULT_POWER_THRESHOLD,
    DEFAULT_STALE_HOURS,
    DEFAULT_TARGET_TEMP,
    DEFAULT_TEMP_STEP,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class TemperatureReading:
    """Result of combining all temperature sensors into one value.

    ``value`` is None when no sensor delivered a usable reading.
    ``active`` lists the sensors that were used for the average,
    ``stale`` the ones that were ignored because they stopped updating,
    ``unavailable`` the ones that are offline or not a number.
    """

    value: float | None = None
    active: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)


class HeaterController:
    """Holds the state of one heater and runs its thermostat logic."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Read the configuration and prepare the initial state.

        Settings come from ``entry.data`` (initial setup) overlaid with
        ``entry.options`` (changes made later through "Configure").
        """
        self.hass = hass
        self.entry = entry
        conf: dict[str, Any] = {**entry.data, **entry.options}

        # Component entities
        self.switch_entity: str = conf[CONF_HEATER_SWITCH]
        self.temp_sensors: list[str] = list(conf[CONF_TEMP_SENSORS])
        self.power_sensor: str | None = conf.get(CONF_POWER_SENSOR) or None
        self.humidity_sensor: str | None = conf.get(CONF_HUMIDITY_SENSOR) or None
        self.co2_sensor: str | None = conf.get(CONF_CO2_SENSOR) or None

        # Behaviour settings (fall back to defaults if missing)
        self.power_threshold = float(
            conf.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD)
        )
        self.min_temp = float(conf.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
        self.max_temp = float(conf.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))
        self.temp_step = float(conf.get(CONF_TEMP_STEP, DEFAULT_TEMP_STEP))
        self.cold_tolerance = float(
            conf.get(CONF_COLD_TOLERANCE, DEFAULT_COLD_TOLERANCE)
        )
        self.hot_tolerance = float(conf.get(CONF_HOT_TOLERANCE, DEFAULT_HOT_TOLERANCE))
        self.stale_after = timedelta(
            hours=float(conf.get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS))
        )
        self.min_cycle = timedelta(
            minutes=float(conf.get(CONF_MIN_CYCLE_MINUTES, DEFAULT_MIN_CYCLE_MINUTES))
        )
        self.max_boost_minutes = int(
            conf.get(CONF_MAX_BOOST_MINUTES, DEFAULT_MAX_BOOST_MINUTES)
        )

        # Runtime state. hvac_mode / target are overwritten by the climate
        # entity when it restores the values from before a restart.
        self.hvac_mode: HVACMode = HVACMode.OFF
        self.target_temperature: float = self._clamp(
            float(conf.get(CONF_DEFAULT_TARGET, DEFAULT_TARGET_TEMP))
        )
        self.boost_until: datetime | None = None
        self.temperature = TemperatureReading()

        # Internal bookkeeping
        self._listeners: list[CALLBACK_TYPE] = []  # entity refresh callbacks
        self._unsubs: list[CALLBACK_TYPE] = []  # event subscriptions to cancel
        self._boost_timer: CALLBACK_TYPE | None = None
        self._lock = asyncio.Lock()  # prevents two control runs at the same time
        self._restored = False  # True once the climate entity restored its state
        self._started = False  # True once Home Assistant has fully started

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """Subscribe to sensor changes and start the periodic check.

        Called once from ``__init__.py`` after the entities are set up.
        """
        # Every entity we read from; a change in any of them triggers a refresh.
        watched = [self.switch_entity, *self.temp_sensors]
        watched += [
            e
            for e in (self.power_sensor, self.humidity_sensor, self.co2_sensor)
            if e
        ]
        self._unsubs.append(
            async_track_state_change_event(self.hass, watched, self._async_on_state_change)
        )

        # Periodic tick: needed to detect stale sensors (they send no event
        # when they go quiet) and to update the boost countdown on screen.
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._async_on_tick,
                timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            )
        )

        # Wait for Home Assistant to finish starting before switching anything,
        # otherwise sensors may still be "unavailable" and we'd shut the heater off.
        self._unsubs.append(async_at_started(self.hass, self._async_on_started))

    async def async_stop(self) -> None:
        """Cancel every subscription and timer (integration unload/reload)."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_boost_timer()

    @callback
    def async_restore(self, hvac_mode: HVACMode | None, target: float | None) -> None:
        """Receive the values remembered from before a restart.

        Called by the climate entity. Until this has happened the controller
        won't touch the switch, so a restart never toggles the heater by mistake.
        """
        if hvac_mode in (HVACMode.HEAT, HVACMode.OFF):
            self.hvac_mode = hvac_mode
        if target is not None:
            self.target_temperature = self._clamp(target)
        self._restored = True
        self.hass.async_create_task(self.async_control())

    async def _async_on_started(self, _hass: HomeAssistant) -> None:
        """Mark Home Assistant as started and run the first control cycle."""
        self._started = True
        await self.async_control()

    # ------------------------------------------------------------------
    # Listener handling (how entities get told to refresh)
    # ------------------------------------------------------------------

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Register an entity refresh callback. Returns a function to remove it."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @callback
    def _notify(self) -> None:
        """Ask every entity to write its (new) state to Home Assistant."""
        for update_callback in list(self._listeners):
            update_callback()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _async_on_state_change(self, event: Event[EventStateChangedData]) -> None:
        """A watched entity changed: re-run the logic and refresh the entities."""
        await self.async_control()

    async def _async_on_tick(self, _now: datetime) -> None:
        """Periodic check for stale sensors, boost expiry and thermostat logic."""
        if self.boost_until and dt_util.utcnow() >= self.boost_until:
            # The boost ran out (this tick came before the exact timer).
            # End it the same way the timer would, so the heater is switched off.
            self._cancel_boost_timer()
            await self._async_on_boost_end(_now)
            return
        await self.async_control()

    # ------------------------------------------------------------------
    # Reading the sensors
    # ------------------------------------------------------------------

    def _state_as_float(self, entity_id: str | None) -> float | None:
        """Return an entity's state as a number, or None if it isn't usable."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            value = float(state.state)
        except ValueError:
            return None
        return value if math.isfinite(value) else None

    def _is_stale(self, state: State, now: datetime) -> bool:
        """Return True if a sensor has not reported for longer than allowed.

        ``last_reported`` is updated every time the device reports, even if the
        value did not change. Older Home Assistant versions lack it, so we fall
        back to ``last_updated``.
        """
        last_seen: datetime = getattr(state, "last_reported", None) or state.last_updated
        return now - last_seen > self.stale_after

    def read_temperature(self) -> TemperatureReading:
        """Combine all temperature sensors into one value.

        * Sensors that are unavailable / not a number are skipped.
        * Sensors that haven't updated within the stale period are skipped.
        * The remaining (good) sensors are averaged.
        So if one sensor fails, the other one is simply used on its own.
        """
        now = dt_util.utcnow()
        reading = TemperatureReading()
        values: list[float] = []

        for entity_id in self.temp_sensors:
            value = self._state_as_float(entity_id)
            if value is None:
                reading.unavailable.append(entity_id)
                continue
            state = self.hass.states.get(entity_id)
            if state is not None and self._is_stale(state, now):
                reading.stale.append(entity_id)
                continue
            values.append(value)
            reading.active.append(entity_id)

        if values:
            reading.value = round(sum(values) / len(values), 2)
        return reading

    @property
    def humidity(self) -> float | None:
        """Current humidity from the optional humidity sensor."""
        return self._state_as_float(self.humidity_sensor)

    @property
    def co2(self) -> float | None:
        """Current CO2 level from the optional CO2 sensor."""
        return self._state_as_float(self.co2_sensor)

    @property
    def power(self) -> float | None:
        """Current power consumption in watts (None if unknown)."""
        return self._state_as_float(self.power_sensor)

    @property
    def switch_is_on(self) -> bool:
        """True if the heater's switch is currently on."""
        state = self.hass.states.get(self.switch_entity)
        return state is not None and state.state == STATE_ON

    @property
    def is_heating(self) -> bool:
        """True if the heater is actually producing heat.

        Decided by the power sensor: drawing more than the threshold means it is
        on. Without a usable power reading we fall back to the switch state.
        """
        power = self.power
        if power is None:
            return self.switch_is_on
        return power >= self.power_threshold

    # ------------------------------------------------------------------
    # Boost
    # ------------------------------------------------------------------

    @property
    def boost_active(self) -> bool:
        """True while a boost timer is running."""
        return self.boost_until is not None and dt_util.utcnow() < self.boost_until

    @property
    def boost_remaining_minutes(self) -> int:
        """Whole minutes left on the boost (rounded up so 30s shows as 1)."""
        if not self.boost_active or self.boost_until is None:
            return 0
        seconds = (self.boost_until - dt_util.utcnow()).total_seconds()
        return max(0, math.ceil(seconds / 60))

    async def async_set_boost(self, minutes: float) -> None:
        """Start (or change) a boost of ``minutes``; 0 cancels the boost.

        During a boost the heater runs regardless of temperature or mode.
        When it ends the normal thermostat logic takes over again.
        """
        self._cancel_boost_timer()
        minutes = max(0.0, min(float(minutes), float(self.max_boost_minutes)))

        if minutes <= 0:
            self.boost_until = None
            # Force the switch off if the thermostat itself doesn't need heat.
            await self.async_control(force=True)
            return

        self.boost_until = dt_util.utcnow() + timedelta(minutes=minutes)
        # An exact timer so the boost ends on time, not at the next 30 s tick.
        self._boost_timer = async_track_point_in_utc_time(
            self.hass, self._async_on_boost_end, self.boost_until
        )
        await self.async_control(force=True)

    async def _async_on_boost_end(self, _now: datetime) -> None:
        """The boost time is up: return to normal thermostat behaviour."""
        self._boost_timer = None
        self.boost_until = None
        await self.async_control(force=True)

    def _cancel_boost_timer(self) -> None:
        """Remove a scheduled boost-end timer if there is one."""
        if self._boost_timer:
            self._boost_timer()
            self._boost_timer = None

    # ------------------------------------------------------------------
    # User actions coming from the climate entity
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch between HEAT and OFF."""
        self.hvac_mode = hvac_mode
        # force=True: turning the mode off must switch the heater off immediately,
        # ignoring the minimum cycle time.
        await self.async_control(force=True)

    async def async_set_target_temperature(self, temperature: float) -> None:
        """Change the target temperature (clamped to min/max)."""
        self.target_temperature = self._clamp(temperature)
        await self.async_control()

    def _clamp(self, temperature: float) -> float:
        """Keep a temperature within the configured min/max range."""
        return max(self.min_temp, min(self.max_temp, temperature))

    # ------------------------------------------------------------------
    # The thermostat logic
    # ------------------------------------------------------------------

    def _desired_switch_state(self, current_on: bool) -> tuple[bool | None, bool]:
        """Work out what the switch should be.

        Returns ``(desired, forced)``:
        * ``desired`` - True = on, False = off, None = leave it alone.
        * ``forced`` - True if the change must happen now, even if the minimum
          cycle time hasn't passed (boost, safety shut-off).
        """
        # 1. A boost always wins: heater on.
        if self.boost_active:
            return True, True

        # 2. Mode OFF: the heater should be off. (We only enforce this when the
        #    mode or boost changes - see async_control - so you can still use the
        #    switch by hand while the thermostat is off.)
        if self.hvac_mode == HVACMode.OFF:
            return False, True

        # 3. Safety: no usable temperature at all -> turn off.
        temp = self.temperature.value
        if temp is None:
            return False, True

        # 4. Normal thermostat with hysteresis:
        #    - heater on:  keep heating until temp reaches target + hot_tolerance
        #    - heater off: stay off until temp drops to target - cold_tolerance
        #    The gap between the two stops the heater flicking on and off.
        if current_on:
            return temp < self.target_temperature + self.hot_tolerance, False
        return temp <= self.target_temperature - self.cold_tolerance, False

    def _min_cycle_passed(self) -> bool:
        """True if the switch has been in its current state long enough.

        Protects relays and heaters from rapid on/off cycling.
        """
        if self.min_cycle <= timedelta(0):
            return True
        state = self.hass.states.get(self.switch_entity)
        if state is None:
            return True
        return dt_util.utcnow() - state.last_changed >= self.min_cycle

    async def async_control(self, force: bool = False) -> None:
        """Refresh sensor data, switch the heater if needed, refresh entities.

        ``force`` is True when the user changed the mode or the boost. Only
        then is mode OFF actively enforced; otherwise, in mode OFF, the
        controller leaves the switch alone.
        """
        async with self._lock:
            self.temperature = self.read_temperature()

            # Don't switch anything until HA has started and the previous
            # mode/target have been restored.
            if self._started and self._restored:
                await self._async_apply_switch(force)

        self._notify()

    async def _async_apply_switch(self, force: bool) -> None:
        """Turn the switch on/off if the logic says it should change."""
        # Mode OFF and no boost: only act when explicitly forced (user action).
        if self.hvac_mode == HVACMode.OFF and not self.boost_active and not force:
            return

        switch_state = self.hass.states.get(self.switch_entity)
        if switch_state is None or switch_state.state in (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            # Can't control a switch that isn't there.
            return

        current_on = switch_state.state == STATE_ON
        desired, forced_by_logic = self._desired_switch_state(current_on)
        if desired is None or desired == current_on:
            return

        if not (force or forced_by_logic) and not self._min_cycle_passed():
            _LOGGER.debug(
                "%s: waiting for minimum cycle time before switching", self.switch_entity
            )
            return

        _LOGGER.debug(
            "%s: turning %s (temp=%s, target=%s, boost=%s)",
            self.switch_entity,
            "on" if desired else "off",
            self.temperature.value,
            self.target_temperature,
            self.boost_active,
        )
        # homeassistant.turn_on/off works for switch, input_boolean, light, ...
        await self.hass.services.async_call(
            "homeassistant",
            SERVICE_TURN_ON if desired else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: self.switch_entity},
            blocking=True,
        )
