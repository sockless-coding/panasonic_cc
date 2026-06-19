"""Aquarea switch entities."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aioaquarea

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)

from ..const import DOMAIN
from .base import AquareaDataEntity
from .coordinator import AquareaDeviceCoordinator
from .const import AQUAREA_COORDINATORS, AQUAREA_SWITCH_DELAY

_LOGGER = logging.getLogger(__name__)


class AquareaBaseSwitch(AquareaDataEntity, SwitchEntity):
    """Base class for Aquarea switches with optimistic updates."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _optimistic_is_on: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return the switch state."""
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        return self._get_is_on()

    def _get_is_on(self) -> bool:
        """Override in subclass to return the actual state from the device."""
        raise NotImplementedError

    async def _schedule_refresh(self, delay: float = AQUAREA_SWITCH_DELAY) -> None:
        """Schedule a coordinator refresh after a short delay."""
        await asyncio.sleep(delay)
        self._optimistic_is_on = None
        try:
            await self.coordinator.async_request_refresh()
        except aioaquarea.RequestFailedError:
            _LOGGER.exception(
                "Delayed refresh failed for device %s",
                self.coordinator.device.device_id,
            )


class AquareaForceDHWSwitch(AquareaBaseSwitch):
    """Switch to force DHW (domestic hot water) mode on Aquarea devices."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "force_dhw")
        self._attr_translation_key = "force_dhw"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    def _get_is_on(self) -> bool:
        return self.coordinator.device.force_dhw is aioaquarea.ForceDHW.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Force DHW."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.device.set_force_dhw(aioaquarea.ForceDHW.ON)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Force DHW."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.device.set_force_dhw(aioaquarea.ForceDHW.OFF)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""


class AquareaForceHeaterSwitch(AquareaBaseSwitch):
    """Switch to force heater mode on Aquarea devices."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "force_heater")
        self._attr_translation_key = "force_heater"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:hvac" if self.is_on else "mdi:hvac-off"

    def _get_is_on(self) -> bool:
        return self.coordinator.device.force_heater is aioaquarea.ForceHeater.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Force Heater."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.device.set_force_heater(aioaquarea.ForceHeater.ON)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Force Heater."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.device.set_force_heater(aioaquarea.ForceHeater.OFF)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""


class AquareaHolidayTimerSwitch(AquareaBaseSwitch):
    """Switch to enable/disable the holiday timer on Aquarea devices."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "holiday_timer")
        self._attr_translation_key = "holiday_timer"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:timer-check" if self.is_on else "mdi:timer-off"

    def _get_is_on(self) -> bool:
        return self.coordinator.device.holiday_timer is aioaquarea.HolidayTimer.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Holiday Timer."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.device.set_holiday_timer(aioaquarea.HolidayTimer.ON)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Holiday Timer."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.device.set_holiday_timer(aioaquarea.HolidayTimer.OFF)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Aquarea switches."""
    devices = []
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][
        AQUAREA_COORDINATORS
    ]

    for coordinator in aquarea_coordinators:
        if coordinator.device.has_tank:
            devices.append(AquareaForceDHWSwitch(coordinator))
        devices.append(AquareaForceHeaterSwitch(coordinator))
        devices.append(AquareaHolidayTimerSwitch(coordinator))

    async_add_entities(devices)
