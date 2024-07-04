"""Support for the Panasonic HVAC."""
import logging

import voluptuous as vol
from typing import Optional, List

from homeassistant.components.climate import ClimateEntity, HVACAction, HVACMode
from homeassistant.helpers import config_validation as cv, entity_platform

from homeassistant.const import UnitOfTemperature

from . import PANASONIC_DEVICES
from .panasonic import PanasonicApiDevice

from .const import (
    SUPPORT_FLAGS,
    OPERATION_LIST,
    PRESET_LIST,
    ATTR_SWING_LR_MODE,
    ATTR_SWING_LR_MODES,
    SERVICE_SET_SWING_LR_MODE)

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

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_SWING_LR_MODE,
        {
            vol.Required('swing_mode'): cv.string,
        },
        "async_set_horizontal_swing_mode",
    )


class PanasonicClimateDevice(ClimateEntity):

    def __init__(self, api: PanasonicApiDevice):
        """Initialize the climate device."""        
        self._api = api
        self._attr_hvac_action = HVACAction.IDLE
        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_translation_key = 'panasonic_climate'
        self._attr_min_temp = api.min_temp
        self._attr_max_temp = api.max_temp


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
        return UnitOfTemperature.CELSIUS

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
            return HVACMode.OFF
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
        if hvac_mode == HVACMode.OFF:
            await self._api.turn_off()
        else:
            await self._api.set_hvac_mode(hvac_mode)
        self._clear_min_max()

    @property
    def hvac_action(self):
        # if not self._api.is_on:
        #     HVACAction.OFF

        hvac_mode = self.hvac_mode
        if (
                (hvac_mode == HVACMode.HEAT or hvac_mode == HVACMode.HEAT_COOL)
                and (
                self._api.inside_temperature is None or self._api.target_temperature > self._api.inside_temperature)
        ):
            return HVACAction.HEATING
        elif (
                (hvac_mode == HVACMode.COOL or hvac_mode == HVACMode.HEAT_COOL)
                and (
                        self._api.inside_temperature is None or self._api.target_temperature < self._api.inside_temperature)
        ):
            return HVACAction.COOLING
        elif hvac_mode == HVACMode.DRY:
            return HVACAction.DRYING
        elif hvac_mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN

        return HVACAction.IDLE

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
        return [f.name for f in self._api.constants.FanSpeed]

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self._api.swing_mode

    async def async_set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        await self._api.set_swing_mode(swing_mode)

    @property
    def swing_lr_mode(self):
        return self._api.swing_lr_mode

    async def async_set_horizontal_swing_mode(self, swing_mode):
        await self._api.set_swing_lr_mode(swing_mode)

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""

        def supported(x):
            return x != self._api.constants.AirSwingUD.Swing or self._api.features is not None and self._api.features[
                'upDownAllSwing']  # noqa: E501

        return [f.name for f in filter(supported, self._api.constants.AirSwingUD)]

    @property
    def swing_lr_modes(self):
        """Return the list of available swing modes."""
        return [f.name for f in self._api.constants.AirSwingLR if f != self._api.constants.AirSwingLR.Unavailable]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._api.inside_temperature

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.
        Requires SUPPORT_PRESET_MODE.
        """
        return self._api.preset_mode

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        await self._api.set_preset_mode(preset_mode)
        self._clear_min_max()

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.
        Requires SUPPORT_PRESET_MODE.
        """
        #_LOGGER.debug("Preset modes are {0}".format(",".join(PRESET_LIST.keys())))
        return self._api.available_presets


    @property
    def target_temp_step(self):
        """Return the temperature step."""
        return 0.5

    async def async_update(self):
        """Retrieve latest state."""
        was_in_summer_house_mode = self._api.in_summer_house_mode
        await self._api.update()
        if was_in_summer_house_mode != self._api.in_summer_house_mode or self.min_temp != self._api.min_temp:
            self._clear_min_max()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._api.device_info

    @property
    def extra_state_attributes(self):
        attrs = {}
        try:
            attrs[ATTR_SWING_LR_MODE] = self.swing_lr_mode
            attrs[ATTR_SWING_LR_MODES] = self.swing_lr_modes
        except KeyError:
            pass
        return attrs
    
    def _clear_min_max(self):
        self._attr_min_temp = self._api.min_temp
        self._attr_max_temp = self._api.max_temp
        del self.min_temp
        del self.max_temp
