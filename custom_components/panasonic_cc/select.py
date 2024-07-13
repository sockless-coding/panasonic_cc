from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import DOMAIN, DATA_COORDINATORS, SELECT_HORIZONTAL_SWING, SELECT_VERTICAL_SWING
from .pcomfortcloud import constants
from .pcomfortcloud.panasonicdevice import PanasonicDevice

from .coordinator import PanasonicDeviceCoordinator
from .base import PanasonicDataEntity



def get_horiziontal_swing_description(device: PanasonicDevice):
    is_supported = device.has_horizontal_swing
    return SelectEntityDescription(
        key=SELECT_HORIZONTAL_SWING, 
        translation_key=SELECT_HORIZONTAL_SWING,
        entity_category=EntityCategory.CONFIG, 
        entity_registry_enabled_default=is_supported,
        entity_registry_visible_default=is_supported,
        options= [opt.name for opt in constants.AirSwingLR if opt != constants.AirSwingLR.Unavailable])

def get_vertical_swing_description(device: PanasonicDevice):
    auto_supported = device.features.auto_swing_ud
    return SelectEntityDescription(
        key=SELECT_VERTICAL_SWING, 
        translation_key=SELECT_VERTICAL_SWING,
        entity_category=EntityCategory.CONFIG, 
        options= [opt.name for opt in constants.AirSwingUD if opt != constants.AirSwingUD.Auto or auto_supported])

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    for coordinator in data_coordinators:
        entities.append(PanasonicHorizontalSwingSelectEntity(coordinator, get_horiziontal_swing_description(coordinator.device)))
        entities.append(PanasonicVerticalSwingSelectEntity(coordinator, get_vertical_swing_description(coordinator.device)))
        
    async_add_entities(entities)

class PanasonicHorizontalSwingSelectEntity(PanasonicDataEntity, SelectEntity):
    
    
    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: SelectEntityDescription):
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_icon = "mdi:swap-horizontal"
        self._attr_name = "Horizontal Swing Mode"
        self._attr_available = self.coordinator.device.has_horizontal_swing

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api_client.set_horizontal_swing(option)
        self._attr_current_option = option
        self.async_write_ha_state()

    async def _async_update_attrs(self) -> None:
        self.current_option = self.coordinator.device.parameters.horizontal_swing_mode.name


class PanasonicVerticalSwingSelectEntity(PanasonicDataEntity, SelectEntity):
        
    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: SelectEntityDescription):
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_icon = "mdi:swap-vertical"
        self._attr_name = "Vertical Swing Mode"
    
    async def async_select_option(self, option: str) -> None:
        await self.coordinator.api_client.set_vertical_swing(option)
        self._attr_current_option = option
        self.async_write_ha_state()

    async def _async_update_attrs(self) -> None:
        self.current_option = self.coordinator.device.parameters.vertical_swing_mode.name