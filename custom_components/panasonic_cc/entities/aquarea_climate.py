"""Aquarea climate entity."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityDescription,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE, PRECISION_WHOLE
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.core import callback

from ..base import AquareaDataEntity
from ..coordinator import AquareaDeviceCoordinator
from aioaquarea import (
    ExtendedOperationMode as AquareaExtendedOperationMode,
    OperationStatus as AquareaZoneOperationStatus,
    DeviceAction as AquareaDeviceAction,
    UpdateOperationMode as AquareaUpdateOperationMode,
    SpecialStatus as AquareaSpecialStatus,
    DeviceDirection as AquareaDeviceDirection,
)

from ..const import (
    PRESET_ECO,
    PRESET_NONE,
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
class AquareaClimateEntityDescription(ClimateEntityDescription):
    """Describes an Aquarea climate entity."""

    zone_id: int


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


class AquareaClimateEntity(AquareaDataEntity, ClimateEntity):
    """Representation of an Aquarea Climate Device."""

    entity_description: AquareaClimateEntityDescription

    _attr_target_temperature_step = 1

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: AquareaClimateEntityDescription,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        zone = self.coordinator.device.zones.get(description.zone_id)
        self._attr_name = zone.name if zone else None
        self._attr_unique_id = f"{super().unique_id}_climate_{description.zone_id}"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if self.coordinator.device.support_special_status:
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(AQUAREA_SPECIAL_STATUS_LOOKUP.keys())
            self._attr_preset_mode = AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP.get(
                self.coordinator.device.special_status, PRESET_NONE
            )
        self._attr_precision = PRECISION_WHOLE
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        if zone and zone.cool_mode:
            self._attr_hvac_modes.extend([HVACMode.COOL, HVACMode.HEAT_COOL])
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        if zone and zone.cool_mode:
            self._attr_hvac_modes.extend([HVACMode.COOL, HVACMode.HEAT_COOL])
        self._attr_hvac_mode = HVACMode.OFF

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
        if mode := kwargs.get("hvac_mode"):
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
