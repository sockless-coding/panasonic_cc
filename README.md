# Panasonic Comfort Cloud - HomeAssistant Component

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

This is a custom component to allow control of Panasonic Comfort Cloud devices in [HomeAssistant](https://home-assistant.io).

![Example entities](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/entities.png)

#### Support Development
- :coffee:&nbsp;&nbsp;[Buy me a coffee](https://www.buymeacoffee.com/sockless)


## Features:

* Climate component for Panasonic airconditioners and heatpumps
* Horizontal swing mode selection
* Sensors for inside and outside temperature (where available)
* Switch for toggling Nanoe
* Daily energy sensor (optional)
* Current Power sensor (Calculated from energy reading)


## Installation

### Install using HACS (recomended)
If you do not have HACS installed yet visit https://hacs.xyz for installation instructions.
In HACS go to the Integrations section hit the big + at the bottom right and search for **Panasonic Comfort Cloud**.

### Install manually
Clone or copy this repository and copy the folder 'custom_components/panasonic_cc' into '<homeassistant config>/custom_components/panasonic_cc'

## Configuration

Once installed the Panasonic Comfort Cloud integration can be configured via the Home Assistant integration interface where it will let you enter your Panasonic ID and Password.

![Setup](https://github.com/aceindy/panasonic_cc/raw/master/doc/setup_dlg.png)

After inital setup additional options are available

![Setup](https://github.com/aceindy/panasonic_cc/raw/master/doc/options_dlg.png)

## Known issues

- Setting the Horizontal swing mode to LefMid will break the component and you have to use Comfort Cloud app to change the mode to sometihng else.

[license-shield]: https://img.shields.io/github/license/aceindy/panasonic_cc.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/releaseaceindy/panasonic_cc.svg?style=for-the-badge
[releases]: https://github.com/aceindy/panasonic_cc/releases
