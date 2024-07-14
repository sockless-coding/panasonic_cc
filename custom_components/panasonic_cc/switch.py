"""Support for Panasonic Nanoe."""
import logging
from typing import Callable
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from .panasonic import PanasonicApiDevice
from .pcomfortcloud import constants
from .pcomfortcloud.panasonicdevice import PanasonicDevice, PanasonicDeviceZone
from .pcomfortcloud.changerequestbuilder import ChangeRequestBuilder
from .pcomfortcloud.apiclient import ApiClient


from . import DOMAIN, PANASONIC_DEVICES
from .const import DATA_COORDINATORS
from .coordinator import PanasonicDeviceCoordinator
from .base import PanasonicDataEntity

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicSwitchEntityDescription(SwitchEntityDescription):
    """Describes Panasonic Switch entity."""

    on_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    off_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    get_state: Callable[[PanasonicDevice], bool]
    is_available: Callable[[PanasonicDevice], bool]

NANOE_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="nanoe",
    translation_key="nanoe",
    name="Nanoe",
    icon="mdi:air-conditioner",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    on_func = lambda builder: builder.set_nanoe_mode(constants.NanoeMode.On),
    off_func= lambda builder: builder.set_nanoe_mode(constants.NanoeMode.Off),
    get_state = lambda device: device.parameters.nanoe_mode == constants.NanoeMode.On,
    is_available = lambda device: device.has_nanoe
)
ECONAVI_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-navi",
    translation_key="eco-navi",
    name="ECONAVI",
    icon="mdi:leaf",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    on_func = lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.On),
    off_func= lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.Off),
    get_state = lambda device: device.parameters.eco_navi_mode == constants.EcoNaviMode.On,
    is_available = lambda device: device.has_eco_navi
)
ECO_FUNCTION_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-function",
    translation_key="eco-function",
    name="AI ECO",
    icon="mdi:leaf",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    on_func = lambda builder: builder.set_eco_function_mode(constants.EcoFunctionMode.On),
    off_func= lambda builder: builder.set_eco_function_mode(constants.EcoFunctionMode.Off),
    get_state = lambda device: device.parameters.eco_function_mode == constants.EcoFunctionMode.On,
    is_available = lambda device: device.has_eco_function
)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    devices = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    for data_coordinator in data_coordinators:
        devices.append(PanasonicSwitchEntity(data_coordinator, NANOE_DESCRIPTION))
        devices.append(PanasonicSwitchEntity(data_coordinator, ECONAVI_DESCRIPTION))
        devices.append(PanasonicSwitchEntity(data_coordinator, ECO_FUNCTION_DESCRIPTION))

    async_add_entities(devices)

class PanasonicSwitchEntityBase(SwitchEntity):
    """Base class for all Panasonic switch entities."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    entity_description: PanasonicSwitchEntityDescription

class PanasonicSwitchEntity(PanasonicDataEntity, PanasonicSwitchEntityBase):
    """Representation of a Panasonic switch."""

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicSwitchEntityDescription):
        """Initialize the Switch."""
        super().__init__(coordinator)
        self.entity_description = description

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = self.entity_description.is_available(self.coordinator.device)
        self._attr_is_on = self.entity_description.get_state(self.coordinator.device)

    async def async_turn_on(self, **kwargs):
        """Turn on the Switch."""
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.on_func(builder)
        await self.coordinator.async_apply_changes(builder)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the Switch."""
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.off_func(builder)
        await self.coordinator.async_apply_changes(builder)
        self._attr_is_on = False
        self.async_write_ha_state()


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