"""Shared constants for Panasonic Comfort Cloud integration."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, Platform
from homeassistant.components.climate.const import (
    HVACMode, ClimateEntityFeature,
    PRESET_ECO, PRESET_NONE, PRESET_BOOST)

DOMAIN = "panasonic_cc"
MANUFACTURER = "Panasonic"

# Coordinator keys in hass.data[DOMAIN]
DATA_COORDINATORS = "data_coordinators"
ENERGY_COORDINATORS = "energy_coordinators"
AQUAREA_COORDINATORS = "aquarea_coordinators"

NOTIFICATION_AUTH_EXPIRED = f"{DOMAIN}_auth_expired"

# Config keys
CONF_FORCE_OUTSIDE_SENSOR = "force_outside_sensor"
DEFAULT_FORCE_OUTSIDE_SENSOR = False
CONF_ENABLE_DAILY_ENERGY_SENSOR = "enable_daily_energy_sensor"
DEFAULT_ENABLE_DAILY_ENERGY_SENSOR = False
CONF_USE_PANASONIC_PRESET_NAMES = "use_panasonic_preset_names"
DEFAULT_USE_PANASONIC_PRESET_NAMES = True
CONF_DEVICE_FETCH_INTERVAL = "device_fetch_interval"
CONF_ENERGY_FETCH_INTERVAL = "energy_fetch_interval"
DEFAULT_DEVICE_FETCH_INTERVAL = 120
DEFAULT_ENERGY_FETCH_INTERVAL = 300
CONF_FORCE_ENABLE_NANOE = "force_enable_nanoe"
DEFAULT_FORCE_ENABLE_NANOE = False

# Service definitions
SERVICE_SET_SWING_LR_MODE = "set_horizontal_swing_mode"

# Platforms
COMPONENT_TYPES = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.WATER_HEATER,
    Platform.BINARY_SENSOR,
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
