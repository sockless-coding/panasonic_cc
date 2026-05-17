"""Base classes for Panasonic entities."""
from __future__ import annotations

from abc import abstractmethod

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    AquareaDeviceCoordinator,
    PanasonicDeviceCoordinator,
    PanasonicDeviceEnergyCoordinator,
)


class PanasonicDataEntity(CoordinatorEntity[PanasonicDeviceCoordinator]):
    """Base class for Panasonic data entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PanasonicDeviceCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_id}-{key}"
        self._attr_device_info = self.coordinator.device_info

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""


class PanasonicEnergyEntity(CoordinatorEntity[PanasonicDeviceEnergyCoordinator]):
    """Base class for Panasonic energy entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PanasonicDeviceEnergyCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_id}-{key}"
        self._attr_device_info = self.coordinator.device_info

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""


class AquareaDataEntity(CoordinatorEntity[AquareaDeviceCoordinator]):
    """Base class for Aquarea data entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AquareaDeviceCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_id}-{key}"
        self._attr_device_info = self.coordinator.device_info

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
