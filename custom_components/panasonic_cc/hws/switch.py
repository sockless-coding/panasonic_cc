"""HWS (standalone Heat Pump Hot Water tank) switch entities."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
)

from aio_panasonic_comfort_cloud.constants import (
    HwsBoostModeSettings,
    HwsOperationModeSettings,
    HwsOperationStatus,
)


from ..const import DOMAIN
from .base import HwsDataEntity
from .coordinator import HwsDeviceCoordinator
from .const import HWS_COORDINATORS, HWS_SWITCH_DELAY

_LOGGER = logging.getLogger(__name__)


class HwsBaseSwitch(HwsDataEntity, SwitchEntity):
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

    async def _schedule_refresh(self, delay: float = HWS_SWITCH_DELAY) -> None:
        """Schedule a coordinator refresh after a short delay."""
        await asyncio.sleep(delay)
        self._optimistic_is_on = None
        try:
            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception(
                "Delayed refresh failed for device %s",
                self.coordinator.device_id,
            )


class HwsBoostModeSwitch(HwsBaseSwitch):
    """Switch to enable/disable boost mode on HWS devices.

    Uses the library's ``set_hws_boost_mode`` setter, which is a POST request to the /hphw/setBoostMode endpoint.
    """

    def __init__(self, coordinator: HwsDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "boost_mode")
        self._attr_translation_key = "boost_mode"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    def _get_is_on(self) -> bool:
        return self.coordinator.device.parameters.boost_mode is HwsBoostModeSettings.On

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on boost mode."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.api_client.set_hws_boost_mode(
            self.coordinator.info, HwsBoostModeSettings.On
        )
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off boost mode."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.api_client.set_hws_boost_mode(
            self.coordinator.info, HwsBoostModeSettings.Off
        )
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""


class HwsHolidayModeSwitch(HwsBaseSwitch):
    """Switch to enable/disable holiday mode on HWS devices.

    Uses the library's ``set_hws_holiday_mode`` setter, which is a POST request to the /hphw/  endpoint.
    """

    def __init__(self, coordinator: HwsDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "holiday_timer")
        self._attr_translation_key = "holiday_timer"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    def _get_is_on(self) -> bool:
        """Return the switch state."""
        return (
            self.coordinator.device.parameters.operation_mode
            is HwsOperationModeSettings.Holiday
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on holiday mode."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.api_client.set_hws_holiday_mode(self.coordinator.info)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off holiday mode."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.api_client.set_hws_schedule_mode(self.coordinator.info)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the HWS switches."""
    entities = []
    hws_coordinators: list[HwsDeviceCoordinator] = hass.data[DOMAIN][HWS_COORDINATORS]

    for coordinator in hws_coordinators:
        entities.append(HwsBoostModeSwitch(coordinator))
        entities.append(HwsHolidayModeSwitch(coordinator))

    async_add_entities(entities)
