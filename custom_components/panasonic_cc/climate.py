"""Support for the Panasonic HVAC."""
from typing import Callable, Any
from dataclasses import dataclass
import logging

import voluptuous as vol
from typing import Optional, List

from homeassistant.core import HomeAssistant
from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription, HVACAction, HVACMode, ATTR_HVAC_MODE
from homeassistant.helpers import config_validation as cv, entity_platform

from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE


from .base import PanasonicDataEntity
from .coordinator import PanasonicDeviceCoordinator
from .pcomfortcloud import constants
from .pcomfortcloud.changerequestbuilder import ChangeRequestBuilder

from .const import (
    SUPPORT_FLAGS,
    SERVICE_SET_SWING_LR_MODE,
    PRESET_8_15, 
    PRESET_NONE, 
    PRESET_ECO, 
    PRESET_BOOST, 
    PRESET_QUIET, 
    PRESET_POWERFUL,
    DOMAIN,
    DATA_COORDINATORS)

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicClimateEntityDescription(ClimateEntityDescription):
    """Describes a Panasonic climate entity."""

PANASONIC_CLIMATE_DESCRIPTION = PanasonicClimateEntityDescription(
    key="climate",
    translation_key="climate",
    unit_of_measurement=UnitOfTemperature.CELSIUS,
    
)

def convert_operation_mode_to_hvac_mode(operation_mode: constants.OperationMode) -> HVACMode | None:
    """Convert OperationMode to HVAC mode."""
    match operation_mode:
        case constants.OperationMode.Auto:
            return HVACMode.AUTO
        case constants.OperationMode.Cool:
            return HVACMode.COOL
        case constants.OperationMode.Dry:
            return HVACMode.DRY
        case constants.OperationMode.Fan:
            return HVACMode.FAN_ONLY
        case constants.OperationMode.Heat:
            return HVACMode.HEAT
        
def convert_hvac_mode_to_operation_mode(hvac_mode: HVACMode) -> constants.OperationMode | None:
    """Convert HVAC mode to OperationMode."""
    match hvac_mode:
        case HVACMode.AUTO:
            return constants.OperationMode.Auto
        case HVACMode.COOL:
            return constants.OperationMode.Cool
        case HVACMode.DRY:
            return constants.OperationMode.Dry
        case HVACMode.FAN_ONLY:
            return constants.OperationMode.Fan
        case HVACMode.HEAT:
            return constants.OperationMode.Heat


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    for coordinator in data_coordinators:
        entities.append(PanasonicClimateEntity(coordinator, PANASONIC_CLIMATE_DESCRIPTION))
        
    async_add_entities(entities)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_SWING_LR_MODE,
        {
            vol.Required('swing_mode'): cv.string,
        },
        "async_set_horizontal_swing_mode",
    )


class PanasonicClimateEntity(PanasonicDataEntity, ClimateEntity):
    """Representation of a Panasonic Climate Device."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = SUPPORT_FLAGS
    _attr_fan_modes = [f.name for f in constants.FanSpeed]

    def __init__(self, coordinator: PanasonicDeviceCoordinator, description: PanasonicClimateEntityDescription):
        """Initialize the climate entity."""
        self.entity_description = description
        self._attr_name = coordinator.device.info.name        
        device = coordinator.device
        hvac_modes = [HVACMode.OFF]
        if device.features.auto_mode:
            hvac_modes += [HVACMode.HEAT_COOL]
        if device.features.cool_mode:
            hvac_modes += [HVACMode.COOL]
        if device.features.dry_mode:
            hvac_modes += [HVACMode.DRY]
        if device.features.fan_mode:
            hvac_modes += [HVACMode.FAN_ONLY]
        if device.features.heat_mode:
            hvac_modes += [HVACMode.HEAT]
        self._attr_hvac_modes = hvac_modes

        preset_modes = [PRESET_NONE]
        if device.features.quiet_mode:
            preset_modes += [PRESET_QUIET]
        if device.features.powerful_mode:
            preset_modes += [PRESET_POWERFUL]
        if device.features.summer_house > 0:
            preset_modes += [PRESET_8_15]
        self._attr_preset_modes = preset_modes
        
        self._attr_swing_modes = [opt.name for opt in constants.AirSwingUD if opt != constants.AirSwingUD.Auto or device.features.auto_swing_ud]
        
        

        super().__init__(coordinator, description.key)
        _LOGGER.info(f"Registing Climate entity: '{self._attr_unique_id}'")
        



    def _async_update_attrs(self) -> None:
        """Update attributes."""
        state = self.coordinator.device.parameters
        self._attr_hvac_mode = (HVACMode.OFF 
                                if state.power == constants.Power.Off 
                                else convert_operation_mode_to_hvac_mode(state.mode))
        

        self._set_temp_range()
        self._attr_current_temperature = state.inside_temperature
        self._attr_target_temperature = state.target_temperature
        self._attr_fan_mode = state.fan_speed.name
        self._attr_swing_mode = state.vertical_swing_mode.name
        if self.coordinator.device.in_summer_house_mode:
            self._attr_preset_mode = PRESET_8_15
        elif state.eco_mode == constants.EcoMode.Quiet:
            self._attr_preset_mode = PRESET_QUIET
        elif state.eco_mode == constants.EcoMode.Powerful:
            self._attr_preset_mode = PRESET_POWERFUL
        else:
            self._attr_preset_mode = PRESET_NONE

    def _set_temp_range(self) -> None:
        """Set new target temperature range."""
        device = self.coordinator.device
        self._attr_min_temp = 8 if device.in_summer_house_mode else 16
        if device.in_summer_house_mode:
            self._attr_max_temp = 15 if device.features.summer_house == 2 else 10
        else:
            self._attr_max_temp = 30

    def _update_attributes(self, builder: ChangeRequestBuilder) -> None:
        """Update attributes."""
        if builder.power_mode == constants.Power.Off:
            self._attr_hvac_mode = HVACMode.OFF
        if builder.target_temperature:
            self._attr_target_temperature = builder.target_temperature
            if builder.target_temperature > 15 and self._attr_preset_mode == PRESET_8_15:
                self._attr_preset_mode = PRESET_NONE
            elif builder.target_temperature < 15 and self._attr_preset_mode != PRESET_8_15:
                self._attr_preset_mode = PRESET_8_15
                
        if builder.eco_mode:
            if builder.eco_mode.name in (PRESET_QUIET, PRESET_ECO):
                self._attr_preset_mode = PRESET_QUIET
            elif builder.eco_mode.name in (PRESET_POWERFUL, PRESET_BOOST):
                self._attr_preset_mode = PRESET_POWERFUL
            else:
                self._attr_preset_mode = PRESET_NONE

        if builder.fan_speed:
            self._attr_fan_mode = builder.fan_speed.name
        if builder.vertical_swing:
            self._attr_swing_mode = builder.vertical_swing.name
        if builder.hvac_mode:
            self._attr_hvac_mode = convert_operation_mode_to_hvac_mode(builder.hvac_mode)
        self.async_write_ha_state()


    async def _async_enter_summer_house_mode(self, builder: ChangeRequestBuilder):
        """Enter summer house mode."""
        device = self.coordinator.device
        stored_data = await self.coordinator.async_get_stored_data()

        stored_data['mode'] = device.parameters.mode
        stored_data['ecoMode'] = device.parameters.eco_mode
        stored_data['targetTemperature'] = device.parameters.target_temperature
        stored_data['fanSpeed'] = device.parameters.fan_speed
        await self.coordinator.async_store_data(stored_data)

        builder.set_hvac_mode(HVACMode.HEAT)
        builder.set_eco_mode(constants.EcoMode.Powerful)
        builder.set_target_temperature(8)
        builder.set_fan_speed(constants.FanSpeed.High)

        self._attr_min_temp = 8
        self._attr_max_temp = 15 if device.features.summer_house == 2 else 10

    async def _async_exit_summer_house_mode(self, builder: ChangeRequestBuilder) -> Callable[[ClimateEntity], None]:
        """Exit summer house mode."""
        self._attr_min_temp = 16
        self._attr_max_temp = 30
        if not self.coordinator.device.in_summer_house_mode:
            return
        stored_data = await self.coordinator.async_get_stored_data()
        hvac_mode = stored_data['mode'] if 'mode' in stored_data else constants.OperationMode.Heat
        eco_mode = stored_data['ecoMode'] if 'ecoMode' in stored_data else constants.EcoMode.Auto
        target_temperature = stored_data['targetTemperature'] if 'targetTemperature' in stored_data else 20
        fan_speed = stored_data['fanSpeed'] if 'fanSpeed' in stored_data else constants.FanSpeed.Auto
        builder.set_hvac_mode(hvac_mode)
        builder.set_eco_mode(eco_mode)
        builder.set_target_temperature(target_temperature)
        builder.set_fan_speed(fan_speed)

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        builder = self.coordinator.get_change_request_builder()
        builder.set_power_mode(constants.Power.On)
        await self.coordinator.async_apply_changes(builder)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        builder = self.coordinator.get_change_request_builder()
        builder.set_power_mode(constants.Power.Off)
        await self.coordinator.async_apply_changes(builder)
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""
        builder = self.coordinator.get_change_request_builder()
        if temp := kwargs.get(ATTR_TEMPERATURE):
            builder.set_target_temperature(temp)
        if mode := kwargs.get(ATTR_HVAC_MODE):
            if op_mode := convert_hvac_mode_to_operation_mode(mode):
                builder.set_hvac_mode(op_mode)
            else:
                mode = None
        await self.coordinator.async_apply_changes(builder)        
        self._update_attributes(builder)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        if not (op_mode := convert_hvac_mode_to_operation_mode(hvac_mode)):
            raise ValueError(f"Invalid hvac mode {hvac_mode}")
        
        builder = self.coordinator.get_change_request_builder()
        await self._async_exit_summer_house_mode(builder)
        builder.set_hvac_mode(op_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)
        
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset_mode '{preset_mode}'")
        
        builder = self.coordinator.get_change_request_builder()
        await self._async_exit_summer_house_mode(builder)
        builder.set_eco_mode(constants.EcoMode.Auto)
        if preset_mode in (PRESET_QUIET, PRESET_ECO):
            builder.set_eco_mode(constants.EcoMode.Quiet)
        elif preset_mode in (PRESET_POWERFUL, PRESET_BOOST):
            builder.set_eco_mode(constants.EcoMode.Powerful)
        elif preset_mode == PRESET_8_15:
            await self._async_enter_summer_house_mode(builder)
                
        self._update_attributes(builder)
        
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan_mode '{fan_mode}'")
        
        builder = self.coordinator.get_change_request_builder()
        builder.set_fan_speed(fan_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)

    async def async_set_swing_mode(self, swing_mode: str):
        """Set new target swing mode."""
        if swing_mode not in self.swing_modes:
            raise ValueError(f"Unsupported swing mode '{swing_mode}'")
        
        builder = self.coordinator.get_change_request_builder()
        builder.set_vertical_swing(swing_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)
