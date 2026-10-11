# Electrical Heater for Home Assistant

Turns a plain smart switch into a full thermostat, using sensors you already have:

| Component | Required | What it does |
|---|---|---|
| Switch (`switch`, `input_boolean` or `light`) | yes | Turns the heater on and off |
| Temperature sensor(s) | optional, 0 or more | Averaged. Unavailable or stale sensors are skipped, so if one fails the others are used. Without any, the heater only runs with Boost |
| Power sensor | yes | Shows whether the heater is really heating (power above threshold) |
| Humidity sensor(s) | optional, 0 or more | Averaged and shown on the thermostat card. Same stale check as temperature |
| CO2 sensor | optional | Shown as the `co2` attribute |

## What you get

One device with these entities:

- **`climate.<name>`**: thermostat with **Heat / Off** modes and **+ / −** target temperature.
  `hvac_action` is *heating* / *idle* / *off*, based on the power sensor.
- **`number.<name>_boost`**: slider from 0 up to the maximum boost time (60 min by default, up to 24 h). Runs the heater for that long whatever the
  mode or temperature, then counts down. Set it to 0 to cancel.
- **`sensor.<name>_temperature`**: the averaged temperature the thermostat uses (only with temperature sensors).
- **`sensor.<name>_humidity`**: the averaged humidity (only when humidity sensors are configured).
- **`binary_sensor.<name>_heating`**: on while power is above the threshold.
- **`binary_sensor.<name>_temperature_sensor_problem`**: on when any temperature sensor is stale or unavailable
  (only with temperature sensors).
  Use it for alert automations.

## Settings

All of these can be changed later under **Settings → Devices & services → Electrical Heater → Configure**.

| Setting | Default | Meaning |
|---|---|---|
| Min / max temperature | 7 / 30 | Range of the target temperature |
| Temperature step | 0.5 | How much one + / − press changes the target |
| Default target | 10 | Target on first start (afterwards the last value is restored) |
| Cold tolerance | 0.3 | Heater turns **on** at `target − cold tolerance` |
| Hot tolerance | 0.3 | Heater turns **off** at `target + hot tolerance` |
| Power threshold | 10 W | Above this the heater counts as heating |
| Sensor stale after | 3 h (max 24) | A temperature or humidity sensor that hasn't reported for this long is ignored |
| Minimum cycle time | 0 min | Minimum time the switch stays on or off before the thermostat toggles it again (protects relays) |
| Maximum boost time | 60 min (max 24 h) | Upper limit of the boost slider. Above 2 h the slider moves in 5-minute steps |

## Behaviour notes

- **Without temperature sensors** the thermostat only has **Off**: the heater runs only during a boost
  and turns off when the boost ends. The card then hides the temperature row and the − / + bar.
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

## Dashboard card

The integration includes its own card and adds it to your dashboard resources automatically
(Settings → Dashboards → ⋮ → Resources). You don't need a separate HACS download. If your
resources are managed in YAML, add `/electrical_heater/electrical-heater-card.js` there as a
`module` resource yourself.

Edit a dashboard → **Add card** → search **Electrical Heater Card**, then pick your heater.

- **Title:** tap it to open the heater's details.
- **Heater icon:** tap it to switch Heat / Off. It's orange with a glow while heating, faded
  orange when on but warm enough, and grey when off.
- **Readings:** temperature, humidity, power and CO2 (each can be hidden).
- **− / +:** change the target. Quick presses are sent as one change.
- **Boost slider:** runs the heater for the chosen time. The label shows the time left (e.g. `15 min`, `2h 30m`).

Colours, borders and corners come from your Home Assistant theme.

| Option | Default | Meaning |
|---|---|---|
| `entity` | (required) | The heater's climate entity |
| `name` | heater name | Card title |
| `icon` | built-in radiator | Icon while on, e.g. `mdi:fire` |
| `icon_off` | crossed-out radiator, or `icon` in grey | Icon while off |
| `show_humidity` | `true` | Show the humidity row |
| `show_power` | `true` | Show the power row |
| `show_co2` | `true` | Show the CO2 row |
| `show_boost` | `true` | Show the boost slider |
| `boost_entity` | found automatically | Boost number entity, only needed in unusual setups |

```yaml
type: custom:electrical-heater-card
entity: climate.emmalee_bedroom
icon: mdi:heat-wave
```

After an update, refresh the browser (or the app) once so it loads the new card version.

## Development

```bash
pip install pytest-homeassistant-custom-component
pytest
```
