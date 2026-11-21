"""Tests for the air conditioner weekly timer switch and its service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from aio_panasonic_comfort_cloud import WeeklyTimer, constants
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.panasonic_cc.panasonic.switch import PanasonicWeeklyTimerSwitch
from custom_components.panasonic_cc.switch import (
    WEEKDAYS_SCHEMA,
    WEEKLY_TIMER_PATTERN_SCHEMA,
)

Weekday = constants.WeeklyTimerWeekday


def schedule(permission: int | None = 3, enabled: bool = True) -> WeeklyTimer:
    """A schedule with two patterns on Monday."""
    json = {
        "avlFlg": enabled,
        "weeklyTimerList": [
            {
                "patternList": [
                    {"startTime": "22:00", "onOff": 0},
                    {"startTime": "06:30", "onOff": 1, "mode": 3,
                     "temperature": 21, "fanSpeed": 2},
                ]
            }
        ],
    }
    if permission is not None:
        json["permission"] = permission
    return WeeklyTimer("guid-1", json)


def make_switch(weekly_timer: WeeklyTimer) -> PanasonicWeeklyTimerSwitch:
    coordinator = MagicMock()
    coordinator.device_id = "dev-1"
    coordinator.weekly_timer = weekly_timer
    coordinator.async_set_enabled = AsyncMock()
    coordinator.async_set_days = AsyncMock()
    return PanasonicWeeklyTimerSwitch(coordinator)


def test_state_and_attributes() -> None:
    """The switch shows whether the schedule is on, and the schedule itself."""
    switch = make_switch(schedule())

    assert switch.is_on is True
    assert switch.unique_id == "dev-1-weekly_timer"
    attributes = switch.extra_state_attributes
    assert attributes["can_edit"] is True
    assert attributes["schedule"]["monday"] == [
        {"start_time": "06:30", "power": "on", "mode": "heat",
         "temperature": 21.0, "fan_speed": "low_mid"},
        {"start_time": "22:00", "power": "off"},
    ]
    assert attributes["schedule"]["sunday"] == []


@pytest.mark.parametrize(
    ("permission", "can_edit"), [(None, True), (2, True), (3, True), (1, False)]
)
def test_can_edit(permission: int | None, can_edit: bool) -> None:
    """Unknown permission is allowed; only read-only accounts are blocked."""
    assert make_switch(schedule(permission)).extra_state_attributes["can_edit"] is can_edit


async def test_turn_on_and_off() -> None:
    """Turning the switch on or off enables or disables the schedule."""
    switch = make_switch(schedule())

    await switch.async_turn_off()
    await switch.async_turn_on()

    assert switch.coordinator.async_set_enabled.await_args_list == [
        ((False,),), ((True,),)
    ]


async def test_read_only_account_cannot_change() -> None:
    """An account without edit rights gets a clear error and nothing is sent."""
    switch = make_switch(schedule(permission=1))

    with pytest.raises(HomeAssistantError, match="not allowed"):
        await switch.async_turn_on()
    with pytest.raises(HomeAssistantError, match="not allowed"):
        await switch.async_set_weekly_timer_day(["monday"], [])

    switch.coordinator.async_set_enabled.assert_not_awaited()
    switch.coordinator.async_set_days.assert_not_awaited()


async def test_api_failure_becomes_ha_error() -> None:
    """Library errors are shown as Home Assistant errors."""
    switch = make_switch(schedule())
    switch.coordinator.async_set_enabled.side_effect = RuntimeError("boom")

    with pytest.raises(HomeAssistantError, match="Failed to update the weekly timer: boom"):
        await switch.async_turn_on()


async def test_set_day() -> None:
    """The service converts weekdays and patterns for the coordinator."""
    switch = make_switch(schedule())

    await switch.async_set_weekly_timer_day(
        ["monday", "friday"],
        [{"start_time": "7:00", "mode": "cool", "temperature": 24}],
        enabled=False,
    )

    weekdays, patterns, enabled = switch.coordinator.async_set_days.await_args.args
    assert weekdays == [Weekday.Monday, Weekday.Friday]
    assert [(p.start_time, p.mode, p.temperature) for p in patterns] == [
        ("07:00", constants.OperationMode.Cool, 24.0)
    ]
    assert enabled is False


async def test_set_day_rejects_duplicate_start_times() -> None:
    """Two patterns can't start at the same time, even written differently."""
    switch = make_switch(schedule())

    with pytest.raises(ServiceValidationError, match="different start time"):
        await switch.async_set_weekly_timer_day(
            ["monday"], [{"start_time": "7:00"}, {"start_time": "07:00"}]
        )
    switch.coordinator.async_set_days.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValueError("too many patterns"), ServiceValidationError),
        (RuntimeError("offline"), HomeAssistantError),
    ],
)
async def test_set_day_errors(error: Exception, expected: type[Exception]) -> None:
    """Invalid schedules are validation errors, anything else a plain error."""
    switch = make_switch(schedule())
    switch.coordinator.async_set_days.side_effect = error

    with pytest.raises(expected):
        await switch.async_set_weekly_timer_day(["monday"], [{"start_time": "07:00"}])


def test_weekdays_schema() -> None:
    """Weekdays accept a single day or a list, but not an empty list or typos."""
    assert WEEKDAYS_SCHEMA("monday") == ["monday"]
    assert WEEKDAYS_SCHEMA(["monday", "sunday"]) == ["monday", "sunday"]
    for bad in ([], ["mon"]):
        with pytest.raises(vol.Invalid):
            WEEKDAYS_SCHEMA(bad)


def test_pattern_schema() -> None:
    """Pattern options are limited to the names the switch understands."""
    assert WEEKLY_TIMER_PATTERN_SCHEMA(
        {"start_time": "07:00", "fan_speed": "high_mid", "temperature": "21"}
    ) == {"start_time": "07:00", "fan_speed": "high_mid", "temperature": 21.0}
    for bad in ({"mode": "heat"}, {"start_time": "07:00", "mode": "turbo"}):
        with pytest.raises(vol.Invalid):
            WEEKLY_TIMER_PATTERN_SCHEMA(bad)
