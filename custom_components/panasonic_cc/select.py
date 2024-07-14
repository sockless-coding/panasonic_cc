from typing import Callable
from dataclasses import dataclass

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import DOMAIN, DATA_COORDINATORS, SELECT_HORIZONTAL_SWING, SELECT_VERTICAL_SWING
from .pcomfortcloud import constants
from .pcomfortcloud.panasonicdevice import PanasonicDevice
from .pcomfortcloud.changerequestbuilder import ChangeRequestBuilder

from .coordinator import PanasonicDeviceCoordinator
from .base import PanasonicDataEntity

@dataclass(frozen=True, kw_only=True)
class PanasonicSelectEntityDescription(SelectEntityDescription):
    """Description of a select entity."""
    set_option: Callable[[ChangeRequestBuilder, str], ChangeRequestBuilder]
    get_current_option: Callable[[PanasonicDevice], str]
    is_available: Callable[[PanasonicDevice], bool]
    get_options: Callable[[PanasonicDevice], list[str]] = None


HORIZONTAL_SWING_DESCRIPTION = PanasonicSelectEntityDescription(
    key=SELECT_HORIZONTAL_SWING, 
    translation_key=SELECT_HORIZONTAL_SWING,
    icon="mdi:swap-horizontal",
    name="Horizontal Swing Mode",
    entity_category=EntityCategory.CONFIG, 
    entity_registry_enabled_default=False,
    options= [opt.name for opt in constants.AirSwingLR if opt != constants.AirSwingLR.Unavailable],
    set_option = lambda builder, new_value : builder.set_horizontal_swing(new_value),
    get_current_option = lambda device : device.parameters.horizontal_swing_mode.name,
    is_available = lambda device : device.has_horizontal_swing
)
VERTICAL_SWING_DESCRIPTION = PanasonicSelectEntityDescription(
    key=SELECT_VERTICAL_SWING, 
    translation_key=SELECT_VERTICAL_SWING,
    icon="mdi:swap-vertical",
    name="Vertical Swing Mode",
    entity_category=EntityCategory.CONFIG, 
    entity_registry_enabled_default=False,
    get_options= lambda device: [opt.name for opt in constants.AirSwingUD if opt != constants.AirSwingUD.Auto or device.features.auto_swing_ud],
    set_option = lambda builder, new_value : builder.set_vertical_swing(new_value),
    get_current_option = lambda device : device.parameters.vertical_swing_mode.name,
    is_available = lambda device : True
)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    for coordinator in data_coordinators:
        entities.append(PanasonicSelectEntity(coordinator, HORIZONTAL_SWING_DESCRIPTION))
        entities.append(PanasonicSelectEntity(coordinator, VERTICAL_SWING_DESCRIPTION))
        
    async_add_entities(entities)

class PanasonicSelectEntityBase(SelectEntity):
    """Base class for all select entities."""
    entity_description: PanasonicSelectEntityDescription

class PanasonicSelectEntity(PanasonicDataEntity, PanasonicSelectEntityBase):

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicSelectEntityDescription):
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.get_options is not None:
            self._attr_options = description.get_options(coordinator.device)
    
    async def async_select_option(self, option: str) -> None:
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.set_option(builder, option)
        await self.coordinator.async_apply_changes(builder)
        self._attr_current_option = option
        self.async_write_ha_state()

    async def _async_update_attrs(self) -> None:
        self.current_option = self.entity_description.get_current_option(self.coordinator.device)

