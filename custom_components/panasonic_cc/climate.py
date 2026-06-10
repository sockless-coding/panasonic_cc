from __future__ import annotations

import asyncio
from typing import Any
from dataclasses import dataclass
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    HVACAction,
    HVACMode,
    ATTR_HVAC_MODE,
)
from homeassistant.helpers import config_validation as cv, entity_platform
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE, PRECISION_WHOLE
from homeassistant.components.climate.const import ClimateEntityFeature

from .base import PanasonicDataEntity, AquareaDataEntity
from .coordinator import PanasonicDeviceCoordinator, AquareaDeviceCoordinator
from aio_panasonic_comfort_cloud import PanasonicDeviceParameters, ChangeRequestBuilder, constants
from aioaquarea import (
    ExtendedOperationMode as AquareaExtendedOperationMode,
    OperationStatus as AquareaZoneOperationStatus,
    DeviceAction as AquareaDeviceAction,
    UpdateOperationMode as AquareaUpdateOperationMode,
    SpecialStatus as AquareaSpecialStatus,
    DeviceDirection as AquareaDeviceDirection,
)

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
    DATA_COORDINATORS,
    AQUAREA_COORDINATORS,
    CONF_USE_PANASONIC_PRESET_NAMES,
    DEFAULT_USE_PANASONIC_PRESET_NAMES,
)

_LOGGER = logging.getLogger(__name__)

AQUAREA_CLIMATE_DELAY_SHORT = 5.0
AQUAREA_CLIMATE_DELAY_LONG = 10.0

AQUAREA_SPECIAL_STATUS_LOOKUP: dict[str, AquareaSpecialStatus | None] = {
    PRESET_ECO: AquareaSpecialStatus.ECO,
    "comfort": AquareaSpecialStatus.COMFORT,
    PRESET_NONE: None,
}
AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP = {v: k for k, v in AQUAREA_SPECIAL_STATUS_LOOKUP.items()}


@dataclass(frozen=True, kw_only=True)
class PanasonicClimateEntityDescription(ClimateEntityDescription):
    """Describes a Panasonic climate entity."""


@dataclass(frozen=True, kw_only=True)
class AquareaClimateEntityDescription(ClimateEntityDescription):
    """Describes an Aquarea climate entity."""

    zone_id: int


PANASONIC_CLIMATE_DESCRIPTION = PanasonicClimateEntityDescription(
    key="climate",
    translation_key="climate",
)


def convert_operation_mode_to_hvac_mode(
    operation_mode: constants.OperationMode, iauto: bool
) -> HVACMode | None:
    """Convert OperationMode to HVAC mode."""
    match operation_mode:
        case constants.OperationMode.Auto:
            return HVACMode.COOL if iauto else HVACMode.HEAT_COOL
        case constants.OperationMode.Cool:
            return HVACMode.COOL
        case constants.OperationMode.Dry:
            return HVACMode.DRY
        case constants.OperationMode.Fan:
            return HVACMode.FAN_ONLY
        case constants.OperationMode.Heat:
            return HVACMode.HEAT


def convert_hvac_mode_to_operation_mode(
    hvac_mode: HVACMode,
) -> constants.OperationMode | None:
    """Convert HVAC mode to OperationMode."""
    match hvac_mode:
        case HVACMode.HEAT_COOL:
            return constants.OperationMode.Auto
        case HVACMode.COOL:
            return constants.OperationMode.Cool
        case HVACMode.DRY:
            return constants.OperationMode.Dry
        case HVACMode.FAN_ONLY:
            return constants.OperationMode.Fan
        case HVACMode.HEAT:
            return constants.OperationMode.Heat


def convert_state_to_hvac_action(state: PanasonicDeviceParameters) -> HVACAction | None:
    """Convert state to HVAC action."""
    if state.power == constants.Power.Off:
        return HVACAction.OFF

    target_temp = state.target_temperature
    inside_temp = state.inside_temperature

    if target_temp is None or inside_temp is None:
        return None

    match state.mode:
        case constants.OperationMode.Auto:
            auto_diff = target_temp - inside_temp
            if auto_diff >= 1:
                return HVACAction.HEATING
            if auto_diff <= -1:
                return HVACAction.COOLING
            return HVACAction.IDLE
        case constants.OperationMode.Cool:
            return (
                HVACAction.COOLING
                if target_temp < inside_temp
                else HVACAction.IDLE
            )
        case constants.OperationMode.Dry:
            return HVACAction.DRYING
        case constants.OperationMode.Fan:
            return HVACAction.IDLE
        case constants.OperationMode.Heat:
            return (
                HVACAction.HEATING
                if target_temp > inside_temp
                else HVACAction.IDLE
            )


def convert_mode_and_status_to_hvac_mode(
    mode: AquareaExtendedOperationMode,
    zone_status: AquareaZoneOperationStatus,
) -> HVACMode:
    """Convert mode and status to HVAC mode."""
    if zone_status == AquareaZoneOperationStatus.OFF:
        return HVACMode.OFF
    match mode:
        case AquareaExtendedOperationMode.HEAT:
            return HVACMode.HEAT
        case AquareaExtendedOperationMode.COOL:
            return HVACMode.COOL
        case AquareaExtendedOperationMode.AUTO_COOL:
            return HVACMode.HEAT_COOL
        case AquareaExtendedOperationMode.AUTO_HEAT:
            return HVACMode.HEAT_COOL
    return HVACMode.OFF


def convert_aquarea_action_to_hvac_action(action: AquareaDeviceAction) -> HVACAction:
    """Convert device action to HVAC action."""
    match action:
        case AquareaDeviceAction.COOLING:
            return HVACAction.COOLING
        case AquareaDeviceAction.HEATING:
            return HVACAction.HEATING
    return HVACAction.IDLE


def convert_hvac_mode_to_aquarea_operation_mode(
    mode: HVACMode,
) -> AquareaUpdateOperationMode:
    """Convert HVAC mode to update operation mode."""
    match mode:
        case HVACMode.HEAT:
            return AquareaUpdateOperationMode.HEAT
        case HVACMode.COOL:
            return AquareaUpdateOperationMode.COOL
        case HVACMode.HEAT_COOL:
            return AquareaUpdateOperationMode.AUTO
    return AquareaUpdateOperationMode.OFF


def _get_hvac_action_from_device_direction(
    direction: AquareaDeviceDirection, hvac_mode: HVACMode
) -> HVACAction:
    """Convert device direction to HVAC action, using hvac_mode for context."""
    if direction == AquareaDeviceDirection.PUMP:
        if hvac_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
    return HVACAction.IDLE


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic climate entities."""
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]
    use_panasonic_preset_names = entry.options.get(
        CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES
    )
    for coordinator in data_coordinators:
        entities.append(
            PanasonicClimateEntity(
                coordinator, PANASONIC_CLIMATE_DESCRIPTION, use_panasonic_preset_names
            )
        )
    for aquarea_coordinator in aquarea_coordinators:
        for zone_id in aquarea_coordinator.device.zones:
            zone = aquarea_coordinator.device.zones.get(zone_id)
            if zone is None:
                continue
            entities.append(
                AquareaClimateEntity(
                    aquarea_coordinator,
                    AquareaClimateEntityDescription(
                        zone_id=zone_id,
                        name=zone.name,
                        key=f"zone-{zone_id}-climate",
                        translation_key=f"zone-{zone_id}-climate",
                    ),
                )
            )
    platform = entity_platform.current_platform.get()
    if platform is not None:
        platform.async_register_entity_service(
            SERVICE_SET_SWING_LR_MODE,
            {vol.Required("swing_mode"): cv.string},
            "async_set_horizontal_swing_mode",
        )
    async_add_entities(entities)


class PanasonicClimateEntity(PanasonicDataEntity, ClimateEntity):
    """Representation of a Panasonic Climate Device."""

    entity_description: PanasonicClimateEntityDescription

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_supported_features = SUPPORT_FLAGS
    _attr_fan_modes = [f.name for f in constants.FanSpeed]
    _attr_translation_key = "climate"
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_action = None
    _attr_preset_mode = PRESET_NONE
    _attr_fan_mode = None
    _attr_swing_mode = None
    _attr_swing_horizontal_mode = None

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicClimateEntityDescription,
        use_panasonic_preset_names: bool,
    ) -> None:
        """Initialize the climate entity."""
        self.entity_description = description
        device = coordinator.device
        hvac_modes = [HVACMode.OFF]
        if device.features.auto_mode:
            hvac_modes.append(HVACMode.HEAT_COOL)
        if device.features.cool_mode:
            hvac_modes.append(HVACMode.COOL)
        if device.features.dry_mode:
            hvac_modes.append(HVACMode.DRY)
        hvac_modes.append(HVACMode.FAN_ONLY)
        if device.features.heat_mode:
            hvac_modes.append(HVACMode.HEAT)
        self._attr_hvac_modes = hvac_modes

        self._quiet_preset = (
            PRESET_QUIET if use_panasonic_preset_names else PRESET_ECO
        )
        self._powerful_preset = (
            PRESET_POWERFUL if use_panasonic_preset_names else PRESET_BOOST
        )

        preset_modes = [PRESET_NONE]
        if device.features.quiet_mode:
            preset_modes.append(self._quiet_preset)
        if device.features.powerful_mode:
            preset_modes.append(self._powerful_preset)
        if device.features.summer_house > 0:
            preset_modes.append(PRESET_8_15)
        self._attr_preset_modes = preset_modes

        self._attr_swing_modes = [
            opt.name
            for opt in constants.AirSwingUD
            if opt != constants.AirSwingUD.Swing or device.features.auto_swing_ud
        ]

        if device.has_horizontal_swing:
            self._attr_supported_features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
            self._attr_swing_horizontal_modes = [
                opt.name
                for opt in constants.AirSwingLR
                if opt != constants.AirSwingLR.Unavailable
            ]

        super().__init__(coordinator, description.key)
        _LOGGER.info("Registering Climate entity: '%s'", self._attr_unique_id)

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        state = self.coordinator.device.parameters
        self._attr_hvac_mode = (
            HVACMode.OFF
            if state.power == constants.Power.Off
            else convert_operation_mode_to_hvac_mode(
                state.mode,
                state.iautox_mode == constants.IAutoXMode.On,
            )
        )

        self._set_temp_range()
        self._attr_current_temperature = state.inside_temperature
        self._attr_target_temperature = state.target_temperature
        self._attr_fan_mode = state.fan_speed.name
        self._attr_swing_mode = state.vertical_swing_mode.name
        if self.coordinator.device.has_horizontal_swing:
            self._attr_swing_horizontal_mode = state.horizontal_swing_mode.name

        if self.coordinator.device.in_summer_house_mode:
            self._attr_preset_mode = PRESET_8_15
        elif state.eco_mode == constants.EcoMode.Quiet:
            self._attr_preset_mode = self._quiet_preset
        elif state.eco_mode == constants.EcoMode.Powerful:
            self._attr_preset_mode = self._powerful_preset
        else:
            self._attr_preset_mode = PRESET_NONE
        if self.coordinator.device.has_inside_temperature:
            self._attr_hvac_action = convert_state_to_hvac_action(state)

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
        default_preset = PRESET_NONE
        if builder.target_temperature:
            self._attr_target_temperature = builder.target_temperature
            if builder.target_temperature > 15 and self._attr_preset_mode == PRESET_8_15:
                self._attr_preset_mode = default_preset
            elif builder.target_temperature < 15 and self._attr_preset_mode != PRESET_8_15:
                self._attr_preset_mode = default_preset = PRESET_8_15

        if builder.eco_mode:
            if builder.eco_mode.name in (PRESET_QUIET, PRESET_ECO):
                self._attr_preset_mode = self._quiet_preset
            elif builder.eco_mode.name in (PRESET_POWERFUL, PRESET_BOOST):
                self._attr_preset_mode = self._powerful_preset
            else:
                self._attr_preset_mode = default_preset

        if builder.fan_speed:
            self._attr_fan_mode = builder.fan_speed.name
        if builder.vertical_swing:
            self._attr_swing_mode = builder.vertical_swing.name
        if builder.horizontal_swing:
            self._attr_swing_horizontal_mode = builder.horizontal_swing.name
        if builder.hvac_mode:
            self._attr_hvac_mode = convert_operation_mode_to_hvac_mode(builder.hvac_mode, False)
        self.async_write_ha_state()

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

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
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

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if self.fan_modes is None or fan_mode not in self.fan_modes:
            raise ValueError(f"Unsupported fan_mode '{fan_mode}'")

        builder = self.coordinator.get_change_request_builder()
        builder.set_fan_speed(fan_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)

    async def _async_enter_summer_house_mode(self, builder: ChangeRequestBuilder):
        """Enter summer house mode."""
        device = self.coordinator.device
        stored_data = await self.coordinator.async_get_stored_data()

        stored_data["mode"] = device.parameters.mode.value
        stored_data["ecoMode"] = device.parameters.eco_mode.value
        stored_data["targetTemperature"] = device.parameters.target_temperature
        stored_data["fanSpeed"] = device.parameters.fan_speed.value
        await self.coordinator.async_store_data(stored_data)

        builder.set_hvac_mode(constants.OperationMode.Heat)
        builder.set_eco_mode(constants.EcoMode.Powerful)
        builder.set_target_temperature(8)
        builder.set_fan_speed(constants.FanSpeed.High)

        self._attr_min_temp = 8
        self._attr_max_temp = 15 if device.features.summer_house == 2 else 10

    async def _async_exit_summer_house_mode(self, builder: ChangeRequestBuilder):
        """Exit summer house mode."""
        self._attr_min_temp = 16
        self._attr_max_temp = 30
        if not self.coordinator.device.in_summer_house_mode:
            return
        stored_data = await self.coordinator.async_get_stored_data()
        try:
            hvac_mode = constants.OperationMode(stored_data["mode"]) if "mode" in stored_data else constants.OperationMode.Heat
        except Exception:
            hvac_mode = constants.OperationMode.Heat
        try:
            eco_mode = constants.EcoMode(stored_data["ecoMode"]) if "ecoMode" in stored_data else constants.EcoMode.Auto
        except Exception:
            eco_mode = constants.EcoMode.Auto
        target_temperature = stored_data["targetTemperature"] if "targetTemperature" in stored_data else 20
        try:
            fan_speed = constants.FanSpeed(stored_data["fanSpeed"]) if "fanSpeed" in stored_data else constants.FanSpeed.Auto
        except Exception:
            fan_speed = constants.FanSpeed.Auto

        builder.set_hvac_mode(hvac_mode)
        builder.set_eco_mode(eco_mode)
        builder.set_target_temperature(target_temperature)
        builder.set_fan_speed(fan_speed)

    async def async_set_preset_mode(self, preset_mode: str | None) -> None:
        """Set new preset mode."""
        if preset_mode is None:
            return
        if self.preset_modes is None or preset_mode not in self.preset_modes:
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
        await self.coordinator.async_apply_changes(builder)
        await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        if self.swing_modes is None or swing_mode not in self.swing_modes:
            raise ValueError(f"Unsupported swing mode '{swing_mode}'")

        builder = self.coordinator.get_change_request_builder()
        builder.set_vertical_swing(swing_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new horizontal swing mode."""
        if self.swing_horizontal_modes is None or swing_horizontal_mode not in self.swing_horizontal_modes:
            raise ValueError(f"Unsupported swing mode '{swing_horizontal_mode}'")

        builder = self.coordinator.get_change_request_builder()
        builder.set_horizontal_swing(swing_horizontal_mode)
        await self.coordinator.async_apply_changes(builder)
        self._update_attributes(builder)


class AquareaClimateEntity(AquareaDataEntity, ClimateEntity):
    """Representation of an Aquarea Climate Device."""

    entity_description: AquareaClimateEntityDescription

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_precision = PRECISION_WHOLE
    _attr_hvac_mode = HVACMode.OFF

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: AquareaClimateEntityDescription,
    ) -> None:
        """Initialize the climate entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

        # Set supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )

        # Add preset mode support if device supports special status
        if coordinator.device.support_special_status:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(AQUAREA_SPECIAL_STATUS_LOOKUP.keys())
            self._attr_preset_mode = PRESET_NONE

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        device = self.coordinator.device
        zone = device.zones.get(self.entity_description.zone_id)

        if zone is None or zone.operation_status == AquareaZoneOperationStatus.OFF:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
            self._attr_target_temperature = None
            self._attr_min_temp = 5
            self._attr_max_temp = 65
            if device.support_special_status:
                self._attr_preset_mode = AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP.get(
                    device.special_status, PRESET_NONE
                )
            return

        # Mode is at device level, not zone level
        self._attr_hvac_mode = convert_mode_and_status_to_hvac_mode(
            device.mode, zone.operation_status
        )

        # Use device direction for more accurate HVAC action
        self._attr_hvac_action = _get_hvac_action_from_device_direction(
            device.current_direction, self._attr_hvac_mode
        )

        self._attr_current_temperature = zone.temperature

        # Target temperature depends on the current mode (heat or cool)
        if device.mode in (
            AquareaExtendedOperationMode.HEAT,
            AquareaExtendedOperationMode.AUTO_HEAT,
        ):
            self._attr_target_temperature = zone.heat_target_temperature
            self._attr_min_temp = zone.heat_min if zone.heat_min is not None else 5
            self._attr_max_temp = zone.heat_max if zone.heat_max is not None else 65
        else:
            self._attr_target_temperature = zone.cool_target_temperature
            self._attr_min_temp = zone.cool_min if zone.cool_min is not None else 5
            self._attr_max_temp = zone.cool_max if zone.cool_max is not None else 65

        # Build HVAC modes list based on zone capabilities
        hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if zone.cool_mode:
            hvac_modes.append(HVACMode.COOL)
            hvac_modes.append(HVACMode.HEAT_COOL)
        self._attr_hvac_modes = hvac_modes

        # Update preset mode if supported
        if device.support_special_status:
            self._attr_preset_mode = AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP.get(
                device.special_status, PRESET_NONE
            )

    async def _schedule_refresh(self, delay: float = AQUAREA_CLIMATE_DELAY_SHORT) -> None:
        """Schedule a coordinator refresh after a short delay."""
        await asyncio.sleep(delay)
        try:
            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception(
                "Delayed refresh failed for device %s",
                self.coordinator.device.device_id,
            )

    async def async_turn_on(self) -> None:
        """Turn the climate entity on."""
        await self.coordinator.device.turn_on()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        await self.coordinator.device.turn_off()
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        operation_mode = convert_hvac_mode_to_aquarea_operation_mode(hvac_mode)
        await self.coordinator.device.set_mode(
            mode=operation_mode,
            zone_id=self.entity_description.zone_id,
        )
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            target_temp = kwargs[ATTR_TEMPERATURE]
            await self.coordinator.device.set_temperature(
                temperature=target_temp,
                zone_id=self.entity_description.zone_id,
            )
        if mode := kwargs.get(ATTR_HVAC_MODE):
            await self.async_set_hvac_mode(mode)
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if not self.coordinator.device.support_special_status:
            return
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset_mode '{preset_mode}'")
        special_status = AQUAREA_SPECIAL_STATUS_LOOKUP.get(preset_mode)
        _LOGGER.debug(
            "Setting preset mode of device %s to %s (special_status=%s)",
            self.coordinator.device.device_id,
            preset_mode,
            special_status,
        )
        await self.coordinator.device.set_special_status(special_status)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))
