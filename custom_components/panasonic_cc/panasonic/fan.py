"""Panasonic fan entities."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
)
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from aio_panasonic_comfort_cloud import ChangeRequestBuilder, constants

from ..const import DOMAIN
from .base import PanasonicDataEntity
from .coordinator import PanasonicDeviceCoordinator
from .const import DATA_COORDINATORS

_LOGGER = logging.getLogger(__name__)

_FAN_SPEEDS = [f for f in constants.FanSpeed]
_SPEED_COUNT = len(_FAN_SPEEDS)


def _percentage_for_speed(speed: constants.FanSpeed) -> int:
    """Return the percentage value for a given fan speed."""
    if speed not in _FAN_SPEEDS:
        return 0
    idx = _FAN_SPEEDS.index(speed)
    return round((idx + 1) * 100 / _SPEED_COUNT)


def _speed_for_percentage(pct: int) -> constants.FanSpeed:
    """Return the nearest fan speed for a given percentage."""
    if pct <= 0:
        return _FAN_SPEEDS[0]
    idx = round(pct / 100 * _SPEED_COUNT) - 1
    idx = max(0, min(_SPEED_COUNT - 1, idx))
    return _FAN_SPEEDS[idx]


@dataclass(frozen=True, kw_only=True)
class PanasonicFanEntityDescription(FanEntityDescription):
    """Describes a Panasonic fan entity."""


PANASONIC_FAN_DESCRIPTION = PanasonicFanEntityDescription(
    key="fan",
    translation_key="fan",
)


class PanasonicFanEntity(PanasonicDataEntity, FanEntity):
    """Representation of a Panasonic fan entity."""

    entity_description: PanasonicFanEntityDescription

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = [f.name for f in _FAN_SPEEDS]
    _attr_speed_count = _SPEED_COUNT

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicFanEntityDescription,
    ) -> None:
        """Initialize the fan entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update attributes of the fan entity."""
        parameters = self.coordinator.device.parameters
        self._attr_is_on = parameters.power != constants.Power.Off
        fan_speed = parameters.fan_speed
        self._attr_percentage = _percentage_for_speed(fan_speed)
        self._attr_preset_mode = fan_speed.name

    @property
    def percentage(self) -> int | None:
        """Return the current percentage."""
        return self._attr_percentage

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._attr_preset_mode

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        return self._attr_is_on

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed by percentage."""
        try:
            speed = _speed_for_percentage(percentage)
            builder = self.coordinator.get_change_request_builder()
            builder.set_fan_speed(speed.name)
            await self.coordinator.async_apply_changes(builder)
            await self.coordinator.async_schedule_refresh()
            self._attr_percentage = _percentage_for_speed(speed)
            self._attr_preset_mode = speed.name
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception(
                "Failed to set fan percentage %s on device %s",
                percentage,
                self.coordinator.device_id,
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan speed by preset mode."""
        if self.preset_modes is None or preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset_mode '{preset_mode}'")

        try:
            builder = self.coordinator.get_change_request_builder()
            builder.set_fan_speed(preset_mode)
            await self.coordinator.async_apply_changes(builder)
            await self.coordinator.async_schedule_refresh()
            self._attr_preset_mode = preset_mode
            speed = next(
                (f for f in _FAN_SPEEDS if f.name == preset_mode), None
            )
            if speed is not None:
                self._attr_percentage = _percentage_for_speed(speed)
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception(
                "Failed to set fan preset mode %s on device %s",
                preset_mode,
                self.coordinator.device_id,
            )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        try:
            builder = self.coordinator.get_change_request_builder()
            builder.set_power_mode(constants.Power.On)
            if percentage is not None:
                speed = _speed_for_percentage(percentage)
                builder.set_fan_speed(speed.name)
            elif preset_mode is not None:
                builder.set_fan_speed(preset_mode)
            await self.coordinator.async_apply_changes(builder)
            await self.coordinator.async_schedule_refresh()
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception(
                "Failed to turn on fan on device %s",
                self.coordinator.device_id,
            )

    async def async_turn_off(self) -> None:
        """Turn off the fan."""
        try:
            builder = self.coordinator.get_change_request_builder()
            builder.set_power_mode(constants.Power.Off)
            await self.coordinator.async_apply_changes(builder)
            await self.coordinator.async_schedule_refresh()
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception(
                "Failed to turn off fan on device %s",
                self.coordinator.device_id,
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic fan entities."""
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][
        DATA_COORDINATORS
    ]
    for coordinator in data_coordinators:
        entities.append(PanasonicFanEntity(coordinator, PANASONIC_FAN_DESCRIPTION))
    async_add_entities(entities)