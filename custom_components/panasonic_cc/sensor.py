"""Support for Panasonic sensors."""
import logging

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, UnitOfTemperature
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass
)

from . import PANASONIC_DEVICES
from .const import (
    ATTR_INSIDE_TEMPERATURE, 
    ATTR_OUTSIDE_TEMPERATURE, 
    SENSOR_TYPES, 
    
    ATTR_DAILY_ENERGY,
    ATTR_CURRENT_POWER,
    ENERGY_SENSOR_TYPES
    )

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    
    for device in hass.data[PANASONIC_DEVICES]:
        sensors = []
        if device.support_inside_temperature:
            sensors.append(ATTR_INSIDE_TEMPERATURE)
        if device.support_outside_temperature:
            sensors.append(ATTR_OUTSIDE_TEMPERATURE)
        entities = [PanasonicClimateSensor(device, sensor) for sensor in sensors]
        if device.energy_sensor_enabled:
            entities.append(PanasonicEnergySensor(device, ATTR_DAILY_ENERGY))
            entities.append(PanasonicEnergySensor(device, ATTR_CURRENT_POWER))
        add_entities(entities)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

async def async_setup_entry(hass, entry, async_add_entities):
    for device in hass.data[PANASONIC_DEVICES]:
        sensors = [ATTR_INSIDE_TEMPERATURE]
        if device.support_outside_temperature:
            sensors.append(ATTR_OUTSIDE_TEMPERATURE)
        entities = [PanasonicClimateSensor(device, sensor) for sensor in sensors]
        if device.energy_sensor_enabled:
            entities.append(PanasonicEnergySensor(device, ATTR_DAILY_ENERGY))
            entities.append(PanasonicEnergySensor(device, ATTR_CURRENT_POWER))
        async_add_entities(entities)


class PanasonicClimateSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, api, monitored_state) -> None:
        """Initialize the sensor."""
        self._api = api
        self._sensor = SENSOR_TYPES[monitored_state]
        self._name = f"{api.name} {self._sensor[CONF_NAME]}"
        self._device_attribute = monitored_state

    @property
    def unique_id(self):
        """Return a unique ID."""
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
        if self._device_attribute == ATTR_INSIDE_TEMPERATURE:
            return self._api.inside_temperature
        if self._device_attribute == ATTR_OUTSIDE_TEMPERATURE:
            return self._api.outside_temperature
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

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
            return round(self._api.daily_energy,2)
        if self._device_attribute == ATTR_CURRENT_POWER:
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
    
