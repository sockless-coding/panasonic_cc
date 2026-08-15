"""Aquarea climate entities."""
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
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

from aio_panasonic_comfort_cloud.constants import (
    AquareaOperationMode,
    AquareaOperationStatus,
    AquareaUpdateOperationMode,
    AquareaSpecialStatus,
    AquareaDeviceDirection,
)
from aio_panasonic_comfort_cloud.models.aquarea import AquareaZoneStatus

from ..const import DOMAIN, PRESET_ECO, PRESET_NONE
from .base import AquareaDataEntity
from .coordinator import AquareaDeviceCoordinator
from .const import AQUAREA_COORDINATORS, AQUAREA_CLIMATE_DELAY_SHORT, AQUAREA_CLIMATE_DELAY_LONG

_LOGGER = logging.getLogger(__name__)

AQUAREA_SPECIAL_STATUS_LOOKUP: dict[str, AquareaSpecialStatus | None] = {
    PRESET_ECO: AquareaSpecialStatus.Eco,
    "comfort": AquareaSpecialStatus.Comfort,
    PRESET_NONE: None,
}
AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP = {v: k for k, v in AQUAREA_SPECIAL_STATUS_LOOKUP.items()}


def zone_supports_special_status(zone: AquareaZoneStatus) -> bool:
    """Whether this zone reports Eco/Comfort setpoint offsets at all."""
    return any(
        value is not None
        for value in (zone.eco_heat, zone.eco_cool, zone.comfort_heat, zone.comfort_cool)
    )


@dataclass(frozen=True, kw_only=True)
class AquareaClimateEntityDescription(ClimateEntityDescription):
    """Describes an Aquarea climate entity."""

    zone_id: int


def convert_mode_and_status_to_hvac_mode(
    mode: AquareaOperationMode,
    zone_status: AquareaOperationStatus,
) -> HVACMode:
    """Convert mode and status to HVAC mode."""
    if zone_status == AquareaOperationStatus.Off:
        return HVACMode.OFF
    match mode:
        case AquareaOperationMode.Heat:
            return HVACMode.HEAT
        case AquareaOperationMode.Cool:
            return HVACMode.COOL
        case AquareaOperationMode.AutoCool:
            return HVACMode.HEAT_COOL
        case AquareaOperationMode.AutoHeat:
            return HVACMode.HEAT_COOL
    return HVACMode.OFF


def convert_hvac_mode_to_aquarea_operation_mode(
    mode: HVACMode,
) -> AquareaUpdateOperationMode:
    """Convert HVAC mode to update operation mode."""
    match mode:
        case HVACMode.HEAT:
            return AquareaUpdateOperationMode.Heat
        case HVACMode.COOL:
            return AquareaUpdateOperationMode.Cool
        case HVACMode.HEAT_COOL:
            return AquareaUpdateOperationMode.Auto
    return AquareaUpdateOperationMode.Off


def _get_hvac_action_from_device_direction(
    direction: AquareaDeviceDirection, hvac_mode: HVACMode
) -> HVACAction:
    """Convert device direction to HVAC action, using hvac_mode for context."""
    if direction == AquareaDeviceDirection.Pump:
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
        zone = self.coordinator.device.parameters.get_zone(description.zone_id)
        self._attr_name = zone.name if zone else None
        self._attr_unique_id = f"{super().unique_id}_climate_{description.zone_id}"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if zone is not None and zone_supports_special_status(zone):
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(AQUAREA_SPECIAL_STATUS_LOOKUP.keys())
            self._attr_preset_mode = AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP.get(
                self.coordinator.device.parameters.special_status, PRESET_NONE
            )
        self._attr_precision = PRECISION_WHOLE
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        if zone and zone.supports_cooling:
            self._attr_hvac_modes.extend([HVACMode.COOL, HVACMode.HEAT_COOL])
        self._attr_hvac_mode = HVACMode.OFF

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        self.async_write_ha_state()

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        params = self.coordinator.device.parameters
        zone = params.get_zone(self.entity_description.zone_id)

        if zone is None or zone.operation_status == AquareaOperationStatus.Off:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
            self._attr_target_temperature = None
            self._attr_min_temp = 5
            self._attr_max_temp = 65
            if zone is not None and zone_supports_special_status(zone):
                self._attr_preset_mode = AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP.get(
                    params.special_status, PRESET_NONE
                )
            return

        self._attr_hvac_mode = convert_mode_and_status_to_hvac_mode(
            params.operation_mode, zone.operation_status
        )

        self._attr_hvac_action = _get_hvac_action_from_device_direction(
            params.direction, self._attr_hvac_mode
        )

        self._attr_current_temperature = zone.temperature

        if params.operation_mode in (
            AquareaOperationMode.Heat,
            AquareaOperationMode.AutoHeat,
        ):
            self._attr_target_temperature = zone.heat_set
            self._attr_min_temp = zone.heat_min if zone.heat_min is not None else 5
            self._attr_max_temp = zone.heat_max if zone.heat_max is not None else 65
        else:
            self._attr_target_temperature = zone.cool_set
            self._attr_min_temp = zone.cool_min if zone.cool_min is not None else 5
            self._attr_max_temp = zone.cool_max if zone.cool_max is not None else 65

        hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if zone.supports_cooling:
            hvac_modes.append(HVACMode.COOL)
            hvac_modes.append(HVACMode.HEAT_COOL)
        self._attr_hvac_modes = hvac_modes

        if zone_supports_special_status(zone):
            self._attr_preset_mode = AQUAREA_SPECIAL_STATUS_REVERSE_LOOKUP.get(
                params.special_status, PRESET_NONE
            )

    async def _schedule_refresh(self, delay: float = AQUAREA_CLIMATE_DELAY_SHORT) -> None:
        """Schedule a coordinator refresh after a short delay."""
        await asyncio.sleep(delay)
        try:
            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception(
                "Delayed refresh failed for device %s",
                self.coordinator.device_id,
            )

    async def async_turn_on(self) -> None:
        """Turn the climate entity's zone on."""
        await self.coordinator.api_client.set_aquarea_zone_operation_status(
            self.coordinator.info, self.entity_description.zone_id, AquareaOperationStatus.On
        )
        params = self.coordinator.device.parameters
        zone = params.get_zone(self.entity_description.zone_id)
        if zone is not None:
            self._attr_hvac_mode = convert_mode_and_status_to_hvac_mode(
                params.operation_mode, AquareaOperationStatus.On
            )
        else:
            self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_turn_off(self) -> None:
        """Turn the climate entity's zone off."""
        await self.coordinator.api_client.set_aquarea_zone_operation_status(
            self.coordinator.info, self.entity_description.zone_id, AquareaOperationStatus.Off
        )
        self._attr_hvac_mode = HVACMode.OFF
        self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        operation_mode = convert_hvac_mode_to_aquarea_operation_mode(hvac_mode)
        await self.coordinator.api_client.set_aquarea_operation_mode(
            self.coordinator.info, operation_mode
        )
        await self.coordinator.api_client.set_aquarea_zone_operation_status(
            self.coordinator.info, self.entity_description.zone_id, AquareaOperationStatus.On
        )
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        state_changed = False
        if ATTR_TEMPERATURE in kwargs:
            target_temp = kwargs[ATTR_TEMPERATURE]
            operation_mode = self.coordinator.device.parameters.operation_mode
            mode = "heat" if operation_mode in (AquareaOperationMode.Heat, AquareaOperationMode.AutoHeat) else "cool"
            await self.coordinator.api_client.set_aquarea_zone_temperature(
                self.coordinator.info,
                self.entity_description.zone_id,
                int(target_temp),
                mode=mode,
            )
            self._attr_target_temperature = target_temp
            state_changed = True
        if mode := kwargs.get("hvac_mode"):
            await self.async_set_hvac_mode(mode)
        if state_changed:
            self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset_mode '{preset_mode}'")
        special_status = AQUAREA_SPECIAL_STATUS_LOOKUP.get(preset_mode)
        _LOGGER.debug(
            "Setting preset mode of device %s to %s (special_status=%s)",
            self.coordinator.device_id,
            preset_mode,
            special_status,
        )
        await self.coordinator.api_client.set_aquarea_special_status(
            self.coordinator.device, special_status
        )
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh(AQUAREA_CLIMATE_DELAY_LONG))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Aquarea climate entities."""
    entities = []
    aquarea_coordinators = hass.data[DOMAIN][AQUAREA_COORDINATORS]
    for aquarea_coordinator in aquarea_coordinators:
        for zone in aquarea_coordinator.device.parameters.zones:
            entities.append(
                AquareaClimateEntity(
                    aquarea_coordinator,
                    AquareaClimateEntityDescription(
                        zone_id=zone.id,
                        name=zone.name,
                        key=f"zone-{zone.id}-climate",
                        translation_key=f"zone-{zone.id}-climate",
                    ),
                )
            )
    async_add_entities(entities)
