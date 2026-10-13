"""HWS (standalone Heat Pump Hot Water tank) sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from aio_panasonic_comfort_cloud import HwsDevice
from aio_panasonic_comfort_cloud.constants import HwsOperationStatus
from aio_panasonic_comfort_cloud.models.hws import HwsConsumption

from homeassistant.const import UnitOfTemperature, EntityCategory, UnitOfEnergy
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.restore_state import RestoreEntity

from ..const import DOMAIN
from .base import HwsDataEntity, HwsEnergyEntity
from .coordinator import HwsDeviceCoordinator, HwsConsumptionCoordinator
from .const import HWS_COORDINATORS, HWS_ENERGY_COORDINATORS

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

HWS_OUTSIDE_TEMPERATURE_DESCRIPTION = HwsSensorEntityDescription(
    key="outside_temperature",
    translation_key="outside_temperature",
    name="Outside Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.parameters.outdoor_temperature,
    # is_available=lambda device: device.parameters.outdoor_temperature is not None,
)

HWS_BOOST_MODE_STATUS_DESCRIPTION = HwsSensorEntityDescription(
    key="boost_mode_status",
    translation_key="boost_mode_status",
    name="Boost Mode Status",
    icon="mdi:arrow-up-circle",
    # device_class=SensorDeviceClass.ENUM,
    # options=[status.name for status in HwsOperationStatus],
    entity_category=EntityCategory.DIAGNOSTIC,
    get_state=lambda device: device.parameters.boost_mode.name,
)

HWS_HPU_STATUS_DESCRIPTION = HwsSensorEntityDescription(
    key="hpu_operation_status",
    translation_key="hpu_operation_status",
    name="Heat Pump Status",
    icon="mdi:heat-pump",
    device_class=SensorDeviceClass.ENUM,
    options=[status.name for status in HwsOperationStatus],
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
    get_state=lambda device: device.parameters.operation_mode.name,
)

# Connection status sensor options
HWS_CONNECTION_STATUS_OPTIONS = [
    "connected",
    "degraded",
    "disconnected",
    "authentication_error",
]


# Energy consumption sensor descriptions for Aquarea, backed by AquareaConsumptionCoordinator
@dataclass(frozen=True, kw_only=True)
class HwsEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Aquarea energy sensor entity."""

    get_state: Callable[[HwsConsumption], Any]
    exists_fn: Callable[[HwsDeviceCoordinator], bool] = lambda _: True


HWS_ENERGY_SENSORS = [
    HwsEnergySensorEntityDescription(
        key="tank_accumulated_energy_consumption",
        translation_key="tank_accumulated_energy_consumption",
        name="Tank Accumulated Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        get_state=lambda entry: entry.tank_consumption,
        # exists_fn=lambda coordinator: coordinator.device.parameters.has_tank,
    )
]
HWS_COST_SENSORS = [
    HwsEnergySensorEntityDescription(
        key="tank_cost_today",
        translation_key="tank_cost_today",
        name="Tank Cost Today",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_state=lambda entry: entry.tank_cost,
        # exists_fn=lambda coordinator: coordinator.device.parameters.has_tank,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up the HWS sensors."""

    entities = []
    hws_coordinators: list[HwsDeviceCoordinator] = hass.data[DOMAIN][HWS_COORDINATORS]
    energy_coordinators: list[HwsConsumptionCoordinator] = hass.data[DOMAIN].get(
        HWS_ENERGY_COORDINATORS, []
    )

    for coordinator in hws_coordinators:
        entities.append(
            HwsSensorEntity(coordinator, HWS_OUTSIDE_TEMPERATURE_DESCRIPTION)
        )
        entities.append(HwsSensorEntity(coordinator, HWS_TANK_TEMPERATURE_DESCRIPTION))
        entities.append(HwsSensorEntity(coordinator, HWS_HPU_STATUS_DESCRIPTION))
        entities.append(HwsSensorEntity(coordinator, HWS_OPERATION_MODE_DESCRIPTION))
        entities.append(HwsSensorEntity(coordinator, HWS_BOOST_MODE_STATUS_DESCRIPTION))
        entities.append(HwsConnectionStatusSensor(coordinator))

    hws_by_id = {
        coordinator._device_info.id: coordinator for coordinator in hws_coordinators
    }
    for energy_coordinator in energy_coordinators:
        device_coordinator = hws_by_id.get(
            energy_coordinator._device_info.id, 0
        )  # FIXME?
        if device_coordinator is None:
            continue
        for desc in HWS_ENERGY_SENSORS:
            if desc.exists_fn(device_coordinator):
                entities.append(HwsEnergySensorEntity(energy_coordinator, desc))
        for desc in HWS_COST_SENSORS:
            if desc.exists_fn(device_coordinator):
                entities.append(HwsEnergySensorEntity(energy_coordinator, desc))

    async_add_entities(entities)


class HwsSensorEntity(HwsDataEntity, SensorEntity):
    """Representation of an HWS sensor."""

    entity_description: HwsSensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self, coordinator: HwsDeviceCoordinator, description: HwsSensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_native_value = self.entity_description.get_state(
            self.coordinator.device
        )


class HwsEnergySensorEntity(HwsEnergyEntity, SensorEntity, RestoreEntity):
    """Sensor for today's energy consumption/cost from the Aquarea consumption endpoint."""

    entity_description: HwsEnergySensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        coordinator: HwsConsumptionCoordinator,
        description: HwsEnergySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_suggested_display_precision = description.suggested_display_precision
        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        super().__init__(coordinator, description.key)

    async def async_added_to_hass(self) -> None:
        """Restore value from previous session."""
        restored = await self.async_get_last_state()
        if restored is not None and restored.state not in (
            None,
            "unknown",
            "unavailable",
        ):
            try:
                self._attr_native_value = float(restored.state)
            except ValueError:
                self._attr_native_value = 0
        else:
            self._attr_native_value = 0
        await super().async_added_to_hass()

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        consumption = self.coordinator.consumption
        if consumption is None:
            return
        value = self.entity_description.get_state(consumption)
        if value is not None:
            self._attr_native_value = value


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
