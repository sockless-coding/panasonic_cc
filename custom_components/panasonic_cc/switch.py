"""Support for Panasonic Nanoe."""
import logging

from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from .panasonic import PanasonicApiDevice
from .pcomfortcloud import constants
from .pcomfortcloud.panasonicdevice import PanasonicDeviceZone

from . import DOMAIN as PANASONIC_DOMAIN, PANASONIC_DEVICES

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    devices = []
    for device in hass.data[PANASONIC_DEVICES]:
        devices.append(PanasonicNanoeSwitch(device))
        if device.support_eco_navi:
            devices.append(PanasonicEcoNaviSwitch(device))
    add_entities(devices)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

async def async_setup_entry(hass, entry, async_add_entities):
    devices = []
    device_list: list[PanasonicApiDevice] = hass.data[PANASONIC_DEVICES]
    for device in device_list:
        devices.append(PanasonicNanoeSwitch(device))
        if device.support_eco_navi:
            devices.append(PanasonicEcoNaviSwitch(device))
        for zone in device.zones:
            devices.append(PanasonicZoneSwitch(device, zone))
    async_add_entities(devices)

class PanasonicNanoeSwitch(ToggleEntity):
    """Representation of a zone."""

    def __init__(self, api_device:PanasonicApiDevice):
        """Initialize the zone."""
        self._api = api_device
        self._attr_entity_category = EntityCategory.CONFIG

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

class PanasonicEcoNaviSwitch(ToggleEntity):
    """Representation of a zone."""

    def __init__(self, api_device:PanasonicApiDevice):
        """Initialize the zone."""
        self._api = api_device
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.id}-eco-navi"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:leaf"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._api.name} Eco Navi"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._api.nanoe_mode == constants.EcoNaviMode.On

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.update()

    async def async_turn_on(self, **kwargs):
        """Turn on nanoe."""
        await self._api.set_eco_navi_mode(constants.EcoNaviMode.On)

    async def async_turn_off(self, **kwargs):
        """Turn off nanoe."""
        await self._api.set_eco_navi_mode(constants.EcoNaviMode.Off)

class PanasonicZoneSwitch(ToggleEntity):
    """Representation of a zone."""

    def __init__(self, api_device:PanasonicApiDevice, zone: PanasonicDeviceZone):
        """Initialize the zone."""
        self._api = api_device
        self._zone = zone
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.id}-zone-{self._zone.id}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:thermostat"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._api.name} {self._zone.name}"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._zone.mode == constants.ZoneMode.On

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.update()

    async def async_turn_on(self, **kwargs):
        """Turn on zone."""
        await self._api.set_zone(self._zone.id, mode=constants.ZoneMode.On)

    async def async_turn_off(self, **kwargs):
        """Turn off zone."""
        await self._api.set_zone(self._zone.id, mode=constants.ZoneMode.Off)