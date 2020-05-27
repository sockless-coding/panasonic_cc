"""Support for the Panasonic HVAC."""
import logging

import voluptuous as vol
from typing import Any, Dict, Optional, List

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import HVAC_MODE_OFF, SUPPORT_PRESET_MODE

from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE)

from . import DOMAIN as PANASONIC_DOMAIN, PANASONIC_DEVICES

from .const import SUPPORT_FLAGS, OPERATION_LIST, PRESET_LIST

_LOGGER = logging.getLogger(__name__)



def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Panasonic climate"""
    
    if discovery_info is None:
        return
    add_devices(
        [
            PanasonicClimateDevice(device)
            for device in hass.data[PANASONIC_DEVICES]
        ]
    )

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    pass

async def async_setup_entry(hass, entry, async_add_entities):

    async_add_entities(
        [
            PanasonicClimateDevice(device)
            for device in hass.data[PANASONIC_DEVICES]
        ]
    )

class PanasonicClimateDevice(ClimateEntity):

    def __init__(self, api):
        """Initialize the climate device."""

        self._api = api

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._api.id}-climate"

    async def async_turn_off(self):
        await self._api.turn_off()

    async def async_turn_on(self):
        await self._api.turn_on()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the display name of this climate."""
        return self._api.name

    @property
    def group(self):
        """Return the display group of this climate."""
        return self._api.group

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        return self._api.target_temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self._api.set_temperature(**kwargs)

    @property
    def hvac_mode(self):
        """Return the current operation."""
        if not self._api.is_on:
            return HVAC_MODE_OFF
        hvac_mode = self._api.hvac_mode
        for key, value in OPERATION_LIST.items():
            if value == hvac_mode:
                return key

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return list(OPERATION_LIST.keys())

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._api.turn_off()
        else:
            await self._api.set_hvac_mode(hvac_mode)

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._api.fan_mode

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        await self._api.set_fan_mode(fan_mode)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [f.name for f in self._api.constants.FanSpeed ]

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self._api.swing_mode

    async def async_set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        await self._api.set_swing_mode(swing_mode)

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        return [f.name for f in self._api.constants.AirSwingUD ]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._api.inside_temperature
        
    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.
        Requires SUPPORT_PRESET_MODE.
        """
        eco = self._api.eco_mode
        for key, value in PRESET_LIST.items():
            if value == eco:
                _LOGGER.debug("Preset mode is {0}".format(key))
                return key

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        await self._api.set_preset_mode(preset_mode)

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.
        Requires SUPPORT_PRESET_MODE.
        """
        _LOGGER.debug("Preset modes are {0}".format(",".join(PRESET_LIST.keys())))
        return list(PRESET_LIST.keys())

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30

    @property
    def target_temp_step(self):
        """Return the temperature step."""
        return 0.5

    async def async_update(self):
        """Retrieve latest state."""
        await self._api.update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info
    

