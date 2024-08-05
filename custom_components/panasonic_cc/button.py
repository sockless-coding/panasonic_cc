from typing import Callable, Awaitable, Any
from dataclasses import dataclass
import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import DOMAIN, DATA_COORDINATORS, ENERGY_COORDINATORS
from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator
from .base import PanasonicDataEntity

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicButtonEntityDescription(ButtonEntityDescription):
    """Describes a Panasonic Button entity."""
    func: Callable[[PanasonicDeviceCoordinator], Awaitable[Any]] | None = None


APP_VERSION_DESCRIPTION = PanasonicButtonEntityDescription(
    key="update_app_version",
    name="Fetch latest app version",
    icon="mdi:refresh",
    entity_category=EntityCategory.DIAGNOSTIC,
    func = lambda coordinator: coordinator.api_client.update_app_version()
)

UPDATE_DATA_DESCRIPTION = ButtonEntityDescription(
    key="update_data",
    name="Fetch latest data",
    icon="mdi:update",
    entity_category=EntityCategory.DIAGNOSTIC
)
UPDATE_ENERGY_DESCRIPTION = ButtonEntityDescription(
    key="update_energy",
    name="Fetch latest energy data",
    icon="mdi:update",
    entity_category=EntityCategory.DIAGNOSTIC
)

async def async_setup_entry(hass: HomeAssistant, config, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = hass.data[DOMAIN][ENERGY_COORDINATORS]

    for coordinator in data_coordinators:
        entities.append(PanasonicButtonEntity(coordinator, APP_VERSION_DESCRIPTION))
        entities.append(CoordinatorUpdateButtonEntity(coordinator, UPDATE_DATA_DESCRIPTION))
    for coordinator in energy_coordinators:
        entities.append(CoordinatorUpdateButtonEntity(coordinator, UPDATE_ENERGY_DESCRIPTION))
        
    async_add_entities(entities)
        
class PanasonicButtonEntity(PanasonicDataEntity, ButtonEntity):
    """Representation of a Panasonic Button."""
    
    entity_description: PanasonicButtonEntityDescription

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicButtonEntityDescription) -> None:
        self.entity_description = description
        super().__init__(coordinator, description.key)
    

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description.func:
            await self.entity_description.func(self.coordinator)

class CoordinatorUpdateButtonEntity(PanasonicDataEntity, ButtonEntity):
    """Representation of a Coordinator Update Button."""
    
    def __init__(self, coordinator: DataUpdateCoordinator, description: ButtonEntityDescription) -> None:
        self.entity_description = description
        super().__init__(coordinator, description.key)
    

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self.coordinator.async_request_refresh()

