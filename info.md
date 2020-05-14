# Panasonic Comfort Cloud

This is a custom component to allow control of Panasonic Comfort Cloud devices in [HomeAssistant](https://home-assistant.io).

![Example entities](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/entities.png)

#### Support Development
- :coffee:&nbsp;&nbsp;[Buy me a coffee](https://www.buymeacoffee.com/sockless)


# Features:

* Climate component for Panasonic airconditioners and heatpumps
* Sensors for inside and outside temperature (where available)
* Switch for toggling Nanoe


# Configuration

The Panasonic Comfort Cloud integration can be configured in two ways
1. Via the Home Assistant integration interface where it will let you enter your Panasonic ID and Password.

    ![Setup](https://github.com/sockless-coding/panasonic_cc/raw/master/doc/setup_dlg.png)

2. Enable the component by editing the configuration.yaml file (within the config directory as well).
Edit it by adding the following lines:
    ```
    # Example configuration.yaml entry
    panasonic_cc:
        username: !secret panasonic_username
        password: !secret panasonic_password
    ```
