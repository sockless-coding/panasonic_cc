"""Tests for the state logic of the Panasonic air conditioner entities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aio_panasonic_comfort_cloud import PanasonicDeviceZone, WeeklyTimerPattern, constants
from homeassistant.exceptions import ServiceValidationError

from custom_components.panasonic_cc.panasonic.number import (
    create_zone_damper_description,
)
from custom_components.panasonic_cc.panasonic.sensor import (
    create_zone_temperature_description,
)
from custom_components.panasonic_cc.panasonic.switch import (
    CLOTHES_DRYING_DESCRIPTION,
    FIREPLACE_DESCRIPTION,
    IAUTOX_DESCRIPTION,
    NANOE_DESCRIPTION,
    NANOE_STAND_ALONE_DESCRIPTION,
    _option_name,
    _pattern_from_dict,
    _pattern_to_dict,
    create_zone_mode_description,
)

On, Off = constants.Power.On, constants.Power.Off
Mode = constants.OperationMode


def make_device(**parameters) -> SimpleNamespace:
    """A stand-in for PanasonicDevice with the given parameters."""
    return SimpleNamespace(parameters=SimpleNamespace(**parameters))


def make_zone(zone_id: int, *, level: int = 100, temperature: int = 21) -> PanasonicDeviceZone:
    """A real library zone object."""
    return PanasonicDeviceZone(
        {
            "zoneId": zone_id,
            "zoneName": f"Zone {zone_id}",
            "zoneOnOff": 1,
            "zoneLevel": level,
            "zoneTemperature": temperature,
            "zoneSpill": 0,
        }
    )


def zone_device(*zones: PanasonicDeviceZone) -> SimpleNamespace:
    """A device whose parameters resolve zones by id, like the library."""
    index = {zone.id: zone for zone in zones}
    return make_device(get_zone=index.__getitem__)


@pytest.mark.parametrize(
    ("power", "iautox", "mode", "expected"),
    [
        (On, constants.IAutoXMode.On, Mode.Auto, True),
        # The cloud keeps the iAuto mode after the unit is switched off.
        (Off, constants.IAutoXMode.On, Mode.Auto, False),
        (On, constants.IAutoXMode.Off, Mode.Auto, False),
        (On, constants.IAutoXMode.On, Mode.Cool, False),
    ],
)
def test_iautox_state(power, iautox, mode, expected: bool) -> None:
    """iAUTO-X is only on while the unit runs in auto with iAUTO-X set."""
    device = make_device(power=power, iautox_mode=iautox, mode=mode)
    assert IAUTOX_DESCRIPTION.get_state(device) is expected


@pytest.mark.parametrize(
    ("nanoe", "expected"),
    [
        (constants.NanoeMode.On, True),
        (constants.NanoeMode.ModeG, True),
        (constants.NanoeMode.All, True),
        (constants.NanoeMode.Off, False),
    ],
)
def test_nanoe_state(nanoe, expected: bool) -> None:
    """Every nanoe variant counts as on."""
    assert NANOE_DESCRIPTION.get_state(make_device(nanoe_mode=nanoe)) is expected


@pytest.mark.parametrize(
    ("has_nanoe", "is_cac", "expected"),
    [(True, False, True), (True, True, False), (False, False, False)],
)
def test_nanoe_availability(has_nanoe: bool, is_cac: bool, expected: bool) -> None:
    """nanoe isn't offered on CAC units."""
    device = SimpleNamespace(has_nanoe=has_nanoe, info=SimpleNamespace(is_cac=is_cac))
    assert NANOE_DESCRIPTION.is_available(device) is expected


@pytest.mark.parametrize(
    ("mode", "expected"), [(Mode.Heat, True), (Mode.Cool, False), (Mode.Auto, False)]
)
def test_fireplace_only_in_heat_mode(mode, expected: bool) -> None:
    """The fireplace switch is only available while heating."""
    device = SimpleNamespace(has_fireplace=True, parameters=SimpleNamespace(mode=mode))
    assert FIREPLACE_DESCRIPTION.is_available(device) is expected


@pytest.mark.parametrize(
    ("power", "mode", "stand_alone", "expected"),
    [
        (On, Mode.NanoeStandAlone, False, True),
        # The unit reports Fan while running nanoe stand-alone.
        (On, Mode.Fan, True, True),
        (On, Mode.Fan, False, False),
        (Off, Mode.NanoeStandAlone, True, False),
    ],
)
def test_nanoe_stand_alone_state(power, mode, stand_alone: bool, expected: bool) -> None:
    """nanoe stand-alone is detected from the mode or the device flag."""
    device = make_device(power=power, mode=mode)
    device.in_nanoe_stand_alone_mode = stand_alone
    assert NANOE_STAND_ALONE_DESCRIPTION.get_state(device) is expected


@pytest.mark.parametrize(
    ("power", "mode", "expected"),
    [(On, Mode.ClothesDrying, True), (Off, Mode.ClothesDrying, False), (On, Mode.Dry, False)],
)
def test_clothes_drying_state(power, mode, expected: bool) -> None:
    """Clothes drying is on only while the unit runs in that mode."""
    assert CLOTHES_DRYING_DESCRIPTION.get_state(make_device(power=power, mode=mode)) is expected


@pytest.mark.parametrize(
    ("description", "expected_call"),
    [
        (NANOE_STAND_ALONE_DESCRIPTION, ("set_power_mode", Off)),
        (CLOTHES_DRYING_DESCRIPTION, ("set_power_mode", Off)),
    ],
)
def test_mode_switches_turn_unit_off(description, expected_call) -> None:
    """Turning a mode switch off powers the unit down, like the app."""
    builder = MagicMock()
    description.off_func(builder)

    method, value = expected_call
    getattr(builder, method).assert_called_once_with(value)


def test_zone_switch_follows_refreshed_zones() -> None:
    """The zone switch reads the zone by id, not the object seen at setup."""
    description = create_zone_mode_description(make_zone(1))
    refreshed = make_zone(1)
    refreshed.mode = constants.ZoneMode.Off

    assert description.get_state(zone_device(refreshed)) is False

    builder = MagicMock()
    description.on_func(builder)
    builder.set_zone_mode.assert_called_once_with(1, constants.ZoneMode.On)


def test_zone_damper_follows_refreshed_zones() -> None:
    """The damper number reads the current zone object on every update."""
    description = create_zone_damper_description(make_zone(2, level=100))

    assert description.get_value(zone_device(make_zone(2, level=40))) == 40

    builder = MagicMock()
    description.set_value(builder, 70)
    builder.set_zone_damper.assert_called_once_with(2, 70)


def test_zone_temperature_follows_refreshed_zones() -> None:
    """The zone temperature sensor reads the current zone object."""
    description = create_zone_temperature_description(make_zone(3, temperature=19))
    device = zone_device(make_zone(1, temperature=30), make_zone(3, temperature=23))

    assert description.get_state(device) == 23
    assert description.is_available(device) is True


def test_zone_temperature_unavailable_without_sensor() -> None:
    """Zones that report -255 have no temperature sensor."""
    description = create_zone_temperature_description(make_zone(1))
    assert description.is_available(zone_device(make_zone(1, temperature=-255))) is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (constants.FanSpeed.LowMid, "low_mid"),
        (constants.FanSpeed.High, "high"),
        (Mode.NanoeStandAlone, "nanoe_stand_alone"),
        (constants.WeeklyTimerWeekday.Monday, "monday"),
    ],
)
def test_option_name(value, expected: str) -> None:
    """Enum members become snake_case options."""
    assert _option_name(value) == expected


def test_weekly_timer_pattern_round_trip() -> None:
    """A service pattern survives converting to the library and back."""
    data = {
        "start_time": "07:30",
        "power": "on",
        "mode": "heat",
        "temperature": 21.5,
        "fan_speed": "low_mid",
    }

    pattern = _pattern_from_dict(data)

    assert pattern.mode is Mode.Heat
    assert pattern.fan_speed is constants.FanSpeed.LowMid
    assert _pattern_to_dict(pattern) == data


def test_weekly_timer_pattern_only_start_time() -> None:
    """Settings left out of the service call are left out of the pattern."""
    pattern = _pattern_from_dict({"start_time": "7:05"})

    assert _pattern_to_dict(pattern) == {"start_time": "07:05"}


def test_weekly_timer_pattern_keeps_raw_mode() -> None:
    """Modes the library doesn't model are shown as their raw value."""
    pattern = WeeklyTimerPattern({"startTime": "08:00", "mode": 99})

    assert pattern.mode is None
    assert _pattern_to_dict(pattern) == {"start_time": "08:00", "mode": 99}


def test_weekly_timer_pattern_rejects_bad_time() -> None:
    """An invalid start time is a validation error for the service call."""
    with pytest.raises(ServiceValidationError):
        _pattern_from_dict({"start_time": "25:99"})
