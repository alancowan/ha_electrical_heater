/**
 * Electrical Heater Card
 *
 * A dashboard card for the Electrical Heater integration. Layout:
 *
 *   ┌──────────────────────────────┐
 *   │          Room name           │  tap: open the heater's details
 *   │   [radiator]   🌡 18.4°C     │  tap radiator: Heat <-> Off
 *   │                💧 65.2%      │
 *   │                ⚡ 824.1W     │
 *   │ ┌──────────────────────────┐ │
 *   │ │  −        25.0        +  │ │  target temperature (hidden for a
 *   │ │                          │ │  heater without temperature sensors)
 *   │ └──────────────────────────┘ │
 *   │ ┌──────────────────────────┐ │
 *   │ │ 🔥 Boost ─────●───────── │ │  boost slider (optional); the label
 *   │ │                          │ │  shows the minutes left while boosting
 *   │ └──────────────────────────┘ │
 *   │ ┌──────────────────────────┐ │
 *   │ │ 📅 Program          [●═] │ │  extra entities (optional), like the
 *   │ │ 🌡 Lounge temp    20.4°C │ │  standard Entities card
 *   │ └──────────────────────────┘ │
 *   └──────────────────────────────┘
 *
 * Works with any climate entity, not only Electrical Heater ones. Rows and
 * bars that need data the entity doesn't have (power, boost, ...) are hidden.
 *
 * Written as a plain Web Component (no build step, no libraries) so the
 * file can be served by the integration as-is.
 *
 * Card options (YAML):
 *   entity:        climate entity (required)
 *   name:          title; defaults to the entity's name
 *   icon:          icon while on, e.g. mdi:fire (default: built-in radiator)
 *   icon_off:      icon while off (default: crossed-out radiator, or `icon` in grey)
 *   show_humidity: show the humidity row        (default true)
 *   show_power:    show the power row           (default true)
 *   show_co2:      show the CO2 row             (default true)
 *   show_action:   show what it's doing ("Idle", "Heating")
 *                  (default: only when there is no power reading)
 *   show_boost:    show the boost slider        (default true)
 *   boost_entity:  number entity for boost; found automatically if omitted
 *   entities:      extra rows; each an entity id or
 *                  { entity, name, icon }. Switches get a toggle, buttons and
 *                  scripts a button, everything else shows its state.
 */

const CARD_VERSION = "0.5.0";
const INTEGRATION = "electrical_heater";

// Material Design Icons (same icons Home Assistant uses), embedded so the
// card looks identical everywhere and doesn't depend on <ha-icon>.
const ICONS = {
  radiator:
    "M7.95,3L6.53,5.19L7.95,7.4H7.94L5.95,10.5L4.22,9.6L5.64,7.39L4.22,5.19L6.22,2.09L7.95,3M13.95,2.89L12.53,5.1L13.95,7.3L13.94,7.31L11.95,10.4L10.22,9.5L11.64,7.3L10.22,5.1L12.22,2L13.95,2.89M20,2.89L18.56,5.1L20,7.3V7.31L18,10.4L16.25,9.5L17.67,7.3L16.25,5.1L18.25,2L20,2.89M2,22V14A2,2 0 0,1 4,12H20A2,2 0 0,1 22,14V22H20V20H4V22H2M6,14A1,1 0 0,0 5,15V17A1,1 0 0,0 6,18A1,1 0 0,0 7,17V15A1,1 0 0,0 6,14M10,14A1,1 0 0,0 9,15V17A1,1 0 0,0 10,18A1,1 0 0,0 11,17V15A1,1 0 0,0 10,14M14,14A1,1 0 0,0 13,15V17A1,1 0 0,0 14,18A1,1 0 0,0 15,17V15A1,1 0 0,0 14,14M18,14A1,1 0 0,0 17,15V17A1,1 0 0,0 18,18A1,1 0 0,0 19,17V15A1,1 0 0,0 18,14Z",
  radiatorOff:
    "M3.28,2L2,3.27L4.77,6.04L5.64,7.39L4.22,9.6L5.95,10.5L7.23,8.5L10.73,12H4A2,2 0 0,0 2,14V22H4V20H18.73L20,21.27V22H22V20.73L22,20.72V20.72L3.28,2M7,17A1,1 0 0,1 6,18A1,1 0 0,1 5,17V15A1,1 0 0,1 6,14A1,1 0 0,1 7,15V17M11,17A1,1 0 0,1 10,18A1,1 0 0,1 9,17V15A1,1 0 0,1 10,14A1,1 0 0,1 11,15V17M15,17A1,1 0 0,1 14,18A1,1 0 0,1 13,17V15C13,14.79 13.08,14.61 13.18,14.45L15,16.27V17M16.25,9.5L17.67,7.3L16.25,5.1L18.25,2L20,2.89L18.56,5.1L20,7.3V7.31L18,10.4L16.25,9.5M22,14V18.18L19,15.18V15A1,1 0 0,0 18,14C17.95,14 17.9,14 17.85,14.03L15.82,12H20C21.11,12 22,12.9 22,14M11.64,7.3L10.22,5.1L12.22,2L13.95,2.89L12.53,5.1L13.95,7.3L13.94,7.31L12.84,9L11.44,7.62L11.64,7.3M7.5,3.69L6.1,2.28L6.22,2.09L7.95,3L7.5,3.69Z",
  thermometer:
    "M15 13V5A3 3 0 0 0 9 5V13A5 5 0 1 0 15 13M12 4A1 1 0 0 1 13 5V8H11V5A1 1 0 0 1 12 4Z",
  humidity:
    "M12,3.25C12,3.25 6,10 6,14C6,17.32 8.69,20 12,20A6,6 0 0,0 18,14C18,10 12,3.25 12,3.25M14.47,9.97L15.53,11.03L9.53,17.03L8.47,15.97M9.75,10A1.25,1.25 0 0,1 11,11.25A1.25,1.25 0 0,1 9.75,12.5A1.25,1.25 0 0,1 8.5,11.25A1.25,1.25 0 0,1 9.75,10M14.25,14.5A1.25,1.25 0 0,1 15.5,15.75A1.25,1.25 0 0,1 14.25,17A1.25,1.25 0 0,1 13,15.75A1.25,1.25 0 0,1 14.25,14.5Z",
  power: "M7,2V13H10V22L17,10H13L17,2H7Z",
  co2: "M5,7A2,2 0 0,0 3,9V15A2,2 0 0,0 5,17H8V15H5V9H8V7H5M11,7A2,2 0 0,0 9,9V15A2,2 0 0,0 11,17H13A2,2 0 0,0 15,15V9A2,2 0 0,0 13,7H11M11,9H13V15H11V9M16,10.5V12H19V13.5H17.5A1.5,1.5 0 0,0 16,15V18H20.5V16.5H17.5V15H19A1.5,1.5 0 0,0 20.5,13.5V12A1.5,1.5 0 0,0 19,10.5H16Z",
  cog: "M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z",
  minus: "M19,13H5V11H19V13Z",
  plus: "M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z",
  fire: "M17.66 11.2C17.43 10.9 17.15 10.64 16.89 10.38C16.22 9.78 15.46 9.35 14.82 8.72C13.33 7.26 13 4.85 13.95 3C13 3.23 12.17 3.75 11.46 4.32C8.87 6.4 7.85 10.07 9.07 13.22C9.11 13.32 9.15 13.42 9.15 13.55C9.15 13.77 9 13.97 8.8 14.05C8.57 14.15 8.33 14.09 8.14 13.93C8.08 13.88 8.04 13.83 8 13.76C6.87 12.33 6.69 10.28 7.45 8.64C5.78 10 4.87 12.3 5 14.47C5.06 14.97 5.12 15.47 5.29 15.97C5.43 16.57 5.7 17.17 6 17.7C7.08 19.43 8.95 20.67 10.96 20.92C13.1 21.19 15.39 20.8 17.03 19.32C18.86 17.66 19.5 15 18.56 12.72L18.43 12.46C18.22 12 17.66 11.2 17.66 11.2M14.5 17.5C14.22 17.74 13.76 18 13.4 18.1C12.28 18.5 11.16 17.94 10.5 17.28C11.69 17 12.4 16.12 12.61 15.23C12.78 14.43 12.46 13.77 12.33 13C12.21 12.26 12.23 11.63 12.5 10.94C12.69 11.32 12.89 11.7 13.13 12C13.9 13 15.11 13.44 15.37 14.8C15.41 14.94 15.43 15.08 15.43 15.23C15.46 16.05 15.1 16.95 14.5 17.5H14.5Z",
};

/** Build an inline <svg> for one of the icons above. */
const svg = (path, cls = "") =>
  `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${path}"></path></svg>`;

// Extra entity rows: domains that get an on/off toggle, and domains that get
// a button (with the service it calls and the button text).
const TOGGLE_DOMAINS = ["switch", "input_boolean", "light", "fan", "automation", "siren", "humidifier"];
const BUTTON_DOMAINS = {
  button: ["press", "Press"],
  input_button: ["press", "Press"],
  script: ["turn_on", "Run"],
  scene: ["turn_on", "Run"],
};

// Colour of the heater icon per HVAC mode (theme variables, HA fallbacks).
const MODE_COLORS = {
  heat: "var(--state-climate-heat-color, #ff8100)",
  cool: "var(--state-climate-cool-color, #2b9af9)",
  heat_cool: "var(--state-climate-heat-cool-color, #8f50ff)",
  auto: "var(--state-climate-auto-color, #008000)",
  dry: "var(--state-climate-dry-color, #efbd07)",
  fan_only: "var(--state-climate-fan_only-color, #00bcd4)",
};
// While actively heating/cooling, the action decides the colour.
const ACTION_COLORS = { heating: MODE_COLORS.heat, cooling: MODE_COLORS.cool, drying: MODE_COLORS.dry, fan: MODE_COLORS.fan_only };

// Wait this long after the last + / − press before sending the new target,
// so several quick presses become one change instead of many.
const TARGET_DEBOUNCE_MS = 800;

// All colours come from Home Assistant theme variables, so the card follows
// your theme (light/dark, custom themes like Frosted Glass). The values after
// the commas are only fallbacks for themes that don't define a variable.
const STYLE = `
  :host { display: block; }

  /* Layout only. The card's frame (background, border, corners, shadow,
     blur) is drawn by Home Assistant's own <ha-card> element from the
     theme, so theme tweaks such as card-mod glass effects apply here too. */
  ha-card {
    display: block;
    height: 100%;
    box-sizing: border-box;
    padding: 12px 12px 10px;
  }

  /* Fallback frame, used only outside Home Assistant (e.g. a preview page)
     where <ha-card> doesn't exist. Mirrors what <ha-card> does itself. */
  ha-card:not(:defined) {
    background: var(--ha-card-background, var(--card-background-color, #fff));
    color: var(--primary-text-color, #212121);
    border-radius: var(--ha-card-border-radius, 12px);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
    box-shadow: var(--ha-card-box-shadow, none);
    backdrop-filter: var(--ha-card-backdrop-filter, none);
    -webkit-backdrop-filter: var(--ha-card-backdrop-filter, none);
    font-family: var(--ha-font-family-body, inherit);
  }
  button {
    font: inherit;
    color: inherit;
    background: none;
    border: 0;
    padding: 0;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  button:focus-visible, input:focus-visible {
    outline: 2px solid var(--primary-color, #03a9f4);
    outline-offset: 2px;
    border-radius: 8px;
  }
  svg { display: block; fill: currentColor; }

  /* ---- Title --------------------------------------------------------- */
  .title {
    display: block;
    width: 100%;
    text-align: center;
    font-size: 1.35rem;
    font-weight: 400;
    line-height: 1.25;
    padding: 0 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ---- Radiator icon + readings -------------------------------------- */
  .body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    align-items: center;
    gap: 8px;
    padding: 6px 4px 12px;
  }
  .heater {
    justify-self: center;
    display: grid;
    place-items: center;
    width: 84px;
    height: 84px;
    border-radius: 50%;
    transition: background-color 0.2s;
  }
  .heater:not(:disabled):hover { background: color-mix(in srgb, currentColor 8%, transparent); }
  /* Boost-only heater (no temperature sensors): the icon is not a button. */
  .heater:disabled { cursor: default; }
  /* .heater-icon is either the built-in <svg> or an <ha-icon> (custom icon). */
  .heater-icon {
    display: block;
    width: 68px;
    height: 68px;
    --mdc-icon-size: 68px;
    transition: opacity 0.3s, filter 0.3s;
  }
  /* --heater-color is set per mode/action (heat = orange, cool = blue, ...). */
  .heater.active { color: var(--heater-color); }
  .heater.active .heater-icon { filter: drop-shadow(0 0 10px color-mix(in srgb, var(--heater-color) 45%, transparent)); }
  .heater.idle { color: var(--heater-color); }
  .heater.idle .heater-icon { opacity: 0.45; }
  .heater.off { color: var(--disabled-text-color, #9e9e9e); }

  .readings {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 4px;
    justify-self: start;
    font-variant-numeric: tabular-nums;
  }
  .readings li {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 1.05rem;
    white-space: nowrap;
  }
  .readings li[hidden] { display: none; }
  .readings svg { width: 18px; height: 18px; flex: none; color: var(--secondary-text-color, #727272); }
  .readings .stale { color: var(--secondary-text-color, #727272); }
  .readings .r-action span { text-transform: lowercase; }

  /* ---- Bottom bars (target, boost) ----------------------------------- */
  .bar {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 48px;
    padding: 0 6px;
    /* Inner panel: the theme's secondary surface and divider colours. */
    border-radius: var(--ha-border-radius-md, 12px);
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.08));
    border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.15));
  }
  .bar + .bar { margin-top: 8px; }
  .step {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    flex: none;
  }
  .step:hover { background: color-mix(in srgb, currentColor 10%, transparent); }
  .step:disabled { opacity: 0.35; cursor: default; background: none; }
  .step svg { width: 22px; height: 22px; }
  .target-value {
    flex: 1;
    text-align: center;
    font-size: 1.1rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    transition: opacity 0.2s;
  }
  .target-value.pending { opacity: 0.6; }
  .target-value.mode-off { color: var(--secondary-text-color, #727272); font-weight: 500; }

  .bar[hidden] { display: none; }
  .boost-icon { width: 20px; height: 20px; margin-left: 6px; flex: none; color: var(--secondary-text-color, #727272); }
  .boost.active .boost-icon { color: var(--state-climate-heat-color, #ff8100); }
  /* The label reads "Boost", or the minutes left ("15 min") while boosting.
     A fixed width stops the slider from jumping when the text changes. */
  .boost-label {
    flex: none;
    min-width: 3.6em;
    font-size: 0.95rem;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .boost.active .boost-label { font-weight: 600; }
  /* The slider takes all remaining width, so it stays usable on phones. */
  .boost input {
    flex: 1;
    min-width: 0;
    margin: 0 8px 0 0;
    accent-color: var(--state-climate-heat-color, #ff8100);
    cursor: pointer;
  }

  /* ---- Extra entities (like the Entities card) ---------------------- */
  .entities {
    margin-top: 8px;
    padding: 4px 12px;
    border-radius: var(--ha-border-radius-md, 12px);
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.08));
    border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.15));
  }
  .entities[hidden] { display: none; }
  .row {
    display: flex;
    align-items: center;
    gap: 16px;
    min-height: 48px;
  }
  .row-icon {
    flex: none;
    width: 24px;
    height: 24px;
    display: grid;
    place-items: center;
    color: var(--state-icon-color, var(--secondary-text-color, #727272));
    --mdc-icon-size: 24px;
  }
  .row-icon svg { width: 24px; height: 24px; }
  .row-name {
    flex: 1;
    min-width: 0;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .row-value {
    flex: none;
    max-width: 50%;
    text-align: right;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-variant-numeric: tabular-nums;
  }
  .row.unavailable .row-name, .row.unavailable .row-value { color: var(--disabled-text-color, #9e9e9e); }
  /* Text button for buttons, scripts and scenes ("Press" / "Run"). */
  .row-action {
    flex: none;
    padding: 6px 10px;
    border-radius: 8px;
    color: var(--primary-color, #03a9f4);
    font-weight: 500;
    text-transform: uppercase;
    font-size: 0.85rem;
    letter-spacing: 0.05em;
  }
  .row-action:hover { background: color-mix(in srgb, currentColor 10%, transparent); }
  /* On/off toggle, coloured with the theme's switch variables. */
  .toggle {
    flex: none;
    position: relative;
    width: 40px;
    height: 22px;
    border-radius: 11px;
    background: color-mix(in srgb, var(--switch-unchecked-track-color, #9e9e9e) 45%, transparent);
    border: 1px solid var(--switch-unchecked-track-color, var(--divider-color, #9e9e9e));
    box-sizing: border-box;
    transition: background-color 0.2s, border-color 0.2s;
  }
  .toggle::after {
    content: "";
    position: absolute;
    top: 3px;
    left: 3px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--switch-unchecked-button-color, #bdbdbd);
    transition: transform 0.2s, background-color 0.2s;
  }
  .toggle[aria-checked="true"] {
    background: color-mix(in srgb, var(--switch-checked-track-color, var(--switch-checked-color, var(--primary-color, #03a9f4))) 55%, transparent);
    border-color: transparent;
  }
  .toggle[aria-checked="true"]::after {
    transform: translateX(18px);
    background: var(--switch-checked-button-color, var(--switch-checked-color, var(--primary-color, #03a9f4)));
  }
  .toggle:disabled { opacity: 0.4; cursor: default; }

  .warning {
    padding: 16px;
    color: var(--error-color, #db4437);
  }

  @media (prefers-reduced-motion: reduce) {
    .heater, .heater-icon, .target-value, .toggle, .toggle::after { transition: none; }
  }
`;

class ElectricalHeaterCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._built = false;
    this._pendingTarget = null; // target shown while + / − presses are pending
    this._debounceTimer = null;
    this._sliderActive = false; // true while the user drags the boost slider
  }

  // ------------------------------------------------------------------
  // Home Assistant card API
  // ------------------------------------------------------------------

  /** Called by Home Assistant with the card's YAML/visual-editor options. */
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Choose a heater (its climate entity).");
    }
    if (!config.entity.startsWith("climate.")) {
      throw new Error("The entity must be a climate entity, e.g. climate.bedroom_heater.");
    }
    const entities = config.entities || [];
    if (!Array.isArray(entities)) {
      throw new Error("`entities` must be a list.");
    }
    this._config = {
      show_humidity: true,
      show_power: true,
      show_co2: true,
      show_boost: true,
      ...config,
      // Accept both "sensor.x" and { entity: "sensor.x", name, icon }.
      entities: entities
        .map((e) => (typeof e === "string" ? { entity: e } : e))
        .filter((e) => e && e.entity),
    };
    this._built = false;
    this._iconKey = null;
    this._render();
  }

  /** Called by Home Assistant every time any state changes. */
  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  /** Rough height in rows of 50px, used by the masonry dashboard layout. */
  getCardSize() {
    if (!this._config) return 3;
    return 3 + (this._config.show_boost ? 1 : 0) + Math.ceil(this._config.entities.length * 0.9);
  }

  /** Default size in the sections (grid) dashboard layout. */
  getGridOptions() {
    return { columns: 6, min_columns: 6, rows: "auto" };
  }

  /** Form shown by the visual card editor. */
  static getConfigForm() {
    const labels = {
      entity: "Heater",
      name: "Name (optional)",
      icon: "Icon (empty = radiator)",
      icon_off: "Icon when off (optional)",
      show_humidity: "Show humidity",
      show_power: "Show power",
      show_co2: "Show CO2",
      show_action: "Show action (idle / heating)",
      show_boost: "Show boost slider",
      entities: "Extra entities (optional)",
    };
    return {
      schema: [
        {
          name: "entity",
          required: true,
          selector: { entity: { filter: { domain: "climate" } } },
        },
        { name: "name", selector: { text: {} } },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "icon", selector: { icon: { placeholder: "mdi:radiator" } } },
            { name: "icon_off", selector: { icon: { placeholder: "mdi:radiator-off" } } },
          ],
        },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "show_humidity", selector: { boolean: {} } },
            { name: "show_power", selector: { boolean: {} } },
            { name: "show_co2", selector: { boolean: {} } },
            { name: "show_action", selector: { boolean: {} } },
            { name: "show_boost", selector: { boolean: {} } },
          ],
        },
        // A list of entity ids. Custom names/icons per row: use YAML.
        { name: "entities", selector: { entity: { multiple: true } } },
      ],
      computeLabel: (schema) => labels[schema.name] || schema.name,
    };
  }

  /** Initial config when the card is added from the card picker. */
  static getStubConfig(hass) {
    const entities = Object.values((hass && hass.entities) || {});
    // Prefer an Electrical Heater; otherwise any climate entity.
    const climates = entities.filter((e) => e.entity_id.startsWith("climate."));
    const heater = climates.find((e) => e.platform === INTEGRATION) || climates[0];
    return { entity: heater ? heater.entity_id : "" };
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------

  /** Build the HTML once, then only update values (keeps slider drags smooth). */
  _render() {
    if (!this._config || !this._hass) return;
    if (!this._built) this._build();
    this._update();
  }

  /** Create the card's HTML structure and wire up the buttons. */
  _build() {
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="content">
          <button class="title" type="button"></button>
          <div class="body">
            <button class="heater" type="button"></button>
            <ul class="readings">
              <li class="r-temp">${svg(ICONS.thermometer)}<span></span></li>
              <li class="r-humidity">${svg(ICONS.humidity)}<span></span></li>
              <li class="r-power">${svg(ICONS.power)}<span></span></li>
              <li class="r-co2">${svg(ICONS.co2)}<span></span></li>
              <li class="r-action">${svg(ICONS.cog)}<span></span></li>
            </ul>
          </div>
          <div class="bar target">
            <button class="step minus" type="button" aria-label="Lower target temperature">${svg(ICONS.minus)}</button>
            <div class="target-value" aria-live="polite"></div>
            <button class="step plus" type="button" aria-label="Raise target temperature">${svg(ICONS.plus)}</button>
          </div>
          <div class="bar boost">
            ${svg(ICONS.fire, "boost-icon")}
            <label class="boost-label" for="boost">Boost</label>
            <input id="boost" type="range" min="0" max="60" step="1" value="0" />
          </div>
          <div class="entities"></div>
        </div>
      </ha-card>
      <div class="warning" hidden></div>
    `;
    const $ = (sel) => this.shadowRoot.querySelector(sel);
    this._el = {
      card: $("ha-card"),
      content: $(".content"),
      warning: $(".warning"),
      title: $(".title"),
      heater: $(".heater"),
      temp: $(".r-temp"),
      humidity: $(".r-humidity"),
      power: $(".r-power"),
      co2: $(".r-co2"),
      action: $(".r-action"),
      entities: $(".entities"),
      minus: $(".minus"),
      plus: $(".plus"),
      target: $(".target-value"),
      boost: $(".boost"),
      slider: $("#boost"),
      boostLabel: $(".boost-label"),
      targetBar: $(".bar.target"),
    };

    this._el.title.addEventListener("click", () => this._moreInfo(this._config.entity));
    this._el.heater.addEventListener("click", () => this._toggleMode());
    this._el.minus.addEventListener("click", () => this._stepTarget(-1));
    this._el.plus.addEventListener("click", () => this._stepTarget(1));

    // Boost slider: show the value live while dragging, send it on release.
    const slider = this._el.slider;
    slider.addEventListener("pointerdown", () => (this._sliderActive = true));
    slider.addEventListener("input", () => {
      this._sliderActive = true;
      this._showBoost(Number(slider.value));
    });
    slider.addEventListener("change", () => {
      this._sliderActive = false;
      this._setBoost(Number(slider.value));
    });

    this._buildEntityRows();
    this._built = true;
  }

  /** Copy the current values from Home Assistant into the card. */
  _update() {
    const el = this._el;
    const stateObj = this._hass.states[this._config.entity];

    // Entity missing (renamed / deleted): show a clear message instead.
    if (!stateObj) {
      el.content.hidden = true;
      el.warning.hidden = false;
      el.warning.textContent = `Entity not found: ${this._config.entity}`;
      return;
    }
    el.content.hidden = false;
    el.warning.hidden = true;

    const a = stateObj.attributes;
    const unit = this._tempUnit();
    const mode = stateObj.state; // "heat" | "off" | "cool" | ... | "unavailable"
    const action = a.hvac_action; // "heating" | "idle" | "off" | ... (optional)

    // Title
    el.title.textContent = this._config.name || a.friendly_name || this._config.entity;

    // Heater icon: colour + shape reflect what the heater is doing.
    //   active: heating/cooling now; idle: on but waiting; off.
    const isOn = mode !== "off" && mode !== "unavailable" && mode !== "unknown";
    const look = ACTION_COLORS[action] ? "active" : isOn || action === "idle" ? "idle" : "off";
    el.heater.className = `heater ${look}`;
    el.heater.style.setProperty("--heater-color", ACTION_COLORS[action] || MODE_COLORS[mode] || MODE_COLORS.heat);
    this._setHeaterIcon(look === "off");

    // Tapping the icon switches between Off and the "on" mode (Heat if the
    // entity has it). An Electrical Heater without temperature sensors has
    // no Heat mode (boost only), so then the icon isn't a button.
    const onMode = this._onMode(a.hvac_modes);
    el.heater.disabled = !onMode;
    if (onMode) {
      el.heater.setAttribute("aria-label", isOn ? "Heater is on. Turn off" : "Heater is off. Turn on");
      el.heater.title = isOn ? "Tap to turn off" : "Tap to turn on";
    } else {
      el.heater.setAttribute("aria-label", look === "off" ? "Heater is off" : "Heater is boosting");
      el.heater.title = "Use Boost to run the heater";
    }

    // Readings. Each row is hidden when switched off in the card options
    // or when the heater has no such sensor.
    this._setReading(el.temp, true, a.current_temperature, 1, unit);
    this._setReading(el.humidity, this._config.show_humidity, a.current_humidity, 1, "%");
    this._setReading(el.power, this._config.show_power, a.power, 1, "W");
    this._setReading(el.co2, this._config.show_co2, a.co2, 0, " ppm");
    // What the climate is doing. By default only when there's no power
    // reading, which already tells whether it's heating.
    const showAction = this._config.show_action ?? !(this._config.show_power && a.power != null);
    el.action.hidden = !showAction || !action;
    if (!el.action.hidden) {
      el.action.querySelector("span").textContent = this._hass.formatEntityAttributeValue
        ? this._hass.formatEntityAttributeValue(stateObj, "hvac_action")
        : action;
    }

    // Target temperature bar. Hidden when the heater has no target
    // temperature (no temperature sensors configured).
    el.targetBar.hidden = a.temperature === undefined || a.temperature === null;
    const target = this._pendingTarget ?? Number(a.temperature);
    el.target.textContent = Number.isFinite(target) ? this._fmt(target, 1) : "–";
    el.target.classList.toggle("pending", this._pendingTarget !== null);
    el.target.classList.toggle("mode-off", mode === "off");
    el.target.setAttribute("aria-label", `Target ${el.target.textContent}${unit}`);
    el.minus.disabled = !Number.isFinite(target) || target <= Number(a.min_temp);
    el.plus.disabled = !Number.isFinite(target) || target >= Number(a.max_temp);

    // Boost bar
    const boostId = this._boostEntityId();
    const boostObj = boostId ? this._hass.states[boostId] : null;
    el.boost.hidden = !this._config.show_boost || !boostObj;
    if (boostObj) {
      const max = Number(boostObj.attributes.max ?? 60);
      el.slider.max = String(max);
      // Room for "23h 55m" when boosts can be longer than an hour.
      el.boostLabel.style.minWidth = max > 60 ? "4.6em" : "";
      el.slider.step = String(boostObj.attributes.step ?? 1);
      if (!this._sliderActive) {
        const minutes = Number(boostObj.state) || 0;
        el.slider.value = String(minutes);
        this._showBoost(minutes);
      }
    }

    this._updateEntityRows();
  }

  /** Create one row per extra entity (once per config). */
  _buildEntityRows() {
    const box = this._el.entities;
    box.replaceChildren();
    this._rows = this._config.entities.map((conf) => {
      const domain = conf.entity.split(".")[0];
      const row = document.createElement("div");
      row.className = "row";

      // HA's own state icon (right icon per device class and state).
      const icon = document.createElement("ha-state-icon");
      icon.className = "row-icon";
      if (conf.icon) icon.icon = conf.icon;

      const name = document.createElement("button");
      name.type = "button";
      name.className = "row-name";
      name.addEventListener("click", () => this._moreInfo(conf.entity));

      let value;
      if (TOGGLE_DOMAINS.includes(domain)) {
        value = document.createElement("button");
        value.type = "button";
        value.className = "toggle";
        value.setAttribute("role", "switch");
        value.addEventListener("click", () => this._toggleEntity(conf.entity));
      } else if (BUTTON_DOMAINS[domain]) {
        const [service, label] = BUTTON_DOMAINS[domain];
        value = document.createElement("button");
        value.type = "button";
        value.className = "row-action";
        value.textContent = label;
        value.addEventListener("click", () =>
          this._hass.callService(domain, service, { entity_id: conf.entity })
        );
      } else {
        value = document.createElement("span");
        value.className = "row-value";
      }

      row.append(icon, name, value);
      box.append(row);
      return { conf, domain, row, icon, name, value };
    });
  }

  /** Refresh the extra entity rows with the current states. */
  _updateEntityRows() {
    this._el.entities.hidden = this._rows.length === 0;
    for (const r of this._rows) {
      const stateObj = this._hass.states[r.conf.entity];
      const unavailable = !stateObj || stateObj.state === "unavailable";
      r.row.classList.toggle("unavailable", unavailable);
      r.name.textContent =
        r.conf.name || (stateObj && stateObj.attributes.friendly_name) || r.conf.entity;

      r.icon.hass = this._hass;
      r.icon.stateObj = stateObj;
      // Coloured like the Entities card: active colour while on.
      const on = stateObj && stateObj.state === "on";
      r.icon.style.color = on
        ? `var(--state-${r.domain}-on-color, var(--state-${r.domain}-active-color, var(--state-active-color, #ffc107)))`
        : "";

      if (r.value.classList.contains("toggle")) {
        r.value.setAttribute("aria-checked", String(!!on));
        r.value.setAttribute("aria-label", r.name.textContent);
        r.value.disabled = unavailable;
      } else if (r.value.classList.contains("row-action")) {
        r.value.disabled = unavailable;
      } else {
        r.value.textContent = this._formatState(stateObj);
      }
    }
  }

  /** An entity's state as Home Assistant shows it, e.g. "20.4 °C" or "Off". */
  _formatState(stateObj) {
    if (!stateObj) return "Not found";
    if (this._hass.formatEntityState) return this._hass.formatEntityState(stateObj);
    const unit = stateObj.attributes.unit_of_measurement;
    return unit ? `${stateObj.state} ${unit}` : stateObj.state;
  }

  /** Toggle an extra entity on/off. */
  _toggleEntity(entityId) {
    const stateObj = this._hass.states[entityId];
    if (!stateObj) return;
    this._hass.callService("homeassistant", stateObj.state === "on" ? "turn_off" : "turn_on", {
      entity_id: entityId,
    });
  }

  /**
   * Show the right heater icon.
   *
   * No `icon` configured: the built-in radiator (crossed out when off).
   * `icon` configured: that icon via <ha-icon>, which knows every mdi: icon
   * and custom icon sets; when off, `icon_off` if set, else the same icon
   * (greyed out by CSS). Only touches the DOM when the icon changes.
   */
  _setHeaterIcon(isOff) {
    const { icon, icon_off: iconOff } = this._config;
    const name = isOff ? iconOff || icon : icon;
    const key = name ? `ha:${name}` : isOff ? "builtin:off" : "builtin:on";
    if (this._iconKey === key) return;
    this._iconKey = key;

    if (name) {
      const haIcon = document.createElement("ha-icon");
      haIcon.className = "heater-icon";
      haIcon.setAttribute("icon", name);
      this._el.heater.replaceChildren(haIcon);
    } else {
      this._el.heater.innerHTML = svg(isOff ? ICONS.radiatorOff : ICONS.radiator, "heater-icon");
    }
  }

  /** Fill in one reading row, or hide it when there's nothing to show. */
  _setReading(li, enabled, value, decimals, unit) {
    const missing = value === undefined || value === null;
    li.hidden = !enabled || missing;
    if (li.hidden) return;
    const num = Number(value);
    li.querySelector("span").textContent = Number.isFinite(num) ? `${this._fmt(num, decimals)}${unit}` : "–";
  }

  /** Show "Boost", or the time left while a boost runs, beside the slider. */
  _showBoost(minutes) {
    this._el.boost.classList.toggle("active", minutes > 0);
    this._el.boostLabel.textContent = minutes > 0 ? this._fmtDuration(minutes) : "Boost";
    this._el.slider.setAttribute("aria-valuetext", minutes > 0 ? `${minutes} minutes` : "Off");
  }

  /** 45 -> "45 min", 60 -> "1h", 90 -> "1h 30m", 1440 -> "24h". */
  _fmtDuration(minutes) {
    if (minutes < 60) return `${minutes} min`;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m ? `${h}h ${m}m` : `${h}h`;
  }

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------

  /** Tap on the heater icon: switch between Off and the "on" mode. */
  _toggleMode() {
    const stateObj = this._hass.states[this._config.entity];
    const onMode = stateObj && this._onMode(stateObj.attributes.hvac_modes);
    if (!onMode) return;
    this._hass.callService("climate", "set_hvac_mode", {
      entity_id: this._config.entity,
      hvac_mode: stateObj.state === "off" ? onMode : "off",
    });
  }

  /**
   * + / − pressed. The new target shows immediately; it is sent to Home
   * Assistant once no button has been pressed for TARGET_DEBOUNCE_MS.
   */
  _stepTarget(direction) {
    const a = this._hass.states[this._config.entity].attributes;
    const step = Number(a.target_temp_step) || (this._tempUnit() === "°F" ? 1 : 0.5);
    const current = this._pendingTarget ?? Number(a.temperature);
    if (!Number.isFinite(current)) return;

    let next = current + direction * step;
    next = Math.round(next / step) * step; // avoid 20.499999 style values
    next = Math.min(Number(a.max_temp), Math.max(Number(a.min_temp), next));
    this._pendingTarget = Number(next.toFixed(2));
    this._update();

    clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => {
      const temperature = this._pendingTarget;
      this._pendingTarget = null;
      this._hass.callService("climate", "set_temperature", {
        entity_id: this._config.entity,
        temperature,
      });
    }, TARGET_DEBOUNCE_MS);
  }

  /** Boost slider released: start (or cancel with 0) the boost. */
  _setBoost(minutes) {
    const boostId = this._boostEntityId();
    if (!boostId) return;
    this._hass.callService("number", "set_value", { entity_id: boostId, value: minutes });
  }

  /** Open Home Assistant's standard details dialog for an entity. */
  _moreInfo(entityId) {
    this.dispatchEvent(
      new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true })
    );
  }

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------

  /**
   * Find the heater's boost slider. Uses `boost_entity` if set, otherwise
   * looks for the number entity of this integration on the same device.
   */
  _boostEntityId() {
    if (this._config.boost_entity) return this._config.boost_entity;
    const entities = this._hass.entities || {};
    const climate = entities[this._config.entity];
    if (!climate || !climate.device_id) return null;
    const match = Object.values(entities).find(
      (e) =>
        e.device_id === climate.device_id &&
        e.platform === INTEGRATION &&
        e.entity_id.startsWith("number.")
    );
    return match ? match.entity_id : null;
  }

  /**
   * The mode the icon switches to: Heat if available, else the first mode
   * that isn't Off (e.g. Auto). Null if the entity can only be Off, or
   * can't be switched off at all.
   */
  _onMode(modes) {
    modes = modes || [];
    if (!modes.includes("off")) return null;
    if (modes.includes("heat")) return "heat";
    return modes.find((m) => m !== "off") || null;
  }

  /** "°C" or "°F", from the Home Assistant unit system. */
  _tempUnit() {
    const units = this._hass.config && this._hass.config.unit_system;
    return (units && units.temperature) || "°C";
  }

  /** Format a number with a fixed number of decimals in the user's locale. */
  _fmt(value, decimals) {
    const lang = (this._hass.locale && this._hass.locale.language) || this._hass.language || undefined;
    try {
      return value.toLocaleString(lang, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    } catch (_err) {
      return value.toFixed(decimals);
    }
  }
}

if (!customElements.get("electrical-heater-card")) {
  customElements.define("electrical-heater-card", ElectricalHeaterCard);
}

// Make the card appear in the dashboard's "Add card" picker.
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "electrical-heater-card")) {
  window.customCards.push({
    type: "electrical-heater-card",
    name: "Electrical Heater Card",
    description: "Thermostat card with readings, + / − target and a boost slider.",
    preview: true,
  });
}

console.info(`%c ELECTRICAL-HEATER-CARD %c v${CARD_VERSION} `, "color:#fff;background:#ff8100;font-weight:600", "");
