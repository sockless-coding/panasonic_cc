"""Tests for the polling, backoff and error tracking of the coordinators."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_panasonic_comfort_cloud import WeeklyTimer, WeeklyTimerPattern
from aio_panasonic_comfort_cloud.constants import WeeklyTimerWeekday
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.panasonic_cc.aquarea.coordinator import AquareaDeviceCoordinator
from custom_components.panasonic_cc.const import (
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENERGY_FETCH_INTERVAL,
)
from custom_components.panasonic_cc.error_handler import ErrorCategory
from custom_components.panasonic_cc.hws.coordinator import HwsDeviceCoordinator
from custom_components.panasonic_cc.panasonic.coordinator import (
    PanasonicDeviceCoordinator,
    PanasonicDeviceEnergyCoordinator,
    PanasonicWeeklyTimerCoordinator,
    _is_auth_error,
)

CONFIG = {CONF_DEVICE_FETCH_INTERVAL: 100, CONF_ENERGY_FETCH_INTERVAL: 300}
NETWORK_ERROR = Exception("Expected status code '200' but received '503'")
AUTH_ERROR = Exception("Expected status code '200' but received '401'")


@pytest.fixture
def device_info() -> SimpleNamespace:
    """The library's device info for one unit."""
    return SimpleNamespace(id="dev-1", guid="guid-1", name="Living room", model="CS-Z25")


@pytest.fixture
def api() -> MagicMock:
    """An API client whose calls succeed."""
    client = MagicMock()
    client.app_version = "1.0.0"
    client.get_device = AsyncMock(return_value=MagicMock())
    client.try_update_device = AsyncMock(return_value=True)
    client.set_device_raw = AsyncMock()
    client.async_get_energy = AsyncMock(return_value=MagicMock())
    client.async_try_update_energy = AsyncMock(return_value=True)
    return client


@pytest.fixture
def notify() -> MagicMock:
    """Capture the 'authentication expired' notification."""
    with patch(
        "custom_components.panasonic_cc.panasonic.coordinator.async_create"
    ) as create:
        yield create


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, api: MagicMock, device_info: SimpleNamespace
) -> PanasonicDeviceCoordinator:
    """A device coordinator that has loaded its device."""
    coord = PanasonicDeviceCoordinator(hass, CONFIG, api, device_info)
    await coord.async_refresh()
    assert coord.last_update_success
    return coord


def interval(coord) -> int:
    return int(coord.update_interval.total_seconds())


# --- Auth error detection ----------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("received '401'", True),
        ("Unauthorized", True),
        ("Token expired", True),
        ("Invalid session", True),
        ("received '503'", False),
        ("Adapter communication error", False),
    ],
)
def test_is_auth_error(message: str, expected: bool) -> None:
    """Auth failures are recognised from the message."""
    assert _is_auth_error(Exception(message)) is expected


# --- Device coordinator ------------------------------------------------------


async def test_first_refresh_loads_device(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """The first poll fetches the device, later polls update it in place."""
    assert coordinator.data == 1
    assert coordinator.device is api.get_device.return_value
    assert coordinator.connection_status == "connected"

    await coordinator.async_refresh()

    assert coordinator.data == 2
    api.get_device.assert_awaited_once()
    api.try_update_device.assert_awaited_once_with(coordinator.device)


async def test_unchanged_poll_keeps_update_id(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """A poll without changes doesn't bump the data."""
    api.try_update_device.return_value = False
    await coordinator.async_refresh()

    assert coordinator.data == 1


async def test_device_before_first_refresh(
    hass: HomeAssistant, api: MagicMock, device_info: SimpleNamespace
) -> None:
    """Using the device before it's loaded is an error, not None."""
    coord = PanasonicDeviceCoordinator(hass, CONFIG, api, device_info)
    with pytest.raises(ValueError):
        coord.device


async def test_failures_back_off_exponentially(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """Each failure doubles the polling interval, up to ten minutes."""
    api.try_update_device.side_effect = NETWORK_ERROR

    intervals = []
    for _ in range(4):
        await coordinator.async_refresh()
        intervals.append(interval(coordinator))

    assert intervals == [200, 400, 600, 600]
    assert not coordinator.last_update_success
    assert coordinator.last_error.category is ErrorCategory.SERVER_ERROR


async def test_connection_status_degrades_then_disconnects(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """A few failures are 'degraded', five in a row is 'disconnected'."""
    api.try_update_device.side_effect = NETWORK_ERROR

    statuses = []
    for _ in range(5):
        await coordinator.async_refresh()
        statuses.append(coordinator.connection_status)

    assert statuses == ["degraded"] * 4 + ["disconnected"]


async def test_recovery_with_changes_resets_backoff(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """A successful poll restores the normal interval and clears the error."""
    api.try_update_device.side_effect = NETWORK_ERROR
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    api.try_update_device.side_effect = None
    await coordinator.async_refresh()

    assert interval(coordinator) == 100
    assert coordinator.connection_status == "connected"
    assert coordinator.last_error is None


async def test_recovery_without_changes_resets_backoff(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """A successful poll that finds no changes still means the API is back."""
    api.try_update_device.side_effect = NETWORK_ERROR
    await coordinator.async_refresh()

    api.try_update_device.side_effect = None
    api.try_update_device.return_value = False
    await coordinator.async_refresh()

    assert coordinator.connection_status == "connected"
    assert interval(coordinator) == 100


async def test_auth_error_disables_coordinator(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock, notify: MagicMock
) -> None:
    """An auth failure stops polling the API and tells the user."""
    api.try_update_device.side_effect = AUTH_ERROR
    await coordinator.async_refresh()

    assert coordinator.connection_status == "authentication_error"
    notify.assert_called_once()

    api.try_update_device.reset_mock()
    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    api.try_update_device.assert_not_awaited()


async def test_apply_changes_success_clears_command_error(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """A successful command sends the built request and clears the old error."""
    coordinator._last_command_error = object()
    builder = MagicMock()

    await coordinator.async_apply_changes(builder)

    api.set_device_raw.assert_awaited_once_with(coordinator.device, builder.build())
    assert coordinator.last_command_error is None


async def test_apply_changes_failure_is_tracked(
    coordinator: PanasonicDeviceCoordinator, api: MagicMock
) -> None:
    """A failed command is re-raised, remembered and counted as a failure."""
    api.set_device_raw.side_effect = Exception('{"code":5005}')
    listener = MagicMock()
    coordinator.async_add_listener(listener)

    with pytest.raises(Exception):
        await coordinator.async_apply_changes(MagicMock())

    assert coordinator.last_command_error.category is ErrorCategory.ADAPTER_COMMUNICATION
    assert coordinator.connection_status == "degraded"
    listener.assert_called()


async def test_schedule_refresh_is_debounced(
    hass: HomeAssistant, coordinator: PanasonicDeviceCoordinator
) -> None:
    """Several commands in a row lead to a single refresh."""
    delay_over = asyncio.Event()

    async def fake_sleep(_seconds: float) -> None:
        await delay_over.wait()

    fake_asyncio = SimpleNamespace(
        sleep=fake_sleep,
        CancelledError=asyncio.CancelledError,
        current_task=asyncio.current_task,
    )
    with (
        patch.object(coordinator, "async_request_refresh", AsyncMock()) as refresh,
        patch("custom_components.panasonic_cc.panasonic.coordinator.asyncio", fake_asyncio),
    ):
        for _ in range(3):
            await coordinator.async_schedule_refresh()
            # Let the previous, cancelled task finish before the next command.
            await asyncio.sleep(0)
        delay_over.set()
        await hass.async_block_till_done()

    refresh.assert_awaited_once()
    assert coordinator._refresh_task is None


async def test_stored_data_round_trip(coordinator: PanasonicDeviceCoordinator) -> None:
    """The per-device store returns what was saved, or an empty dict."""
    assert await coordinator.async_get_stored_data() == {}

    await coordinator.async_store_data({"last_mode": "heat"})

    assert await coordinator.async_get_stored_data() == {"last_mode": "heat"}


# --- Energy coordinator ------------------------------------------------------


async def test_energy_coordinator(
    hass: HomeAssistant, api: MagicMock, device_info: SimpleNamespace, notify: MagicMock
) -> None:
    """Energy polling loads, backs off from its own interval and handles auth."""
    coord = PanasonicDeviceEnergyCoordinator(hass, CONFIG, api, device_info)
    await coord.async_refresh()
    assert coord.data == 1
    assert coord.energy is api.async_get_energy.return_value

    api.async_try_update_energy.side_effect = NETWORK_ERROR
    await coord.async_refresh()
    assert interval(coord) == 600
    assert coord.connection_status == "degraded"

    api.async_try_update_energy.side_effect = AUTH_ERROR
    await coord.async_refresh()
    assert coord.connection_status == "authentication_error"
    notify.assert_called_once()


async def test_energy_recovery_without_changes_resets_backoff(
    hass: HomeAssistant, api: MagicMock, device_info: SimpleNamespace
) -> None:
    """Energy polling returns to normal even if the numbers didn't change."""
    coord = PanasonicDeviceEnergyCoordinator(hass, CONFIG, api, device_info)
    await coord.async_refresh()
    api.async_try_update_energy.side_effect = NETWORK_ERROR
    await coord.async_refresh()

    api.async_try_update_energy.side_effect = None
    api.async_try_update_energy.return_value = False
    await coord.async_refresh()

    assert coord.connection_status == "connected"
    assert interval(coord) == 300
    assert coord.data == 1


# --- Weekly timer coordinator -----------------------------------------------


def weekly_timer(*, enabled: bool = False) -> WeeklyTimer:
    """A real schedule with a pattern on Monday and Tuesday."""
    day = {"patternList": [{"startTime": "06:00", "onOff": 1}]}
    return WeeklyTimer(
        "guid-1",
        {"avlFlg": enabled, "permission": 3, "weeklyTimerList": [day, day]},
    )


@pytest.fixture
def timer_api(api: MagicMock) -> MagicMock:
    api.get_weekly_timer = AsyncMock(side_effect=lambda _: weekly_timer())
    api.try_update_weekly_timer = AsyncMock(return_value=False)
    api.set_weekly_timer = AsyncMock()
    api.set_weekly_timer_enabled = AsyncMock(return_value=weekly_timer(enabled=True))
    return api


async def test_weekly_timer_polling(
    hass: HomeAssistant, timer_api: MagicMock, device_info: SimpleNamespace
) -> None:
    """The schedule is fetched once, then only re-read for changes."""
    coord = PanasonicWeeklyTimerCoordinator(hass, CONFIG, timer_api, device_info)
    await coord.async_refresh()
    await coord.async_refresh()

    assert coord.data == 1
    assert interval(coord) == 300
    timer_api.get_weekly_timer.assert_awaited_once()

    timer_api.try_update_weekly_timer.side_effect = NETWORK_ERROR
    with pytest.raises(UpdateFailed, match="Service Unavailable"):
        await coord._async_update_data()


async def test_weekly_timer_set_enabled(
    hass: HomeAssistant, timer_api: MagicMock, device_info: SimpleNamespace
) -> None:
    """Turning the schedule on stores what the API returns."""
    coord = PanasonicWeeklyTimerCoordinator(hass, CONFIG, timer_api, device_info)
    await coord.async_refresh()

    await coord.async_set_enabled(True)

    timer_api.set_weekly_timer_enabled.assert_awaited_once_with(device_info, True)
    assert coord.weekly_timer.enabled
    assert coord.data == 2


async def test_weekly_timer_set_days(
    hass: HomeAssistant, timer_api: MagicMock, device_info: SimpleNamespace
) -> None:
    """Only the chosen days change, each with its own copy of the patterns."""
    coord = PanasonicWeeklyTimerCoordinator(hass, CONFIG, timer_api, device_info)
    await coord.async_refresh()
    patterns = [WeeklyTimerPattern(start_time="07:00"), WeeklyTimerPattern(start_time="22:00")]

    await coord.async_set_days(
        [WeeklyTimerWeekday.Monday, WeeklyTimerWeekday.Wednesday], patterns, True
    )

    # The schedule is re-read so edits made in the app aren't overwritten.
    assert timer_api.get_weekly_timer.await_count == 2
    saved: WeeklyTimer = timer_api.set_weekly_timer.await_args.args[0]
    assert saved is coord.weekly_timer
    assert saved.enabled

    def times(weekday):
        return [p.start_time for p in saved.day(weekday).patterns]

    assert times(WeeklyTimerWeekday.Monday) == ["07:00", "22:00"]
    assert times(WeeklyTimerWeekday.Wednesday) == ["07:00", "22:00"]
    assert times(WeeklyTimerWeekday.Tuesday) == ["06:00"]
    monday = saved.day(WeeklyTimerWeekday.Monday).patterns[0]
    assert monday is not saved.day(WeeklyTimerWeekday.Wednesday).patterns[0]
    assert monday is not patterns[0]


# --- Aquarea and hot water coordinators -------------------------------------


def aquarea_device() -> SimpleNamespace:
    params = SimpleNamespace(
        operation_status=1, operation_mode=1, direction=0, special_status=0,
        force_dhw=0, force_heater=0, quiet_mode=0, powerful_time=0,
        tank=None, zones=[],
    )
    return SimpleNamespace(parameters=params)


def hws_device() -> SimpleNamespace:
    params = SimpleNamespace(
        hpu_operation_status=1, operation_mode=1, boost_mode=0,
        tank_temperature=50, outdoor_temperature=5, weekly_settings=[],
    )
    return SimpleNamespace(parameters=params)


HEAT_PUMP_COORDINATORS = [
    pytest.param(
        AquareaDeviceCoordinator, "get_aquarea_device", "try_update_aquarea_device",
        aquarea_device, "custom_components.panasonic_cc.aquarea.coordinator.async_create",
        id="aquarea",
    ),
    pytest.param(
        HwsDeviceCoordinator, "get_hws_device", "try_update_hws_device",
        hws_device, "custom_components.panasonic_cc.hws.coordinator.async_create",
        id="hws",
    ),
]


@pytest.mark.parametrize(
    ("coordinator_cls", "get_name", "update_name", "make_device", "notify_path"),
    HEAT_PUMP_COORDINATORS,
)
async def test_heat_pump_coordinator_backoff_and_recovery(
    hass: HomeAssistant,
    api: MagicMock,
    device_info: SimpleNamespace,
    coordinator_cls,
    get_name: str,
    update_name: str,
    make_device,
    notify_path: str,
) -> None:
    """Backoff, recovery and change detection for Aquarea and hot water units."""
    device = make_device()
    setattr(api, get_name, AsyncMock(return_value=device))
    try_update = AsyncMock(return_value=True)
    setattr(api, update_name, try_update)

    coord = coordinator_cls(hass, CONFIG, api, device_info)
    await coord.async_refresh()
    assert coord.data == 1

    # The API says something changed, but none of the tracked state did.
    await coord.async_refresh()
    assert coord.data == 1

    device.parameters.operation_mode = 2
    await coord.async_refresh()
    assert coord.data == 2

    try_update.side_effect = NETWORK_ERROR
    await coord.async_refresh()
    await coord.async_refresh()
    assert coord.connection_status == "degraded"
    assert interval(coord) == 400

    # Back online without changes: the backoff is still reset.
    try_update.side_effect = None
    try_update.return_value = False
    await coord.async_refresh()
    assert coord.connection_status == "connected"
    assert interval(coord) == 100
    assert coord.last_error is None

    with patch(notify_path) as notify:
        try_update.side_effect = AUTH_ERROR
        await coord.async_refresh()
    assert coord.connection_status == "authentication_error"
    notify.assert_called_once()


async def test_aquarea_device_id_uses_raw_guid(
    hass: HomeAssistant, api: MagicMock, device_info: SimpleNamespace
) -> None:
    """Aquarea keeps the raw GUID as id so existing installs keep their entities."""
    coord = AquareaDeviceCoordinator(hass, CONFIG, api, device_info)
    assert coord.device_id == "guid-1"

    device_info.guid = None
    assert coord.device_id == "dev-1"
