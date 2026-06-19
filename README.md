# Panasonic Comfort Cloud - Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Integration Usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&style=for-the-badge&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.panasonic_cc.total)](https://analytics.home-assistant.io/)

This is a custom integration to control Panasonic Comfort Cloud devices in [Home Assistant](https://home-assistant.io). It supports both Panasonic air conditioners/heat pumps and Panasonic Aquarea heat pump systems.

> [!IMPORTANT]
> Before installing this integration, please ensure the following steps have been completed in the Panasonic Comfort Cloud App:
>
> - **Set Up Two-Factor Authentication (2FA):** Complete the entire 2FA setup process.
> - **Select the SMS Option:** It is crucial to choose the SMS option for 2FA. Failing to do so will result in the error "Missing required parameter: code."
>
> For optimal operation, it is also recommended that you use separate accounts for Home Assistant and the Comfort Cloud App.

<p>
    <img src="https://github.com/sockless-coding/panasonic_cc/raw/master/doc/controls.png" alt="Example controls" style="vertical-align: top;max-width:100%" align="top" />
    <img src="https://github.com/sockless-coding/panasonic_cc/raw/master/doc/sensors.png" alt="Example sensors" style="vertical-align: top;max-width:100%" align="top" />
    <img src="https://github.com/sockless-coding/panasonic_cc/raw/master/doc/diagnostics.png" alt="Example diagnostics" style="vertical-align: top;max-width:100%" align="top" />
</p>

---

## Features

### Climate Control
- Full climate entity for Panasonic air conditioners and heat pumps
- Full climate entity for Panasonic Aquarea zones
- Support for Heat, Cool, Auto, Dry, and Fan modes
- Target temperature control
- Fan mode selection
- Preset modes (Quiet, Powerful, +8/15°C heat)

### Water Heater
- **Aquarea Hot Water Tank** — Water heater entity with target temperature control (40–65°C), operation modes (Heat Pump, Off)

### Swing Control
- Horizontal swing mode via Select entity
- Vertical swing mode via Select entity
- Legacy `set_horizontal_swing_mode` service for automations

### Switches
- **Nanoe** — Toggle Nanoe air purification (where available)
- **ECONAVI** — Toggle ECONAVI energy-saving mode (where available)
- **AI ECO** — Toggle AI ECO mode (where available)
- **iAUTO-X** — Toggle iAUTO-X intelligent auto mode (where available)
- **Zone controls** — Toggle individual zone on/off (where available)
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
- **Connection Status** — Current connection status: connected, degraded, disconnected, or authentication_error (diagnostic)
- **Last Updated** — Timestamp of last device data update (diagnostic)
- **Cached Data Age** — Timestamp of cached data when device is offline (diagnostic)
- **Data Mode** — Current data mode: LIVE, CACHED, or OFFLINE (diagnostic)
- **Outside Temperature** — Outdoor temperature reading (Aquarea)
- **Tank Temperature** — Hot water tank temperature (Aquarea, where available)
- **Direction** — Current operating direction (Aquarea)
- **Pump Status** — On/Off pump status (Aquarea)
- **Accumulated Energy** — Heating, cooling, tank, and total accumulated energy consumption in kWh (Aquarea)

### Zone Controls
- **Zone Damper Position** — Slider control for zone damper (0–100%, in steps of 10)
- **Zone Mode** — Switch to enable/disable individual zones

### Select
- **Quiet Mode** — Select quiet mode level: level1, level2, level3, or off (Aquarea)
- **Powerful Time** — Select powerful mode duration: on-30m, on-60m, on-90m, or off (Aquarea)

### Binary Sensors
- **Error Status** — Indicates if the Aquarea device is in an error state, with error code and message attributes (Aquarea)
- **Defrost** — Indicates if the Aquarea device is in defrost mode (Aquarea)

### Buttons
- **Fetch latest data** — Manually refresh device data from the cloud
- **Fetch latest energy data** — Manually refresh energy data from the cloud
- **Fetch latest app version** — Refresh the app version information
- **Request Defrost** — Request the Aquarea device to start the defrost process (Aquarea)

## Installation

### HACS (recommended)
1. [Install HACS](https://hacs.xyz/docs/setup/download), if you haven't already
2. [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sockless-coding&repository=panasonic_cc&category=integration)
3. Press the **Download** button
4. Restart Home Assistant
5. [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=panasonic_cc)

### Manual Installation
1. Clone or download this repository
2. Copy the `custom_components/panasonic_cc` folder into `<homeassistant config>/custom_components/panasonic_cc`
3. Restart Home Assistant
4. Add the integration via **Settings → Devices & Services → Add Integration** and search for "Panasonic Comfort Cloud"

## Configuration

### Initial Setup
Once installed, add the integration via the Home Assistant UI and enter your Panasonic ID and password:

![Setup](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/setup.png)

The initial setup form includes the following options:

| Option | Description | Default |
|--------|-------------|---------|
| **Panasonic ID** | Your Panasonic Comfort Cloud account ID | — |
| **Password** | Your Panasonic Comfort Cloud password | — |
| **Enable daily energy sensors** | Create daily energy and current power sensors | Disabled |
| **Enable Nanoe switch for all devices** | Force the Nanoe switch to appear even if the device doesn't report Nanoe support | Disabled |
| **Use Panasonic preset names** | Use "Quiet" and "Powerful" instead of "Eco" and "Boost" preset names | Enabled |
| **Device fetch interval** | How often to poll device data (5–300 seconds) | 120s |
| **Energy fetch interval** | How often to poll energy data (10–600 seconds) | 300s |

### Options
After initial setup, you can modify the following options from the integration's configuration:

![Options](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/configuration.png)

| Option | Description | Default |
|--------|-------------|---------|
| **Force outside sensor** | Force the outside temperature sensor to appear even if no reading is available | Disabled |
| **Enable daily energy sensors** | Create daily energy and current power sensors | Disabled |
| **Enable Nanoe switch for all devices** | Force the Nanoe switch to appear on all devices | Disabled |
| **Use Panasonic preset names** | Use "Quiet" and "Powerful" instead of "Eco" and "Boost" | Enabled |
| **Device fetch interval** | How often to poll device data (5–300 seconds) | 120s |
| **Energy fetch interval** | How often to poll energy data (10–600 seconds) | 300s |

> [!TIP]
> Some options require a Home Assistant restart to take effect. The integration will indicate which options need a restart.

---

## Services

### Set Horizontal Swing Mode

The `panasonic_cc.set_horizontal_swing_mode` service allows you to set the horizontal swing mode for a climate entity.

**Service data:**

| Field | Description | Required |
|-------|-------------|----------|
| `entity_id` | The climate entity to control | Yes |
| `swing_mode` | The horizontal swing mode to set | Yes |

**Available swing modes:** `Auto`, `Left`, `LeftMid`, `Mid`, `RightMid`, `Right`

**Example automation:**
```yaml
service: panasonic_cc.set_horizontal_swing_mode
data:
  entity_id: climate.living_room_ac
  swing_mode: Auto
```

---

## Troubleshooting

### Authentication Issues
- **"Missing required parameter: code"** — You must use SMS-based 2FA. Other 2FA methods are not supported.
- **Authentication fails repeatedly** — Try resetting your MFA by logging in and out of the Panasonic Comfort Cloud app, then try again.
- **Session expired** — The integration will notify you when authentication expires. Use the reconfigure option from the integration settings to re-authenticate.

### Device Data Issues
- **Cached data** — If your device is offline, the integration will show cached data. Check the "Data Mode" diagnostic sensor to see if data is LIVE, CACHED, or OFFLINE.
- **Stale readings** — Use the "Fetch latest data" button to manually refresh device data.
- **No outside temperature** — Not all devices report outside temperature. Use the "Force outside sensor" option if you want the sensor entity to always appear.

### Energy Sensors
- **Energy data not updating** — Ensure "Enable daily energy sensors" is checked in the integration options. Note that energy data resets daily.
- **Current power seems inaccurate** — Current power is extrapolated from the daily energy reading and may not reflect instantaneous power accurately.

---

## Dependencies

This integration uses the following Python packages:

- [`aio-panasonic-comfort-cloud`](https://github.com/sockless-coding/aio-panasonic-comfort-cloud) — For Panasonic air conditioners and heat pumps
- [`aioaquarea`](https://github.com/cjaliaga/aioaquarea) — For Panasonic Aquarea heat pump systems

---

## Support & Development

- **Report issues:** [GitHub Issues](https://github.com/sockless-coding/panasonic_cc/issues)
- **Contribute:** See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Buy me a coffee:** ☕ [Buy Me a Coffee](https://www.buymeacoffee.com/sockless)

[license-shield]: https://img.shields.io/github/license/sockless-coding/panasonic_cc.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/sockless-coding/panasonic_cc.svg?style=for-the-badge
[releases]: https://github.com/sockless-coding/panasonic_cc/releases
