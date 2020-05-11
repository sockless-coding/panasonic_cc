"""Platform for the Panasonic Comfort Cloud."""
from datetime import timedelta
import logging

from async_timeout import timeout

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD)
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from homeassistant.helpers import discovery

from .const import TIMEOUT

from .panasonic import PanasonicApiDevice

_LOGGER = logging.getLogger(__name__)

DOMAIN = "panasonic_cc"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)



PANASONIC_DEVICES = "panasonic_devices"
COMPONENT_TYPES = ["climate", "sensor", "switch"]

def setup(hass, config):
    """Establish connection with Comfort Cloud."""
    import pcomfortcloud
    

    if DOMAIN not in config:
        return True

    if PANASONIC_DEVICES not in hass.data:
        hass.data[PANASONIC_DEVICES] = []

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    api = pcomfortcloud.Session(username, password, verifySsl=False)
    for device in api.get_devices():
        api_device = PanasonicApiDevice(api, device)
        api_device.update()
        hass.data[PANASONIC_DEVICES].append(api_device)

    if hass.data[PANASONIC_DEVICES]:
        for component in COMPONENT_TYPES:
            discovery.load_platform(hass, component, DOMAIN, {}, config)
    return True




