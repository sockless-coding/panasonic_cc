"""Panasonic switch entities."""
from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, Callable
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from aio_panasonic_comfort_cloud import (
    PanasonicDevice,
    PanasonicDeviceZone,
    ChangeRequestBuilder,
    WeeklyTimerPattern,
    constants,
)

from ..const import (
    CONF_FORCE_ENABLE_NANOE,
    DEFAULT_FORCE_ENABLE_NANOE,
    DOMAIN,
)
from .base import PanasonicDataEntity
from .coordinator import PanasonicDeviceCoordinator, PanasonicWeeklyTimerCoordinator
from .const import DATA_COORDINATORS, WEEKLY_TIMER_COORDINATORS

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PanasonicSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Panasonic switch entity."""

    on_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    off_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    get_state: Callable[[PanasonicDevice], bool]
    is_available: Callable[[PanasonicDevice], bool]


NANOE_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="nanoe",
    translation_key="nanoe",
    name="Nanoe",
    icon="mdi:virus-off",
    on_func=lambda builder: builder.set_nanoe_mode(constants.NanoeMode.On),
    off_func=lambda builder: builder.set_nanoe_mode(constants.NanoeMode.Off),
    get_state=lambda device: device.parameters.nanoe_mode
    in [
        constants.NanoeMode.On,
        constants.NanoeMode.ModeG,
        constants.NanoeMode.All,
    ],
    is_available=lambda device: device.has_nanoe,
)
ECONAVI_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-navi",
    translation_key="eco-navi",
    name="ECONAVI",
    icon="mdi:leaf",
    on_func=lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.On),
    off_func=lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.Off),
    get_state=lambda device: device.parameters.eco_navi_mode
    == constants.EcoNaviMode.On,
    is_available=lambda device: device.has_eco_navi,
)
ECO_FUNCTION_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-function",
    translation_key="eco-function",
    name="AI ECO",
    icon="mdi:leaf",
    on_func=lambda builder: builder.set_eco_function_mode(
        constants.EcoFunctionMode.On
    ),
    off_func=lambda builder: builder.set_eco_function_mode(
        constants.EcoFunctionMode.Off
    ),
    get_state=lambda device: device.parameters.eco_function_mode
    == constants.EcoFunctionMode.On,
    is_available=lambda device: device.has_eco_function,
)
IAUTOX_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="iauto-x",
    translation_key="iauto-x",
    name="iAUTO-X",
    icon="mdi:snowflake",
    on_func=lambda builder: builder.set_iautox_mode(constants.IAutoXMode.On),
    off_func=lambda builder: builder.set_iautox_mode(constants.IAutoXMode.Off),
    get_state=lambda device: device.parameters.iautox_mode
    == constants.IAutoXMode.On
    and device.parameters.mode == constants.OperationMode.Auto,
    is_available=lambda device: device.has_iauto_x,
)


def create_zone_mode_description(zone: PanasonicDeviceZone) -> PanasonicSwitchEntityDescription:
    """Create a switch description for a zone."""
    return PanasonicSwitchEntityDescription(
        key=f"zone-{zone.id}",
        translation_key=f"zone-{zone.id}",
        name=zone.name,
        icon="mdi:thermostat",
        off_func=lambda builder, z=zone.id: builder.set_zone_mode(
            z, constants.ZoneMode.Off
        ),
        on_func=lambda builder, z=zone.id: builder.set_zone_mode(
            z, constants.ZoneMode.On
        ),
        get_state=lambda device, z=zone.id: device.parameters.get_zone(
            z
        ).mode
        == constants.ZoneMode.On,
        is_available=lambda device: True,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic switches."""
    devices = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][
        DATA_COORDINATORS
    ]
    force_enable_nanoe = entry.options.get(
        CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE
    )
    for data_coordinator in data_coordinators:
        devices.append(
            PanasonicSwitchEntity(
                data_coordinator, NANOE_DESCRIPTION, always_available=force_enable_nanoe
            )
        )
        devices.append(PanasonicSwitchEntity(data_coordinator, ECONAVI_DESCRIPTION))
        devices.append(
            PanasonicSwitchEntity(data_coordinator, ECO_FUNCTION_DESCRIPTION)
        )
        devices.append(PanasonicSwitchEntity(data_coordinator, IAUTOX_DESCRIPTION))
        if data_coordinator.device.has_zones:
            for zone in data_coordinator.device.parameters.zones:
                devices.append(
                    PanasonicSwitchEntity(
                        data_coordinator, create_zone_mode_description(zone)
                    )
                )

    for weekly_timer_coordinator in hass.data[DOMAIN].get(WEEKLY_TIMER_COORDINATORS, []):
        devices.append(PanasonicWeeklyTimerSwitch(weekly_timer_coordinator))

    async_add_entities(devices)


class PanasonicSwitchEntity(PanasonicDataEntity, SwitchEntity):
    """Representation of a Panasonic switch."""

    entity_description: PanasonicSwitchEntityDescription
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicSwitchEntityDescription,
        always_available: bool = False,
    ) -> None:
        """Initialize the switch entity."""
        self.entity_description = description
        self._always_available = always_available
        super().__init__(coordinator, description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._always_available or self.entity_description.is_available(
            self.coordinator.device
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the switch."""
        self._attr_is_on = self.entity_description.get_state(
            self.coordinator.device
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            builder = self.coordinator.get_change_request_builder()
            self.entity_description.on_func(builder)
            await self.coordinator.async_apply_changes(builder)
            await self.coordinator.async_schedule_refresh()
            self._attr_is_on = True
        except Exception:
            _LOGGER.exception(
                "Failed to turn on switch %s for device %s",
                self.entity_description.key,
                self.coordinator.device_id,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            builder = self.coordinator.get_change_request_builder()
            self.entity_description.off_func(builder)
            await self.coordinator.async_apply_changes(builder)
            await self.coordinator.async_schedule_refresh()
            self._attr_is_on = False
        except Exception:
            _LOGGER.exception(
                "Failed to turn off switch %s for device %s",
                self.entity_description.key,
                self.coordinator.device_id,
            )


def _option_name(value: Enum) -> str:
    """Enum member name as a snake_case option, e.g. LowMid -> low_mid."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value.name).lower()


def _options(enum_type: type[Enum]) -> dict[str, Enum]:
    return {_option_name(member): member for member in enum_type}


WEEKLY_TIMER_WEEKDAYS = _options(constants.WeeklyTimerWeekday)
WEEKLY_TIMER_POWER = _options(constants.Power)
WEEKLY_TIMER_MODES = _options(constants.OperationMode)
WEEKLY_TIMER_FAN_SPEEDS = _options(constants.FanSpeed)


def _pattern_to_dict(pattern: WeeklyTimerPattern) -> dict[str, Any]:
    """Summarize a pattern with the same keys/values the service accepts."""
    data: dict[str, Any] = {"start_time": pattern.start_time}
    if pattern.power is not None:
        data["power"] = _option_name(pattern.power)
    if pattern.mode is not None:
        data["mode"] = _option_name(pattern.mode)
    elif pattern.mode_raw is not None:
        # Modes the library doesn't model (e.g. nanoe standalone) stay raw.
        data["mode"] = pattern.mode_raw
    if pattern.temperature is not None:
        data["temperature"] = pattern.temperature
    if pattern.fan_speed is not None:
        data["fan_speed"] = _option_name(pattern.fan_speed)
    return data


def _pattern_from_dict(data: dict[str, Any]) -> WeeklyTimerPattern:
    """Build a pattern from a validated service call entry."""
    try:
        return WeeklyTimerPattern(
            start_time=data["start_time"],
            power=WEEKLY_TIMER_POWER[data["power"]] if "power" in data else None,
            mode=WEEKLY_TIMER_MODES[data["mode"]] if "mode" in data else None,
            temperature=data.get("temperature"),
            fan_speed=WEEKLY_TIMER_FAN_SPEEDS[data["fan_speed"]] if "fan_speed" in data else None,
        )
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err


class PanasonicWeeklyTimerSwitch(CoordinatorEntity[PanasonicWeeklyTimerCoordinator], SwitchEntity):
    """Turns an air conditioner's weekly schedule on/off and exposes its patterns."""

    _attr_has_entity_name = True
    _attr_translation_key = "weekly_timer"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: PanasonicWeeklyTimerCoordinator) -> None:
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
        """Return the schedule, one list of patterns per weekday."""
        weekly_timer = self.coordinator.weekly_timer
        return {
            "can_edit": self._can_edit(),
            "schedule": {
                _option_name(day.weekday): [_pattern_to_dict(pattern) for pattern in day.patterns]
                for day in weekly_timer.days
            },
        }

    def _can_edit(self) -> bool:
        # Unknown permission is allowed; the API will reject it if needed.
        weekly_timer = self.coordinator.weekly_timer
        return weekly_timer.permission is None or weekly_timer.can_edit

    def _ensure_editable(self) -> None:
        if not self._can_edit():
            raise HomeAssistantError(
                "This account is not allowed to change the weekly timer of this device"
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the schedule on."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the schedule off."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        self._ensure_editable()
        try:
            await self.coordinator.async_set_enabled(enabled)
        except Exception as err:
            raise HomeAssistantError(f"Failed to update the weekly timer: {err}") from err

    async def async_set_weekly_timer_day(
        self,
        weekdays: list[str],
        patterns: list[dict[str, Any]],
        enabled: bool = True,
    ) -> None:
        """Replace the patterns of the given weekdays."""
        self._ensure_editable()
        new_patterns = [_pattern_from_dict(pattern) for pattern in patterns]
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
