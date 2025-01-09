import logging
from typing import Callable
from dataclasses import dataclass

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)

from aio_panasonic_comfort_cloud import PanasonicDevice, PanasonicDeviceZone, ChangeRequestBuilder

from . import DOMAIN
from .const import DATA_COORDINATORS
from .coordinator import PanasonicDeviceCoordinator
from .base import PanasonicDataEntity

@dataclass(frozen=True, kw_only=True)
class PanasonicNumberEntityDescription(NumberEntityDescription):
    """Describes Panasonic Number entity."""
    get_value: Callable[[PanasonicDevice], int]
    set_value: Callable[[ChangeRequestBuilder, int], ChangeRequestBuilder]

def create_zone_damper_description(zone: PanasonicDeviceZone):
    return PanasonicNumberEntityDescription(
        key = f"zone-{zone.id}-damper",
        translation_key=f"zone-{zone.id}-damper",
        name = f"{zone.name} Damper Position",
        icon="mdi:valve",
        native_unit_of_measurement=PERCENTAGE,
        native_max_value=100,
        native_min_value=0,
        native_step=10,
        mode=NumberMode.SLIDER,
        get_value=lambda device: zone.level,
        set_value=lambda builder, value: builder.set_zone_damper(zone.id, value),
    )

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    devices = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    for data_coordinator in data_coordinators:
        if data_coordinator.device.has_zones:
            for zone in data_coordinator.device.parameters.zones:
                devices.append(PanasonicNumberEntity(
                    data_coordinator,
                    create_zone_damper_description(zone)))

    async_add_entities(devices)

class PanasonicNumberEntity(PanasonicDataEntity, NumberEntity):

    entity_description: PanasonicNumberEntityDescription

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicNumberEntityDescription):
        self.entity_description = description
        super().__init__(coordinator, description.key)
    

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(value)
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.set_value(builder, value)
        await self.coordinator.async_apply_changes(builder)
        self._attr_native_value = value
        self.async_write_ha_state()

    def _async_update_attrs(self) -> None:
        self._attr_native_value = self.entity_description.get_value(self.coordinator.device)