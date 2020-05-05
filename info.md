# Panasonic Comfort Cloud

This is a custom component to allow control of Panasonic Comfort Cloud devices in [HomeAssistant](https://home-assistant.io).

#### Support Development
- :coffee:&nbsp;&nbsp;[Buy me a coffee](https://www.buymeacoffee.com/sockless)


# Features:

* Climate component for Panasonic airconditioners and heatpumps
* Sensors for inside and outside temperature (where available)
* Switch for toggling Nanoe


# Configuration

1. Enable the component by editing the configuration.yaml file (within the config directory as well).
Edit it by adding the following lines:
    ```
    # Example configuration.yaml entry
    panasonic_cc:
        username: !secret panasonic_username
        password: !secret panasonic_password
    ```