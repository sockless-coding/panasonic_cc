from homeassistant.const import EntityCategory
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .panasonic import PanasonicApiDevice
from . import PANASONIC_DEVICES
from .const import SELECT_HORIZONTAL_SWING, SELECT_VERTICAL_SWING
from .pcomfortcloud import constants



def get_horiziontal_swing_description(device: PanasonicApiDevice):
    is_supported = device.support_horizontal_swing
    return SelectEntityDescription(
        key=SELECT_HORIZONTAL_SWING, 
        translation_key=SELECT_HORIZONTAL_SWING,
        entity_category=EntityCategory.CONFIG, 
        entity_registry_enabled_default=is_supported,
        entity_registry_visible_default=is_supported,
        options= [opt.name for opt in constants.AirSwingLR if opt != constants.AirSwingLR.Unavailable])

def get_vertical_swing_description(device: PanasonicApiDevice):
    auto_supported = device._details.features.auto_swing_ud
    return SelectEntityDescription(
        key=SELECT_VERTICAL_SWING, 
        translation_key=SELECT_VERTICAL_SWING,
        entity_category=EntityCategory.CONFIG, 
        options= [opt.name for opt in constants.AirSwingUD if opt != constants.AirSwingUD.Auto or auto_supported])

async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    device_list: list[PanasonicApiDevice] = hass.data[PANASONIC_DEVICES]

    for device in device_list:
        entities.append(PanasonicHorizontalSwingSelectEntity(device, get_horiziontal_swing_description(device)))
        entities.append(PanasonicVerticalSwingSelectEntity(device, get_vertical_swing_description(device)))
        
    async_add_entities(entities)

class PanasonicHorizontalSwingSelectEntity(SelectEntity):
    
    _attr_has_entity_name = True
    
    def __init__(self, device: PanasonicApiDevice, description: SelectEntityDescription):
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"
        self.current_option = device._details.parameters.horizontal_swing_mode.name
        self._attr_icon = "mdi:swap-horizontal"
        self._attr_name = "Horizontal Swing Mode"
        self._attr_device_info = device.device_info
        self._attr_available = device.support_horizontal_swing

    async def async_select_option(self, option: str) -> None:
        await self._device.set_swing_lr_mode(option)

    async def async_update(self):
        await self._device.update()

class PanasonicVerticalSwingSelectEntity(SelectEntity):
    
    _attr_has_entity_name = True
    
    def __init__(self, device: PanasonicApiDevice, description: SelectEntityDescription):
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.id}_{description.key}"
        self.current_option = device._details.parameters.vertical_swing_mode.name
        self._attr_icon = "mdi:swap-vertical"
        self._attr_name = "Vertical Swing Mode"
        self._attr_device_info = device.device_info
        

    async def async_select_option(self, option: str) -> None:
        await self._device.set_swing_mode(option)

    async def async_update(self):
        await self._device.update()