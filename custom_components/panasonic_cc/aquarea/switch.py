"""Aquarea switch entities."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)

from aio_panasonic_comfort_cloud import AquareaWeeklyTimerPattern
from aio_panasonic_comfort_cloud.constants import (
    AquareaForceDHW,
    AquareaForceHeater,
    AquareaHolidayTimer,
    AquareaOperationStatus,
    AquareaUpdateOperationMode,
)

from ..const import DOMAIN
from ..panasonic.switch import WEEKLY_TIMER_WEEKDAYS, _option_name
from .base import AquareaDataEntity
from .coordinator import AquareaDeviceCoordinator, AquareaWeeklyTimerCoordinator
from .const import (
    AQUAREA_COORDINATORS,
    AQUAREA_SWITCH_DELAY,
    AQUAREA_WEEKLY_TIMER_COORDINATORS,
)

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
        except Exception:
            _LOGGER.exception(
                "Delayed refresh failed for device %s",
                self.coordinator.device_id,
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
        return self.coordinator.device.parameters.force_dhw is AquareaForceDHW.On

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Force DHW."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.api_client.set_aquarea_force_dhw(self.coordinator.info, AquareaForceDHW.On)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Force DHW."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.api_client.set_aquarea_force_dhw(self.coordinator.info, AquareaForceDHW.Off)
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
        return self.coordinator.device.parameters.force_heater is AquareaForceHeater.On

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Force Heater."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.api_client.set_aquarea_force_heater(self.coordinator.info, AquareaForceHeater.On)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Force Heater."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.api_client.set_aquarea_force_heater(self.coordinator.info, AquareaForceHeater.Off)
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
        return self.coordinator.device.parameters.holiday_timer is AquareaHolidayTimer.On

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Holiday Timer."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.api_client.set_aquarea_holiday_timer(self.coordinator.info, AquareaHolidayTimer.On)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Holiday Timer."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.api_client.set_aquarea_holiday_timer(self.coordinator.info, AquareaHolidayTimer.Off)
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
        if coordinator.device.parameters.has_tank:
            devices.append(AquareaForceDHWSwitch(coordinator))
        devices.append(AquareaForceHeaterSwitch(coordinator))
        devices.append(AquareaHolidayTimerSwitch(coordinator))

    for weekly_timer_coordinator in hass.data[DOMAIN].get(AQUAREA_WEEKLY_TIMER_COORDINATORS, []):
        devices.append(AquareaWeeklyTimerSwitch(weekly_timer_coordinator))

    async_add_entities(devices)


# The app only offers Heat, Cool and Auto for a pattern.
AQUAREA_WEEKLY_TIMER_MODES = {
    _option_name(mode): mode
    for mode in (
        AquareaUpdateOperationMode.Heat,
        AquareaUpdateOperationMode.Cool,
        AquareaUpdateOperationMode.Auto,
    )
}
AQUAREA_WEEKLY_TIMER_ON_OFF = {
    _option_name(status): status
    for status in (AquareaOperationStatus.On, AquareaOperationStatus.Off)
}
AQUAREA_WEEKLY_TIMER_ZONES = (1, 2)


def _aquarea_pattern_to_dict(pattern: AquareaWeeklyTimerPattern) -> dict[str, Any]:
    """Summarize a pattern with the same keys/values the service accepts."""
    data: dict[str, Any] = {"start_time": pattern.start_time}
    if pattern.mode is not None:
        data["mode"] = _option_name(pattern.mode)
    elif pattern.mode_raw is not None:
        data["mode"] = pattern.mode_raw
    for zone_id in AQUAREA_WEEKLY_TIMER_ZONES:
        if (on_off := pattern.zone_on_off(zone_id)) is not None:
            data[f"zone{zone_id}"] = _option_name(on_off)
        if (heat := pattern.zone_heat(zone_id)) is not None:
            data[f"zone{zone_id}_heat"] = heat
        if (cool := pattern.zone_cool(zone_id)) is not None:
            data[f"zone{zone_id}_cool"] = cool
    if pattern.tank_on_off is not None:
        data["tank"] = _option_name(pattern.tank_on_off)
    if pattern.tank_temperature is not None:
        data["tank_temperature"] = pattern.tank_temperature
    return data


def _aquarea_pattern_from_dict(data: dict[str, Any]) -> AquareaWeeklyTimerPattern:
    """Build a pattern from a validated service call entry."""
    try:
        pattern = AquareaWeeklyTimerPattern(
            start_time=data["start_time"],
            mode=AQUAREA_WEEKLY_TIMER_MODES[data["mode"]] if "mode" in data else None,
        )
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err
    for zone_id in AQUAREA_WEEKLY_TIMER_ZONES:
        on_off = data.get(f"zone{zone_id}")
        pattern.set_zone(
            zone_id,
            AQUAREA_WEEKLY_TIMER_ON_OFF[on_off] if on_off is not None else None,
            heat=data.get(f"zone{zone_id}_heat"),
            cool=data.get(f"zone{zone_id}_cool"),
        )
    if "tank" in data:
        pattern.tank_on_off = AQUAREA_WEEKLY_TIMER_ON_OFF[data["tank"]]
    pattern.tank_temperature = data.get("tank_temperature")
    return pattern


class AquareaWeeklyTimerSwitch(CoordinatorEntity[AquareaWeeklyTimerCoordinator], SwitchEntity):
    """Turns an Aquarea heat pump's weekly schedule on/off and exposes its patterns."""

    _attr_has_entity_name = True
    _attr_translation_key = "weekly_timer"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: AquareaWeeklyTimerCoordinator) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}-weekly_timer"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return whether the schedule is active."""
        return self.coordinator.weekly_timer.enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the schedule, one list of patterns per weekday, and the setpoint limits."""
        weekly_timer = self.coordinator.weekly_timer
        attrs: dict[str, Any] = {
            "schedule": {
                _option_name(day.weekday): [_aquarea_pattern_to_dict(pattern) for pattern in day.patterns]
                for day in weekly_timer.days
            },
        }
        for zone_id in AQUAREA_WEEKLY_TIMER_ZONES:
            if (limits := weekly_timer.zone_limits(zone_id)) is not None:
                attrs[f"zone{zone_id}_limits"] = {
                    key: value for key, value in limits.items() if key != "zoneId"
                }
        if weekly_timer.tank_status is not None:
            attrs["tank_limits"] = weekly_timer.tank_status
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the schedule on."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the schedule off."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        try:
            await self.coordinator.async_set_enabled(enabled)
        except Exception as err:
            raise HomeAssistantError(f"Failed to update the weekly timer: {err}") from err

    async def async_set_aquarea_weekly_timer_day(
        self,
        weekdays: list[str],
        patterns: list[dict[str, Any]],
        enabled: bool = True,
    ) -> None:
        """Replace the patterns of the given weekdays."""
        new_patterns = [_aquarea_pattern_from_dict(pattern) for pattern in patterns]
        start_times = [pattern.start_time for pattern in new_patterns]
        if len(set(start_times)) != len(start_times):
            raise ServiceValidationError("Each pattern of a day needs a different start time")
        try:
            await self.coordinator.async_set_days(
                [WEEKLY_TIMER_WEEKDAYS[weekday] for weekday in weekdays],
                new_patterns,
                enabled,
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        except Exception as err:
            raise HomeAssistantError(f"Failed to update the weekly timer: {err}") from err
