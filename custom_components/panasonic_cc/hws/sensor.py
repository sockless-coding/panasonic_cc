"""HWS (standalone Heat Pump Hot Water tank) sensor entities."""
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from aio_panasonic_comfort_cloud import HwsDevice
from aio_panasonic_comfort_cloud.constants import AquareaOperationStatus

from homeassistant.const import UnitOfTemperature, EntityCategory
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from ..const import DOMAIN
from .base import HwsDataEntity
from .coordinator import HwsDeviceCoordinator
from .const import HWS_COORDINATORS

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HwsSensorEntityDescription(SensorEntityDescription):
    """Describes HWS sensor entity."""
    get_state: Callable[[HwsDevice], Any]


HWS_TANK_TEMPERATURE_DESCRIPTION = HwsSensorEntityDescription(
    key="tank_temperature",
    translation_key="tank_temperature",
    name="Tank Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.parameters.tank_temperature,
)

HWS_HPU_STATUS_DESCRIPTION = HwsSensorEntityDescription(
    key="hpu_operation_status",
    translation_key="hpu_operation_status",
    name="Heat Pump Status",
    icon="mdi:heat-pump",
    device_class=SensorDeviceClass.ENUM,
    options=[status.name for status in AquareaOperationStatus],
    entity_category=EntityCategory.DIAGNOSTIC,
    get_state=lambda device: device.parameters.hpu_operation_status.name,
)

# The meaning of operation_mode hasn't been confirmed against a real device
# (see aio_panasonic_comfort_cloud/models/hws.py) — exposed as a raw
# diagnostic value, disabled by default, so testers can report back what
# they observe.
HWS_OPERATION_MODE_DESCRIPTION = HwsSensorEntityDescription(
    key="operation_mode",
    translation_key="operation_mode",
    name="Operation Mode (raw)",
    icon="mdi:cog",
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    get_state=lambda device: device.parameters.operation_mode,
)

# Connection status sensor options
HWS_CONNECTION_STATUS_OPTIONS = ["connected", "degraded", "disconnected", "authentication_error"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the HWS sensors."""
    entities = []
    hws_coordinators: list[HwsDeviceCoordinator] = hass.data[DOMAIN][HWS_COORDINATORS]

    for coordinator in hws_coordinators:
        entities.append(HwsSensorEntity(coordinator, HWS_TANK_TEMPERATURE_DESCRIPTION))
        entities.append(HwsSensorEntity(coordinator, HWS_HPU_STATUS_DESCRIPTION))
        entities.append(HwsSensorEntity(coordinator, HWS_OPERATION_MODE_DESCRIPTION))
        entities.append(HwsConnectionStatusSensor(coordinator))

    async_add_entities(entities)


class HwsSensorEntity(HwsDataEntity, SensorEntity):
    """Representation of an HWS sensor."""

    entity_description: HwsSensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(self, coordinator: HwsDeviceCoordinator, description: HwsSensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_native_value = self.entity_description.get_state(self.coordinator.device)


class HwsConnectionStatusSensor(HwsDataEntity, SensorEntity):
    """Sensor that reports the connection status and error information for an HWS device."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = HWS_CONNECTION_STATUS_OPTIONS
    _attr_icon = "mdi:network"

    def __init__(self, coordinator: HwsDeviceCoordinator) -> None:
        """Initialize the connection status sensor."""
        super().__init__(coordinator, "connection_status")
        self._attr_unique_id = f"{coordinator.device_id}-connection_status"

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_native_value = self.coordinator.connection_status

        attrs = {}
        attrs["consecutive_failures"] = self.coordinator._consecutive_failures

        if self.coordinator.last_error is not None:
            err = self.coordinator.last_error
            attrs["last_error_title"] = err.title
            attrs["last_error_message"] = err.message
            attrs["last_error_category"] = err.category.name.lower()
            attrs["last_error_recoverable"] = err.is_recoverable
            if err.suggestion:
                attrs["last_error_suggestion"] = err.suggestion

        self._attr_extra_state_attributes = attrs
