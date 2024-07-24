from abc import abstractmethod


from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator

class PanasonicDataEntity(CoordinatorEntity[PanasonicDeviceCoordinator]):

    _attr_has_entity_name = True

    def __init__(self, coordinator: PanasonicDeviceCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device.id}-{key}"
        self._attr_device_info = self.coordinator.device_info
        self._async_update_attrs()

    
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

class PanasonicEnergyEntity(CoordinatorEntity[PanasonicDeviceEnergyCoordinator]):

    _attr_has_entity_name = True

    def __init__(self, coordinator: PanasonicDeviceEnergyCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.energy.id}-{key}"
        self._attr_device_info = self.coordinator.device_info
        self._async_update_attrs()

    
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""