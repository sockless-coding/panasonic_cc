from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable
from dataclasses import dataclass

import aioaquarea

from homeassistant.core import HomeAssistant, cached_property
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, DATA_COORDINATORS, ENERGY_COORDINATORS, AQUAREA_COORDINATORS
from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator, AquareaDeviceCoordinator

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
    func=lambda coordinator: coordinator.api_client.update_app_version(),
)

UPDATE_DATA_DESCRIPTION = ButtonEntityDescription(
    key="update_data",
    translation_key="update_data",
    name="Fetch latest data",
    icon="mdi:update",
    entity_category=EntityCategory.DIAGNOSTIC,
)
UPDATE_ENERGY_DESCRIPTION = ButtonEntityDescription(
    key="update_energy",
    translation_key="update_energy",
    name="Fetch latest energy data",
    icon="mdi:update",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic and Aquarea button entities."""
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = hass.data[DOMAIN][ENERGY_COORDINATORS]
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]

    for coordinator in data_coordinators:
        entities.append(PanasonicButtonEntity(coordinator, APP_VERSION_DESCRIPTION))
        entities.append(CoordinatorUpdateButtonEntity(coordinator, UPDATE_DATA_DESCRIPTION))
    for coordinator in energy_coordinators:
        entities.append(CoordinatorUpdateEnergyButtonEntity(coordinator, UPDATE_ENERGY_DESCRIPTION))

    # Aquarea buttons
    for coordinator in aquarea_coordinators:
        entities.append(AquareaDefrostButton(coordinator))

    async_add_entities(entities)


class PanasonicButtonEntity(ButtonEntity):
    """Representation of a Panasonic Button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__()
        self.entity_description = description # type: ignore[assignment]
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device_id}-{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_key = description.key

    @cached_property
    def available(self) -> bool:
        """Return if the button is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Press the button."""
        desc = self.entity_description # type: ignore[union-attr]
        if isinstance(desc, PanasonicButtonEntityDescription) and desc.func:
            await desc.func(self._coordinator)


class CoordinatorUpdateButtonEntity(ButtonEntity):
    """Representation of a Coordinator Update Button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__()
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device_id}-{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_key = description.key

    @cached_property
    def available(self) -> bool:
        """Return if the button is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.async_request_refresh()


class CoordinatorUpdateEnergyButtonEntity(ButtonEntity):
    """Representation of a Coordinator Update Button for energy entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PanasonicDeviceEnergyCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button entity."""
        super().__init__()
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device_id}-{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_key = description.key

    @cached_property
    def available(self) -> bool:
        """Return if the button is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
# Aquarea buttons
# ---------------------------------------------------------------------------

class AquareaDefrostButton(ButtonEntity):
    """Button that requests the Aquarea device to start the defrost process."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the button."""
        super().__init__()
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.device_id}-request_defrost"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_key = "request_defrost"
        self._attr_icon = "mdi:snowflake-melt"

    @cached_property
    def available(self) -> bool:
        """Return if the button is available."""
        return self._coordinator.last_update_success

    async def async_press(self) -> None:
        """Request to start the defrost process."""
        _LOGGER.debug(
            "Requesting defrost for device %s",
            self._coordinator.device.device_id,
        )
        if self._coordinator.device.device_mode_status is not aioaquarea.DeviceModeStatus.DEFROST:
            await self._coordinator.device.request_defrost()
