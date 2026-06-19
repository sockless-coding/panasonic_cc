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
- Support for Heat, Cool, Auto, Dry, and Fan modes
- Target temperature control, fan modes, and preset modes

### Water Heater
- **Aquarea Hot Water Tank** — Water heater entity with target temperature control (40–65°C), operation modes (Heat Pump, Off)

### Swing Control
- Horizontal and vertical swing mode via Select entities
- `set_horizontal_swing_mode` service for automations

### Switches
- **Nanoe** — Air purification (where available)
- **ECONAVI** — Energy-saving mode (where available)
- **AI ECO** — Intelligent eco mode (where available)
- **iAUTO-X** — Intelligent auto mode (where available)
- **Zone controls** — Individual zone on/off (where available)
- **Force DHW** — Force domestic hot water mode (Aquarea, where available)
- **Force Heater** — Force heater mode (Aquarea)
- **Holiday Timer** — Enable/disable holiday timer (Aquarea)

### Sensors
- **Inside Temperature** — Indoor temperature reading
- **Outside Temperature** — Outdoor temperature reading (where available)
- **Daily Energy** — Daily energy consumption in kWh (optional)
- **Daily Heating Energy** — Daily heating energy consumption in kWh (optional)
- **Daily Cooling Energy** — Daily cooling energy consumption in kWh (optional)
- **Current Extrapolated Power** — Current power consumption in W (calculated from energy readings)
- **Cooling Extrapolated Power** — Cooling power consumption in W (calculated from energy readings)
- **Heating Extrapolated Power** — Heating power consumption in W (calculated from energy readings)
- **Zone Temperature** — Per-zone temperature reading (where zones are available)
- **Connection Status** — Connection status: connected, degraded, disconnected, authentication_error (diagnostic)
- **Last Updated** — Last data update timestamp (diagnostic)
- **Cached Data Age** — Cached data timestamp when offline (diagnostic)
- **Data Mode** — LIVE / CACHED / OFFLINE status (diagnostic)
- **Outside Temperature** — Outdoor temperature reading (Aquarea)
- **Tank Temperature** — Hot water tank temperature (Aquarea, where available)
- **Direction** — Current operating direction (Aquarea)
- **Pump Status** — On/Off pump status (Aquarea)
- **Accumulated Energy** — Heating, cooling, tank, and total accumulated energy consumption in kWh (Aquarea)

### Zone Controls
- **Zone Damper Position** — Slider for damper control (0–100%)
- **Zone Mode** — Switch to enable/disable individual zones

### Select
- **Quiet Mode** — Quiet mode level: level1, level2, level3, or off (Aquarea)
- **Powerful Time** — Powerful mode duration: on-30m, on-60m, on-90m, or off (Aquarea)

### Binary Sensors
- **Error Status** — Indicates if the Aquarea device is in an error state (Aquarea)
- **Defrost** — Indicates if the Aquarea device is in defrost mode (Aquarea)

### Buttons
- **Fetch latest data** — Manually refresh device data
- **Fetch latest energy data** — Manually refresh energy data
- **Fetch latest app version** — Refresh app version info
- **Request Defrost** — Request the Aquarea device to start the defrost process (Aquarea)

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