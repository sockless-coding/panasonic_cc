import logging
from typing import Any, Callable
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

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PanasonicNumberEntityDescription(NumberEntityDescription):
    """Describes a Panasonic number entity."""

    get_value: Callable[[PanasonicDevice], int]
    set_value: Callable[[ChangeRequestBuilder, int], ChangeRequestBuilder]


def create_zone_damper_description(zone: PanasonicDeviceZone) -> PanasonicNumberEntityDescription:
    """Create a number entity description for a zone damper."""
    return PanasonicNumberEntityDescription(
        key=f"zone-{zone.id}-damper",
        translation_key=f"zone-{zone.id}-damper",
        name=f"{zone.name} Damper Position",
        icon="mdi:valve",
        native_unit_of_measurement=PERCENTAGE,
        native_max_value=100,
        native_min_value=0,
        native_step=10,
        mode=NumberMode.SLIDER,
        get_value=lambda device, z=zone: z.level,
        set_value=lambda builder, value, z=zone: builder.set_zone_damper(z.id, value),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic number entities."""
    devices = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    for data_coordinator in data_coordinators:
        if data_coordinator.device.has_zones:
            for zone in data_coordinator.device.parameters.zones:
                devices.append(
                    PanasonicNumberEntity(
                        data_coordinator, create_zone_damper_description(zone)
                    )
                )

    async_add_entities(devices)


class PanasonicNumberEntity(PanasonicDataEntity, NumberEntity):
    """Representation of a Panasonic number entity."""

    entity_description: PanasonicNumberEntityDescription

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        int_value = int(value)
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.set_value(builder, int_value)
        await self.coordinator.async_apply_changes(builder)
        self._attr_native_value = int_value

    def _async_update_attrs(self) -> None:
        """Update the attributes of the number entity."""
        self._attr_native_value = self.entity_description.get_value(
            self.coordinator.device
        )
