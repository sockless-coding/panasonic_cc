import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from . import PANASONIC_DEVICES
from .panasonic import PanasonicApiDevice

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config, async_add_entities):
    entities = []
    for device in hass.data[PANASONIC_DEVICES]:
        entities.append(UpdateAppVersionButton(device, hass))
    async_add_entities(entities, update_before_add=True)
        

class UpdateAppVersionButton(ButtonEntity):

    def __init__(self, device: PanasonicApiDevice, hass):
        self._hass = hass
        self._device = device
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:update'
    
    @property
    def name(self):
        """Return the name of the sensor."""
        return "Fetch latest app version"

    async def async_press(self):
        await self._device.update_app_version()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.id}-update_app_version"
    
    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._device.device_info
