"""Platform for the Panasonic Comfort Cloud."""
from datetime import timedelta
import logging
from typing import Any, Dict

import asyncio
from async_timeout import timeout

import voluptuous as vol

from homeassistant.core import HomeAssistant
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
   pass

async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the Garo Wallbox component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Establish connection with Comfort Cloud."""
    import pcomfortcloud
    
    conf = entry.data
    if PANASONIC_DEVICES not in hass.data:
        hass.data[PANASONIC_DEVICES] = []

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    api = pcomfortcloud.Session(username, password, verifySsl=False)
    devices = await hass.async_add_executor_job(api.get_devices)
    for device in devices:
        try:
            api_device = PanasonicApiDevice(hass, api, device)
            await api_device.update()
            hass.data[PANASONIC_DEVICES].append(api_device)
        except Exception as e:
            _LOGGER.warning(f"Failed to setup device: {device['name']} ({e})")
    
    if hass.data[PANASONIC_DEVICES]:
        for component in COMPONENT_TYPES:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await asyncio.wait(
        [
            hass.config_entries.async_forward_entry_unload(config_entry, component)
            for component in COMPONENT_TYPES
        ]
    )
    hass.data.pop(PANASONIC_DEVICES)
    return True


