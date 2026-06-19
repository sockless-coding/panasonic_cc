"""Constants for Panasonic Comfort Cloud devices."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    PRESET_ECO, PRESET_NONE, PRESET_BOOST,
)

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_DAILY_ENERGY = "daily_energy"
ATTR_CURRENT_POWER = "current_power"

ATTR_SWING_LR_MODE = "horizontal_swing_mode"
ATTR_SWING_LR_MODES = "horizontal_swing_modes"

SERVICE_SET_SWING_LR_MODE = "set_horizontal_swing_mode"

SENSOR_TYPE_TEMPERATURE = "temperature"

PRESET_8_15 = "heat_8_15"
PRESET_QUIET = "quiet"
PRESET_POWERFUL = "powerful"

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

ENERGY_SENSOR_TYPES = {
    ATTR_DAILY_ENERGY: {
        CONF_NAME: "Daily Energy",
        CONF_ICON: "mdi:flash",
        CONF_TYPE: "kWh",
    },
    ATTR_CURRENT_POWER: {
        CONF_NAME: "Current Power",
        CONF_ICON: "mdi:flash",
        CONF_TYPE: "W",
    },
}

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE |
    ClimateEntityFeature.FAN_MODE |
    ClimateEntityFeature.PRESET_MODE |
    ClimateEntityFeature.SWING_MODE |
    ClimateEntityFeature.TURN_OFF |
    ClimateEntityFeature.TURN_ON
)

DATA_COORDINATORS = "data_coordinators"
ENERGY_COORDINATORS = "energy_coordinators"

SELECT_HORIZONTAL_SWING = "horizontal_swing"
SELECT_VERTICAL_SWING = "vertical_swing"
