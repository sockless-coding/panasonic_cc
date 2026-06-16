"""Base classes for Aquarea entities."""
from __future__ import annotations

from abc import abstractmethod

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AquareaDeviceCoordinator


class AquareaDataEntity(CoordinatorEntity[AquareaDeviceCoordinator]):
    """Base class for Aquarea data entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AquareaDeviceCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_id}-{key}"
        self._attr_device_info = self.coordinator.device_info

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._async_update_attrs()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
