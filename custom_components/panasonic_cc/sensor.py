from typing import Callable, Any
from dataclasses import dataclass
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, UnitOfTemperature, EntityCategory
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription
)

from .pcomfortcloud.panasonicdevice import PanasonicDevice, PanasonicDeviceEnergy

from .const import (
    DOMAIN,
    DATA_COORDINATORS,
    ENERGY_COORDINATORS,
    
    ATTR_DAILY_ENERGY,
    ATTR_CURRENT_POWER,
    ENERGY_SENSOR_TYPES
    )
from .base import PanasonicDataEntity, PanasonicEnergyEntity
from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicSensorEntityDescription(SensorEntityDescription):
    """Describes Panasonic sensor entity."""
    get_state: Callable[[PanasonicDevice], Any] = None
    is_available: Callable[[PanasonicDevice], bool] = None

@dataclass(frozen=True, kw_only=True)
class PanasonicEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Panasonic sensor entity."""
    get_state: Callable[[PanasonicDeviceEnergy], Any] = None

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
    is_available=lambda device: True
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
    name="Current Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.current_power
)
COOLING_POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="cooling_power",
    translation_key="cooling_power",
    name="Cooling Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.cooling_power
)
HEATING_POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="heating_power",
    translation_key="heating_power",
    name="Heating Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.heating_power
)


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = hass.data[DOMAIN][ENERGY_COORDINATORS]
    for coordinator in data_coordinators:
        entities.append(PanasonicSensorEntity(coordinator, INSIDE_TEMPERATURE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, OUTSIDE_TEMPERATURE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, LAST_UPDATE_TIME_DESCRIPTION))

    for coordinator in energy_coordinators:
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_COOLING_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_HEATING_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, POWER_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, COOLING_POWER_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, HEATING_POWER_DESCRIPTION))
        

        
    async_add_entities(entities)
    """
    for device in hass.data[PANASONIC_DEVICES]:
        sensors = [ATTR_INSIDE_TEMPERATURE]
        if device.support_outside_temperature:
            sensors.append(ATTR_OUTSIDE_TEMPERATURE)
        entities = [PanasonicClimateSensor(device, sensor) for sensor in sensors]
        if device.energy_sensor_enabled:
            entities.append(PanasonicEnergySensor(device, ATTR_DAILY_ENERGY))
            entities.append(PanasonicEnergySensor(device, ATTR_CURRENT_POWER))
        async_add_entities(entities)
        """

class PanasonicSensorEntityBase(SensorEntity):
    """Base class for all sensor entities."""
    entity_description: PanasonicSensorEntityDescription

class PanasonicSensorEntity(PanasonicDataEntity, PanasonicSensorEntityBase):
    
    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicSensorEntityDescription):
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entity_description.is_available(self.coordinator.device)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_available = self.entity_description.is_available(self.coordinator.device)
        self._attr_native_value = self.entity_description.get_state(self.coordinator.device)

class PanasonicEnergySensorEntity(PanasonicEnergyEntity, SensorEntity):
    
    entity_description: PanasonicEnergySensorEntityDescription

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicEnergySensorEntityDescription):
        self.entity_description = description
        super().__init__(coordinator, description.key)
    
    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_native_value = self.entity_description.get_state(self.coordinator.energy)
        if self.registry_entry is not None and self.registry_entry.disabled and self._attr_native_value is not None:
           self.registry_entry.disabled_by = None



class PanasonicEnergySensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api, monitored_state) -> None:
        """Initialize the sensor."""
        self._api = api
        self._sensor = ENERGY_SENSOR_TYPES[monitored_state]
        self._name = f"{api.name} {self._sensor[CONF_NAME]}"
        self._device_attribute = monitored_state
        if self._device_attribute == ATTR_DAILY_ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_device_class = SensorDeviceClass.ENERGY
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_device_class = SensorDeviceClass.POWER

    @property
    def unique_id(self):
        """Return a unique ID."""
        if self._device_attribute == ATTR_DAILY_ENERGY:
            return f"{self._api.id}-daily_energy_sensor"
        return f"{self._api.id}-{self._device_attribute}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._sensor[CONF_ICON]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._device_attribute == ATTR_DAILY_ENERGY:
            if self._api.daily_energy is None:
                return None
            return round(self._api.daily_energy,2)
        if self._device_attribute == ATTR_CURRENT_POWER:
            if self._api.current_power is None:
                return None
            return round(self._api.current_power,2)
        return None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor[CONF_TYPE]

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor[CONF_TYPE]

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.update_energy()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info
    
