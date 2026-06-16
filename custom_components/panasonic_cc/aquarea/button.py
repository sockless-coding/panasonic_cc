"""Aquarea button entities."""
from __future__ import annotations

import logging
from typing import Any

import aioaquarea

from homeassistant.core import HomeAssistant, cached_property
from homeassistant.components.button import ButtonEntity

from ..const import DOMAIN
from .coordinator import AquareaDeviceCoordinator
from .const import AQUAREA_COORDINATORS

_LOGGER = logging.getLogger(__name__)


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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> None:
    """Set up the Aquarea button entities."""
    entities = []
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]

    for coordinator in aquarea_coordinators:
        entities.append(AquareaDefrostButton(coordinator))

    async_add_entities(entities)
