# Panasonic Comfort Cloud - HomeAssistant Component

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Integration Usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&style=for-the-badge&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.panasonic_cc.total)](https://analytics.home-assistant.io/)

This is a custom component to allow control of Panasonic Comfort Cloud devices in [HomeAssistant](https://home-assistant.io).

![Example entities](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/entities.png)

## IMPORTANT
Before installing this integration, you **must** have **completed** the **2FA** process using the Panasonic Comfort Cloud app.

#### Support Development
- :coffee:&nbsp;&nbsp;[Buy me a coffee](https://www.buymeacoffee.com/sockless)

## Features

* Climate component for Panasonic airconditioners and heatpumps
* Horizontal swing mode selection
* Sensors for inside and outside temperature (where available)
* Switch for toggling Nanoe
* Daily energy sensor (optional)
* Current Power sensor (Calculated from energy reading)

## Installation

### HACS (recommended)
1. [Install HACS](https://hacs.xyz/docs/setup/download), if you did not already
2. [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sockless-coding&repository=panasonic_cc&category=integration)
3. Press the Download button
4. Restart Home Assistant
5. [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=panasonic_cc)

### Install manually
Clone or copy this repository and copy the folder 'custom_components/panasonic_cc' into '<homeassistant config>/custom_components/panasonic_cc'

## Configuration

Once installed, the Panasonic Comfort Cloud integration can be configured via the Home Assistant integration interface where it will let you enter your Panasonic ID and Password.

![Setup](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/setup_dlg.png)

After inital setup, additional options are available

![Setup](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/options_dlg.png)

## Known issues

- Setting the Horizontal swing mode to LefMid will break the component, you will need to use the Comfort Cloud app to change the mode to something else.

[license-shield]: https://img.shields.io/github/license/sockless-coding/panasonic_cc.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/sockless-coding/panasonic_cc.svg?style=for-the-badge
[releases]: https://github.com/sockless-coding/panasonic_cc/releases
