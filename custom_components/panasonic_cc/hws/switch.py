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

from aio_panasonic_comfort_cloud.constants import AquareaOperationStatus

from ..const import DOMAIN
from .base import HwsDataEntity
from .coordinator import HwsDeviceCoordinator
from .const import HWS_COORDINATORS, HWS_SWITCH_DELAY

_LOGGER = logging.getLogger(__name__)


class HwsBoostModeSwitch(HwsDataEntity, SwitchEntity):
    """Switch to enable/disable boost mode on HWS devices.

    Uses the library's ``set_hws_boost_mode`` setter, which its own
    docstrings call "unverified/best-effort" — the write endpoint is
    confirmed only from an app capture, not tested against a real device.
    """

    _attr_device_class = SwitchDeviceClass.SWITCH
    _optimistic_is_on: bool | None = None

    def __init__(self, coordinator: HwsDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "boost_mode")
        self._attr_translation_key = "boost_mode"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    @property
    def is_on(self) -> bool:
        """Return the switch state."""
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        return self.coordinator.device.parameters.boost_mode is AquareaOperationStatus.On

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on boost mode."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.api_client.set_hws_boost_mode(self.coordinator.info, AquareaOperationStatus.On)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off boost mode."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.api_client.set_hws_boost_mode(self.coordinator.info, AquareaOperationStatus.Off)
        self.hass.async_create_task(self._schedule_refresh())

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

    async_add_entities(entities)
