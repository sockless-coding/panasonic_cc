from homeassistant.const import EntityCategory
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .panasonic import PanasonicApiDevice
from . import DOMAIN as PANASONIC_DOMAIN, PANASONIC_DEVICES
from .const import SELECT_HORIZONTAL_SWING



def get_horiziontal_swing_description(device: PanasonicApiDevice):
    return SelectEntityDescription(
        key=SELECT_HORIZONTAL_SWING, 
        translation_key=SELECT_HORIZONTAL_SWING,
        entity_category=EntityCategory.CONFIG, 
        entity_registry_enabled_default=device._details.features.air_swing_lr,
        entity_registry_visible_default=device._details.features.air_swing_lr,
        options= [])

async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    device_list: list[PanasonicApiDevice] = hass.data[PANASONIC_DEVICES]

    for device in device_list:
        entities.append(PanasonicSwingSelectEntity(device, get_horiziontal_swing_description(device)))
        pass
    async_add_entities(entities)

class PanasonicSwingSelectEntity(SelectEntity):
    def __init__(self, device: PanasonicApiDevice, description: SelectEntityDescription):
        self._device = device
        self.entity_description = description
        