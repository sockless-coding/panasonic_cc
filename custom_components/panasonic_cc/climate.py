from __future__ import annotations

from typing import Any
from dataclasses import dataclass
import logging

from homeassistant.core import HomeAssistant
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
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.components.climate.const import ClimateEntityFeature

from .base import PanasonicDataEntity, AquareaDataEntity
from .coordinator import PanasonicDeviceCoordinator, AquareaDeviceCoordinator
from aio_panasonic_comfort_cloud import PanasonicDeviceParameters, ChangeRequestBuilder, constants
from aioaquarea import (
    ExtendedOperationMode as AquareaExtendedOperationMode,
    OperationStatus as AquareaZoneOperationStatus,
    DeviceAction as AquareaDeviceAction,
    UpdateOperationMode as AquareaUpdateOperationMode,
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
)

_LOGGER = logging.getLogger(__name__)


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

    match state.mode:
        case constants.OperationMode.Auto:
            auto_diff = state.target_temperature - state.inside_temperature
            if auto_diff >= 1:
                return HVACAction.HEATING
            if auto_diff <= -1:
                return HVACAction.COOLING
            return HVACAction.IDLE
        case constants.OperationMode.Cool:
            return (
                HVACAction.COOLING
                if state.target_temperature < state.inside_temperature
                else HVACAction.IDLE
            )
        case constants.OperationMode.Dry:
            return HVACAction.DRYING
        case constants.OperationMode.Fan:
            return HVACAction.IDLE
        case constants.OperationMode.Heat:
            return (
                HVACAction.HEATING
                if state.target_temperature > state.inside_temperature
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
        CONF_USE_PANASONIC_PRESET_NAMES, True
    )
    for coordinator in data_coordinators:
        entities.append(
            PanasonicClimateEntity(
                coordinator, PANASONIC_CLIMATE_DESCRIPTION, use_panasonic_preset_names
            )
        )
    for aquarea_coordinator in aquarea_coordinators:
        for zone_id in aquarea_coordinator.device.zones:
            entities.append(
                AquareaClimateEntity(
                    aquarea_coordinator,
                    AquareaClimateEntityDescription(
                        zone_id=zone_id,
                        name=aquarea_coordinator.device.zones.get(zone_id).name,
                        key=f"zone-{zone_id}-climate",
                        translation_key=f"zone-{zone_id}-climate",
                    ),
                )
            )
    platform = entity_platform.current_platform.get()
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

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        builder = self.coordinator.get_change_request_builder()
        if hvac_mode == HVACMode.OFF:
            builder.set_power(constants.Power.Off)
        else:
            builder.set_power(constants.Power.On)
            operation_mode = convert_hvac_mode_to_operation_mode(hvac_mode)
            if operation_mode:
                builder.set_mode(operation_mode)
        await self.coordinator.async_apply_changes(builder)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_HVAC_MODE in kwargs:
            await self.async_set_hvac_mode(kwargs[ATTR_HVAC_MODE])
        if ATTR_TEMPERATURE in kwargs:
            builder = self.coordinator.get_change_request_builder()
            builder.set_target_temperature(kwargs[ATTR_TEMPERATURE])
            await self.coordinator.async_apply_changes(builder)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        builder = self.coordinator.get_change_request_builder()
        builder.set_fan_speed(fan_mode)
        await self.coordinator.async_apply_changes(builder)

    async def async_set_preset_mode(self, preset_mode: str | None) -> None:
        """Set new preset mode."""
        if preset_mode is None:
            return
        builder = self.coordinator.get_change_request_builder()
        if preset_mode == PRESET_8_15:
            builder.set_summer_house_mode(True)
        elif preset_mode == self._quiet_preset:
            builder.set_eco_mode(constants.EcoMode.Quiet)
        elif preset_mode == self._powerful_preset:
            builder.set_eco_mode(constants.EcoMode.Powerful)
        else:
            builder.set_eco_mode(constants.EcoMode.Off)
            if preset_mode == PRESET_8_15:
                builder.set_summer_house_mode(False)
        await self.coordinator.async_apply_changes(builder)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        builder = self.coordinator.get_change_request_builder()
        builder.set_vertical_swing(swing_mode)
        await self.coordinator.async_apply_changes(builder)

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new horizontal swing mode."""
        builder = self.coordinator.get_change_request_builder()
        builder.set_horizontal_swing(swing_horizontal_mode)
        await self.coordinator.async_apply_changes(builder)


class AquareaClimateEntity(AquareaDataEntity, ClimateEntity):
    """Representation of an Aquarea Climate Device."""

    entity_description: AquareaClimateEntityDescription

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_mode = HVACMode.OFF

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: AquareaClimateEntityDescription,
    ) -> None:
        """Initialize the climate entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        device = self.coordinator.device
        zone = device.zones.get(self.entity_description.zone_id)

        if zone is None or zone.operation_status == AquareaZoneOperationStatus.OFF:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
            return

        self._attr_hvac_mode = convert_mode_and_status_to_hvac_mode(
            zone.extended_operation_mode, zone.operation_status
        )
        self._attr_hvac_action = convert_aquarea_action_to_hvac_action(
            device.current_action
        )
        self._attr_current_temperature = zone.temperature
        self._attr_target_temperature = zone.target_temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        operation_mode = convert_hvac_mode_to_aquarea_operation_mode(hvac_mode)
        await self.coordinator.device.set_operation_mode(
            zone_id=self.entity_description.zone_id,
            update_operation_mode=operation_mode,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            target_temp = kwargs[ATTR_TEMPERATURE]
            await self.coordinator.device.set_target_temperature(
                zone_id=self.entity_description.zone_id,
                target_temperature=target_temp,
            )
