"""Tests for the diagnostics download."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from aio_panasonic_comfort_cloud import WeeklyTimer, constants
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.panasonic_cc.aquarea.const import AQUAREA_WEEKLY_TIMER_COORDINATORS
from custom_components.panasonic_cc.const import (
    AQUAREA_COORDINATORS,
    DATA_COORDINATORS,
    DOMAIN,
    ENERGY_COORDINATORS,
    HWS_COORDINATORS,
)
from custom_components.panasonic_cc.diagnostics import async_get_config_entry_diagnostics
from custom_components.panasonic_cc.panasonic.const import WEEKLY_TIMER_COORDINATORS

USERNAME = "person@example.com"
PASSWORD = "hunter2"
GUID = "CS-Z25XKEW+1234567890"


def entry(hass: HomeAssistant) -> MockConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Panasonic",
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        version=3,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    return config_entry


def ac_coordinator(device) -> SimpleNamespace:
    return SimpleNamespace(
        device_id="dev-1",
        _device_info=SimpleNamespace(name="Living room", model="CS-Z25"),
        _device=device,
    )


def ac_device(**overrides) -> MagicMock:
    device = MagicMock()
    params = device.parameters
    params.mode = constants.OperationMode.Heat
    params.fan_speed = constants.FanSpeed.Auto
    params.vertical_swing_mode = constants.AirSwingUD.Auto
    params.inside_temperature = 21
    params.outside_temperature = 4
    params.target_temperature = 22
    params.fireplace = 0
    device.features.fireplace = False
    device.has_nanoe = True
    device.has_eco_navi = False
    device.has_eco_function = False
    for key, value in overrides.items():
        setattr(params, key, value)
    return device


async def test_diagnostics_redacts_secrets(hass: HomeAssistant) -> None:
    """Credentials and device GUIDs never end up in the download."""
    config_entry = entry(hass)
    timer = WeeklyTimer(GUID, {"avlFlg": True, "permission": 3})
    hass.data[DOMAIN] = {
        DATA_COORDINATORS: [ac_coordinator(ac_device())],
        WEEKLY_TIMER_COORDINATORS: [
            SimpleNamespace(device_id="dev-1", _weekly_timer=timer)
        ],
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    dumped = json.dumps(diagnostics, default=str)
    for secret in (USERNAME, PASSWORD, GUID):
        assert secret not in dumped
    assert diagnostics["entry"]["data"] == {
        CONF_USERNAME: "**REDACTED**",
        CONF_PASSWORD: "**REDACTED**",
    }
    assert diagnostics["weekly_timers"][0]["weekly_timer"]["deviceGuid"] == "**REDACTED**"
    assert diagnostics["devices"][0]["state"]["operation_mode"] == "Heat"


async def test_diagnostics_handles_missing_data(hass: HomeAssistant) -> None:
    """Devices that haven't loaded yet, or report no mode, don't break it."""
    config_entry = entry(hass)
    hass.data[DOMAIN] = {
        DATA_COORDINATORS: [
            ac_coordinator(None),
            ac_coordinator(ac_device(mode=None, fan_speed=None, vertical_swing_mode=None)),
        ],
        ENERGY_COORDINATORS: [SimpleNamespace(device_id="dev-1", _energy=None)],
        AQUAREA_COORDINATORS: [SimpleNamespace(_device=None)],
        HWS_COORDINATORS: [SimpleNamespace(_device=None)],
        AQUAREA_WEEKLY_TIMER_COORDINATORS: [SimpleNamespace(_weekly_timer=None)],
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    not_loaded, no_mode = diagnostics["devices"]
    assert "state" not in not_loaded
    assert no_mode["state"]["operation_mode"] is None
    assert no_mode["state"]["fan_mode"] is None
    assert diagnostics["energy_data"] == []
    assert diagnostics["aquarea_devices"] == []
    assert diagnostics["hws_devices"] == []
    assert diagnostics["weekly_timers"] == []


async def test_diagnostics_without_any_devices(hass: HomeAssistant) -> None:
    """An entry whose slices stored nothing still produces a report."""
    config_entry = entry(hass)
    hass.data[DOMAIN] = {}

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["devices"] == []
    assert diagnostics["entry"]["title"] == "Panasonic"
