"""HWS (standalone Heat Pump Hot Water tank) water heater entities."""
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature, PRECISION_WHOLE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from aio_panasonic_comfort_cloud import HwsDailySettings, HwsDevice
from aio_panasonic_comfort_cloud.constants import HwsOperationMode
from aio_panasonic_comfort_cloud.exceptions import DeviceIsNotReadyError

from ..const import DOMAIN
from .base import HwsDataEntity
from .coordinator import HwsDeviceCoordinator
from .const import HWS_COORDINATORS, HWS_WATER_HEATER_DELAY

_LOGGER = logging.getLogger(__name__)

OPERATION_MODE_LOOKUP = {
    "schedule": HwsOperationMode.Schedule,
    "pv_timer": HwsOperationMode.PVTimer,
    "holiday": HwsOperationMode.Holiday,
}

OPERATION_MODE_REVERSE_LOOKUP = {v: k for k, v in OPERATION_MODE_LOOKUP.items()}


@dataclass(frozen=True, kw_only=True)
class HwsWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Describes an HWS Water Heater entity."""


HWS_WATER_TANK_DESCRIPTION = HwsWaterHeaterEntityDescription(
    key="tank",
    translation_key="tank",
    name="Tank",
)


def _supported_operation_modes(device: HwsDevice) -> list[HwsOperationMode]:
    """Return the operation modes the device reports support for.

    A capability flag that's missing from the status response is treated as
    supported, and the current mode is always included.
    """
    capabilities = device.device_parameters
    supported = {
        HwsOperationMode.Schedule: capabilities.weekly_mode,
        HwsOperationMode.PVTimer: capabilities.pv_mode,
        HwsOperationMode.Holiday: capabilities.holiday_mode,
    }
    current = device.parameters.operation_mode
    return [mode for mode, flag in supported.items() if flag is not False or mode == current]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the HWS water heater."""
    entities = []
    hws_coordinators: list[HwsDeviceCoordinator] = hass.data[DOMAIN][HWS_COORDINATORS]
    for coordinator in hws_coordinators:
        entities.append(HwsWaterHeater(coordinator, HWS_WATER_TANK_DESCRIPTION))
    async_add_entities(entities)


class HwsWaterHeater(HwsDataEntity, WaterHeaterEntity):
    """Representation of an HWS hot water tank.

    The API has no tank setpoint to write; heating is driven by the weekly
    schedule (or PV signal / holiday mode), so the entity exposes the tank
    temperature, the operation mode and the schedule itself.
    """

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE

    def __init__(
        self,
        coordinator: HwsDeviceCoordinator,
        description: HwsWaterHeaterEntityDescription,
    ) -> None:
        """Initialize the water heater entity."""
        self.entity_description = description
        self._optimistic_operation: str | None = None
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        device = self.coordinator.device
        params = device.parameters
        self._attr_current_temperature = params.tank_temperature

        modes = _supported_operation_modes(device)
        self._attr_operation_list = [OPERATION_MODE_REVERSE_LOOKUP[mode] for mode in modes]
        features = WaterHeaterEntityFeature.OPERATION_MODE
        if HwsOperationMode.Holiday in modes:
            features |= WaterHeaterEntityFeature.AWAY_MODE
        self._attr_supported_features = features

        if self._optimistic_operation is not None:
            self._attr_current_operation = self._optimistic_operation
        else:
            self._attr_current_operation = OPERATION_MODE_REVERSE_LOOKUP.get(params.operation_mode)
        self._attr_is_away_mode_on = self._attr_current_operation == "holiday"

        attrs: dict[str, Any] = {}
        if params.weekly_settings:
            attrs["weekly_schedule"] = [day.to_dict() for day in params.weekly_settings]
        try:
            limits = device.device_parameters.limits
        except DeviceIsNotReadyError:
            limits = None
        if limits is not None:
            attrs["temperature_setting_limits"] = {
                "set1_end_temperature": limits.set1_end_temperature,
                "set2_start_temperature_min": limits.set2_start_temperature_min,
                "set2_start_temperature_max": limits.set2_start_temperature_max,
                "set2_end_temperature_min": limits.set2_end_temperature_min,
                "set2_end_temperature_max": limits.set2_end_temperature_max,
            }
        self._attr_extra_state_attributes = attrs

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        if (mode := OPERATION_MODE_LOOKUP.get(operation_mode)) is None:
            raise ServiceValidationError(f"Unsupported operation mode '{operation_mode}'")
        await self.coordinator.api_client.set_hws_operation_mode(self.coordinator.info, mode)
        self._optimistic_operation = operation_mode
        self._async_update_attrs()
        self.async_write_ha_state()
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_away_mode_on(self) -> None:
        """Switch to holiday mode."""
        await self.async_set_operation_mode("holiday")

    async def async_turn_away_mode_off(self) -> None:
        """Leave holiday mode by going back to the schedule."""
        await self.async_set_operation_mode("schedule")

    async def async_set_hws_weekly_schedule(self, weekly_schedule: list[dict[str, Any]]) -> None:
        """Replace the weekly schedule.

        Takes the same shape as the ``weekly_schedule`` attribute, so it can be
        copied, edited and sent back.
        """
        days = [HwsDailySettings(day) for day in weekly_schedule]
        try:
            await self.coordinator.api_client.async_set_hws_weekly_settings(self.coordinator.info, days)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        except Exception as err:
            raise HomeAssistantError(f"Failed to set the weekly schedule: {err}") from err
        self.hass.async_create_task(self._schedule_refresh())

    async def _schedule_refresh(self, delay: float = HWS_WATER_HEATER_DELAY) -> None:
        """Clear optimistic state and refresh the coordinator after a short delay."""
        await asyncio.sleep(delay)
        self._optimistic_operation = None
        try:
            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception(
                "Delayed refresh failed for device %s",
                self.coordinator.device_id,
            )
