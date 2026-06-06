# Panasonic Comfort Cloud

This is a custom integration to control Panasonic Comfort Cloud devices in [Home Assistant](https://home-assistant.io). It supports both Panasonic air conditioners/heat pumps and Panasonic Aquarea heat pump systems.

> [!IMPORTANT]
> Before installing this integration, you **must** have **completed** the **2FA** process using the Panasonic Comfort Cloud app, and you **must** select the **SMS** option for 2FA.

<p>
    <img src="https://github.com/sockless-coding/panasonic_cc/raw/master/doc/controls.png" alt="Example controls" style="vertical-align: top;max-width:100%" align="top" />
    <img src="https://github.com/sockless-coding/panasonic_cc/raw/master/doc/sensors.png" alt="Example sensors" style="vertical-align: top;max-width:100%" align="top" />
    <img src="https://github.com/sockless-coding/panasonic_cc/raw/master/doc/diagnostics.png" alt="Example diagnostics" style="vertical-align: top;max-width:100%" align="top" />
</p>

## Features

### Climate Control
- Full climate entity for Panasonic air conditioners and heat pumps
- Full climate entity for Panasonic Aquarea zones
- Water heater entity for Aquarea hot water tanks
- Support for Heat, Cool, Auto, Dry, and Fan modes
- Target temperature control, fan modes, and preset modes

### Swing Control
- Horizontal and vertical swing mode via Select entities
- `set_horizontal_swing_mode` service for automations

### Switches
- **Nanoe** — Air purification (where available)
- **ECONAVI** — Energy-saving mode (where available)
- **AI ECO** — Intelligent eco mode (where available)
- **iAUTO-X** — Intelligent auto mode (where available)
- **Zone controls** — Individual zone on/off (where available)

### Sensors
- **Inside Temperature** — Indoor temperature reading
- **Outside Temperature** — Outdoor temperature (where available)
- **Daily Energy** — Daily energy consumption in kWh (optional)
- **Current Power** — Current power consumption in W (calculated)
- **Last Updated** — Last data update timestamp (diagnostic)
- **Cached Data Age** — Cached data timestamp when offline (diagnostic)
- **Data Mode** — LIVE / CACHED / OFFLINE status (diagnostic)

### Zone Controls
- **Zone Damper Position** — Slider for damper control (0–100%)
- **Zone Mode** — Switch to enable/disable individual zones

### Buttons
- **Fetch latest data** — Manually refresh device data
- **Fetch latest energy data** — Manually refresh energy data
- **Fetch latest app version** — Refresh app version info

## Configuration

The Panasonic Comfort Cloud integration can be configured via the Home Assistant integration interface where it will let you enter your Panasonic ID and Password.

![Setup](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/setup.png)

After initial setup, the following options are available:

![Options](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/configuration.png)

| Option | Description | Default |
|--------|-------------|---------|
| Force outside sensor | Show outside temp sensor even without reading | Disabled |
| Enable daily energy sensors | Create energy and power sensors | Disabled |
| Enable Nanoe for all devices | Force Nanoe switch on all devices | Disabled |
| Use Panasonic preset names | Use "Quiet"/"Powerful" instead of "Eco"/"Boost" | Enabled |
| Device fetch interval | Poll interval for device data (5–300s) | 120s |
| Energy fetch interval | Poll interval for energy data (10–600s) | 300s |

## Support & Development
- **Report issues:** [GitHub Issues](https://github.com/sockless-coding/panasonic_cc/issues)
- ☕ [Buy me a coffee](https://www.buymeacoffee.com/sockless)