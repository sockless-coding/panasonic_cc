"""Panasonic sensor entities."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.const import UnitOfEnergy, UnitOfTemperature, EntityCategory
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from aio_panasonic_comfort_cloud import PanasonicDevice, PanasonicDeviceEnergy, PanasonicDeviceZone, constants

from ..const import DOMAIN
from .base import PanasonicDataEntity, PanasonicEnergyEntity
from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator
from .const import DATA_COORDINATORS, ENERGY_COORDINATORS

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicSensorEntityDescription(SensorEntityDescription):
    """Describes Panasonic sensor entity."""
    get_state: Callable[[PanasonicDevice], Any] | None = None
    is_available: Callable[[PanasonicDevice], bool] | None = None

@dataclass(frozen=True, kw_only=True)
class PanasonicEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Panasonic sensor entity."""
    get_state: Callable[[PanasonicDeviceEnergy], Any]| None = None

INSIDE_TEMPERATURE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="inside_temperature",
    translation_key="inside_temperature",
    name="Inside Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.parameters.inside_temperature,
    is_available=lambda device: device.parameters.inside_temperature is not None,
)
OUTSIDE_TEMPERATURE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="outside_temperature",
    translation_key="outside_temperature",
    name="Outside Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.parameters.outside_temperature,
    is_available=lambda device: device.parameters.outside_temperature is not None,
)
LAST_UPDATE_TIME_DESCRIPTION = PanasonicSensorEntityDescription(
    key="last_update",
    translation_key="last_update",
    name="Last Updated",
    icon="mdi:clock-outline",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=None,
    native_unit_of_measurement=None,
    get_state=lambda device: device.last_update,
    is_available=lambda device: True,
    entity_registry_enabled_default=False,
)
DATA_AGE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="data_age",
    translation_key="data_age",
    name="Cached Data Age",
    icon="mdi:clock-outline",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=None,
    native_unit_of_measurement=None,
    get_state=lambda device: device.timestamp,
    is_available=lambda device: device.info.status_data_mode == constants.StatusDataMode.CACHED,
    entity_registry_enabled_default=False,
)
DATA_MODE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="status_data_mode",
    translation_key="status_data_mode",
    name="Data Mode",
    options=[opt.name for opt in constants.StatusDataMode],
    device_class=SensorDeviceClass.ENUM,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=None,
    native_unit_of_measurement=None,
    get_state=lambda device: device.info.status_data_mode.name,
    is_available=lambda device: True,
    entity_registry_enabled_default=True,
)
DAILY_ENERGY_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="daily_energy_sensor",
    translation_key="daily_energy_sensor",
    name="Daily Energy",
    icon="mdi:flash",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement="kWh",
    get_state=lambda energy: energy.consumption
)
DAILY_HEATING_ENERGY_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="daily_heating_energy",
    translation_key="daily_heating_energy",
    name="Daily Heating Energy",
    icon="mdi:flash",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement="kWh",
    get_state=lambda energy: energy.heating_consumption
)
DAILY_COOLING_ENERGY_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="daily_cooling_energy",
    translation_key="daily_cooling_energy",
    name="Daily Cooling Energy",
    icon="mdi:flash",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement="kWh",
    get_state=lambda energy: energy.cooling_consumption
)
POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="current_power",
    translation_key="current_power",
    name="Current Extrapolated Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.current_power
)
COOLING_POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="cooling_power",
    translation_key="cooling_power",
    name="Cooling Extrapolated Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.cooling_power
)
HEATING_POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="heating_power",
    translation_key="heating_power",
    name="Heating Extrapolated Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.heating_power
)


def create_zone_temperature_description(zone: PanasonicDeviceZone):
    return PanasonicSensorEntityDescription(
        key = f"zone-{zone.id}-temperature",
        translation_key=f"zone-{zone.id}-temperature",
        name = f"{zone.name} Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        get_state=lambda device: zone.temperature,
        is_available=lambda device: zone.has_temperature
    )


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = hass.data[DOMAIN][ENERGY_COORDINATORS]

    for coordinator in data_coordinators:
        entities.append(PanasonicSensorEntity(coordinator, INSIDE_TEMPERATURE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, OUTSIDE_TEMPERATURE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, LAST_UPDATE_TIME_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, DATA_AGE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, DATA_MODE_DESCRIPTION))
        if coordinator.device.has_zones:
            for zone in coordinator.device.parameters.zones:
                entities.append(PanasonicSensorEntity(
                    coordinator,
                    create_zone_temperature_description(zone)))

    for coordinator in energy_coordinators:
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_COOLING_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_HEATING_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, POWER_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, COOLING_POWER_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, HEATING_POWER_DESCRIPTION))

    async_add_entities(entities)


class PanasonicSensorEntityBase(SensorEntity):
    """Base class for all sensor entities."""

    entity_description: PanasonicSensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

class PanasonicSensorEntity(PanasonicDataEntity, PanasonicSensorEntityBase):
    """Representation of a Panasonic sensor."""

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        super().__init__(coordinator, description.key)

    @property  # type: ignore[reportIncompatibleOverride]
    def available(self) -> bool:
        """Return if entity is available."""
        if self.entity_description.is_available is None:
            return True
        return self.entity_description.is_available(self.coordinator.device)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        if self.entity_description.is_available:
            self._attr_available = self.entity_description.is_available(self.coordinator.device)
        if self.entity_description.get_state:
            state = self.entity_description.get_state(self.coordinator.device)
            self._attr_native_value = state


class PanasonicEnergySensorEntity(PanasonicEnergyEntity, SensorEntity):
    """Representation of a Panasonic energy sensor."""

    entity_description: PanasonicEnergySensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(self, coordinator: PanasonicDeviceEnergyCoordinator, description: PanasonicEnergySensorEntityDescription):
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        super().__init__(coordinator, description.key)

    @property  # type: ignore[reportIncompatibleOverride]
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        energy = self.coordinator.energy
        if energy is None:
            return
        if self.entity_description.get_state is None:
            return
        value = self.entity_description.get_state(energy)
        self._attr_available = value is not None
        self._attr_native_value = value  # type: ignore[assignment]
