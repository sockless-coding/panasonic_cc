"""Constants for Panasonic Cloud."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL,
    HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY, HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, 
    SUPPORT_SWING_MODE, SUPPORT_PRESET_MODE,
    PRESET_ECO, PRESET_NONE, PRESET_BOOST)

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

KEY_DOMAIN = "domain"

TIMEOUT = 60

CONF_FORCE_OUTSIDE_SENSOR = "force_outside_sensor"
DEFAULT_FORCE_OUTSIDE_SENSOR = False
CONF_ENABLE_DAILY_ENERGY_SENSOR = "enable_daily_energy_sensor"
DEFAULT_ENABLE_DAILY_ENERGY_SENSOR = False

SENSOR_TYPE_TEMPERATURE = "temperature"

SENSOR_TYPES = {
    ATTR_INSIDE_TEMPERATURE: {
        CONF_NAME: "Inside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
    },
    ATTR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: "Outside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
    },
}

SUPPORT_FLAGS = (
    SUPPORT_TARGET_TEMPERATURE |
    SUPPORT_FAN_MODE |
    SUPPORT_PRESET_MODE |
    SUPPORT_SWING_MODE )

PRESET_LIST = {
    PRESET_NONE: 'Auto',
    PRESET_BOOST: 'Powerful',
    PRESET_ECO: 'Quiet'
}

OPERATION_LIST = {
    HVAC_MODE_OFF: 'Off',
    HVAC_MODE_HEAT: 'Heat',
    HVAC_MODE_COOL: 'Cool',
    HVAC_MODE_HEAT_COOL: 'Auto',
    HVAC_MODE_DRY: 'Dry',
    HVAC_MODE_FAN_ONLY: 'Fan'
    }
