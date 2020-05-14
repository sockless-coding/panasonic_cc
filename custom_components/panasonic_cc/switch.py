"""Support for Panasonic Nanoe."""
import logging

from homeassistant.helpers.entity import ToggleEntity

from . import DOMAIN as PANASONIC_DOMAIN, PANASONIC_DEVICES

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    devices = []
    for device in hass.data[PANASONIC_DEVICES]:
        devices.append(PanasonicNanoeSwitch(device))
    add_entities(devices)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

async def async_setup_entry(hass, entry, async_add_entities):
    devices = []
    for device in hass.data[PANASONIC_DEVICES]:
        devices.append(PanasonicNanoeSwitch(device))
    async_add_entities(devices)

class PanasonicNanoeSwitch(ToggleEntity):
    """Representation of a zone."""

    def __init__(self, api_device):
        """Initialize the zone."""
        self._api = api_device

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.id}-nanoe"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:air-filter"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._api.name} Nanoe"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._api.nanoe_mode == self._api.constants.NanoeMode.On

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.update()

    async def async_turn_on(self, **kwargs):
        """Turn on nanoe."""
        await self._api.set_nanoe_mode(self._api.constants.NanoeMode.On.name)

    async def async_turn_off(self, **kwargs):
        """Turn off nanoe."""
        await self._api.set_nanoe_mode(self._api.constants.NanoeMode.Off.name)
