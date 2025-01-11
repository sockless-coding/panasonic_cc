"""Constants for Panasonic Cloud."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, Platform
from homeassistant.components.climate.const import (
    HVACMode, ClimateEntityFeature,
    PRESET_ECO, PRESET_NONE, PRESET_BOOST)

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_DAILY_ENERGY = "daily_energy"
ATTR_CURRENT_POWER = "current_power"

ATTR_SWING_LR_MODE = "horizontal_swing_mode"
ATTR_SWING_LR_MODES = "horizontal_swing_modes"

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

STATE_HEATING = "heating"

SERVICE_SET_SWING_LR_MODE = "set_horizontal_swing_mode"

KEY_DOMAIN = "domain"

TIMEOUT = 60

CONF_FORCE_OUTSIDE_SENSOR = "force_outside_sensor"
DEFAULT_FORCE_OUTSIDE_SENSOR = False
CONF_ENABLE_DAILY_ENERGY_SENSOR = "enable_daily_energy_sensor"
DEFAULT_ENABLE_DAILY_ENERGY_SENSOR = False
CONF_USE_PANASONIC_PRESET_NAMES = "use_panasonic_preset_names"
DEFAULT_USE_PANASONIC_PRESET_NAMES = True

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



OPERATION_LIST = {
    HVACMode.OFF: 'Off',
    HVACMode.HEAT: 'Heat',
    HVACMode.COOL: 'Cool',
    HVACMode.HEAT_COOL: 'Auto',
    HVACMode.DRY: 'Dry',
    HVACMode.FAN_ONLY: 'Fan'
}

DOMAIN = "panasonic_cc"
MANUFACTURER = "Panasonic"
PANASONIC_DEVICES = "panasonic_devices"
DATA_COORDINATORS = "data_coordinators"
ENERGY_COORDINATORS = "energy_coordinators"
AQUAREA_COORDINATORS = "aquarea_coorinators"

COMPONENT_TYPES = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.WATER_HEATER
    ]

STARTUP = """
-------------------------------------------------------------------
Panasonic Comfort Cloud

Version: %s
This is a custom integration
If you have any issues with this you need to open an issue here:
https://github.com/sockless-coding/panasonic_cc/issues
-------------------------------------------------------------------
"""

SELECT_HORIZONTAL_SWING = "horizontal_swing"
SELECT_VERTICAL_SWING = "vertical_swing"

CONF_DEVICE_FETCH_INTERVAL = "device_fetch_interval"
CONF_ENERGY_FETCH_INTERVAL = "energy_fetch_interval"
DEFAULT_DEVICE_FETCH_INTERVAL = 30
DEFAULT_ENERGY_FETCH_INTERVAL = 60
CONF_FORCE_ENABLE_NANOE = "force_enable_nanoe"
DEFAULT_FORCE_ENABLE_NANOE = False