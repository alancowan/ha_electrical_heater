# Electrical Heater for Home Assistant

Turns a plain smart switch into a full thermostat, using sensors you already have:

| Component | Required | What it does |
|---|---|---|
| Switch (`switch`, `input_boolean` or `light`) | yes | Turns the heater on and off |
| Temperature sensor(s) | yes, 1 or more | Averaged. Unavailable or stale sensors are skipped, so if one fails the others are used |
| Power sensor | yes | Shows whether the heater is really heating (power above threshold) |
| Humidity sensor | optional | Shown on the thermostat card |
| CO2 sensor | optional | Shown as the `co2` attribute |

## What you get

One device with these entities:

- **`climate.<name>`**: thermostat with **Heat / Off** modes and **+ / −** target temperature.
  `hvac_action` is *heating* / *idle* / *off*, based on the power sensor.
- **`number.<name>_boost`**: slider from 0 to 60 min. Runs the heater for that long whatever the
  mode or temperature, then counts down. Set it to 0 to cancel.
- **`sensor.<name>_temperature`**: the averaged temperature the thermostat uses.
- **`binary_sensor.<name>_heating`**: on while power is above the threshold.
- **`binary_sensor.<name>_temperature_sensor_problem`**: on when any temperature sensor is stale or unavailable.
  Use it for alert automations.

## Settings

All of these can be changed later under **Settings → Devices & services → Electrical Heater → Configure**.

| Setting | Default | Meaning |
|---|---|---|
| Min / max temperature | 7 / 30 | Range of the target temperature |
| Temperature step | 0.5 | How much one + / − press changes the target |
| Default target | 20 | Target on first start (afterwards the last value is restored) |
| Cold tolerance | 0.3 | Heater turns **on** at `target − cold tolerance` |
| Hot tolerance | 0.3 | Heater turns **off** at `target + hot tolerance` |
| Power threshold | 10 W | Above this the heater counts as heating |
| Sensor stale after | 3 h (max 24) | A temperature sensor that hasn't reported for this long is ignored |
| Minimum cycle time | 0 min | Minimum time the switch stays on or off before the thermostat toggles it again (protects relays) |
| Maximum boost time | 60 min | Upper limit of the boost slider |

## Behaviour notes

- **Safety:** in Heat mode, if *no* temperature sensor is usable the heater is switched off.
- **Off mode:** the switch is turned off when you choose Off. After that the integration leaves
  the switch alone, so you can still use it by hand.
- **Boost** overrides everything, and it is **not** resumed after a Home Assistant restart.
- **Stale detection** uses the time the sensor last *reported*, not the last time its value changed.
  Sensors that only report when the value changes might be marked stale in a very stable room,
  so pick a stale time that suits your sensors.
- The mode and target temperature are restored after a restart.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/alancowan/ha_electrical_heater`, category **Integration**.
2. Install **Electrical Heater** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Electrical Heater**.

Manual install: copy `custom_components/electrical_heater` into your `config/custom_components/` folder.

## Dashboard

You don't need a custom card. The built-in thermostat card has the + / − buttons, and a
tile card shows the boost slider. Stack them together:

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.office_heater
  - type: tile
    entity: number.office_heater_boost
    name: Boost
    features:
      - type: numeric-input
        style: slider
```

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```
