"""Binary sensors for the Aquarea integration."""
from __future__ import annotations

import logging

import aioaquarea

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from ..const import DOMAIN
from .base import AquareaDataEntity
from .coordinator import AquareaDeviceCoordinator
from .const import AQUAREA_COORDINATORS

_LOGGER = logging.getLogger(__name__)


AQUAREA_STATUS_DESCRIPTION = BinarySensorEntityDescription(
    key="status",
    translation_key="status",
    name="Error Status",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)

AQUAREA_DEFROST_DESCRIPTION = BinarySensorEntityDescription(
    key="defrost",
    translation_key="defrost",
    name="Defrost",
    device_class=BinarySensorDeviceClass.RUNNING,
    icon="mdi:snowflake-off",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the Aquarea binary sensors."""
    entities = []
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]
    for coordinator in aquarea_coordinators:
        entities.append(AquareaStatusBinarySensor(coordinator, AQUAREA_STATUS_DESCRIPTION))
        entities.append(AquareaDefrostBinarySensor(coordinator, AQUAREA_DEFROST_DESCRIPTION))
    async_add_entities(entities)


class AquareaStatusBinarySensor(AquareaDataEntity, BinarySensorEntity):
    """Binary sensor that indicates if the Aquarea device is on error."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        self._attr_is_on = self.coordinator.device.is_on_error

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        if self.coordinator.device.current_error is not None:
            return {
                "error_code": self.coordinator.device.current_error.error_code,
                "error_message": self.coordinator.device.current_error.error_message,
            }
        return {}


class AquareaDefrostBinarySensor(AquareaDataEntity, BinarySensorEntity):
    """Binary sensor that indicates if the Aquarea device is in defrost mode."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        is_defrosting = self.coordinator.device.device_mode_status is aioaquarea.DeviceModeStatus.DEFROST
        self._attr_is_on = is_defrosting
        self._attr_icon = "mdi:snowflake-melt" if is_defrosting else "mdi:snowflake-off"
