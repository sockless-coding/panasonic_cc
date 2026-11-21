"""Tests for setting up, migrating and removing the config entry."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_panasonic_comfort_cloud.exceptions import (
    AgreementNotAcceptedError,
    RequestError,
)
from aiohttp import ClientConnectionError
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.panasonic_cc import _is_connection_error
from custom_components.panasonic_cc.const import (
    CONF_AUTO_POWER_ON,
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_ENERGY_FETCH_INTERVAL,
    CONF_FORCE_ENABLE_NANOE,
    CONF_FORCE_OUTSIDE_SENSOR,
    CONF_USE_PANASONIC_PRESET_NAMES,
    DOMAIN,
)

CREDENTIALS = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"}


def make_entry(
    hass: HomeAssistant,
    *,
    data: dict | None = None,
    options: dict | None = None,
    version: int = 3,
) -> MockConfigEntry:
    """Add a config entry to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CREDENTIALS[CONF_USERNAME],
        data=data or CREDENTIALS,
        options=options or {},
        version=version,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def api() -> Generator[MagicMock]:
    """Patch the Comfort Cloud client with an account that has no devices."""
    with patch("custom_components.panasonic_cc.ApiClient") as client_cls:
        client = client_cls.return_value
        client.start_session = AsyncMock()
        client.has_devices = True
        client.get_devices.return_value = []
        client.aquarea_devices = []
        client.hws_devices = []
        client.app_version = "1.0.0"
        client.client_cls = client_cls
        yield client


async def test_setup_and_unload(hass: HomeAssistant, api: MagicMock) -> None:
    """An entry loads with the account's options and unloads again."""
    entry = make_entry(hass, options={CONF_AUTO_POWER_ON: False})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    _, kwargs = api.client_cls.call_args
    assert kwargs["auto_power_on"] is False
    assert kwargs["token_file_name"].endswith("panasonic_cc_user_example_com.tokens")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_without_devices(hass: HomeAssistant, api: MagicMock) -> None:
    """An account without devices fails to set up."""
    api.has_devices = False
    entry = make_entry(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "error",
    [
        ClientConnectionError("no route"),
        TimeoutError(),
        RequestError(ClientConnectionError("dns")),
    ],
)
async def test_setup_retries_on_connection_errors(
    hass: HomeAssistant, api: MagicMock, error: Exception
) -> None:
    """Network problems make Home Assistant retry later instead of reauth."""
    api.start_session.side_effect = error
    entry = make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.parametrize(
    "error",
    [
        Exception("401 unauthorized"),
        Exception("bad password"),
        AgreementNotAcceptedError([1]),
    ],
)
async def test_setup_starts_reauth_on_auth_errors(
    hass: HomeAssistant, api: MagicMock, error: Exception
) -> None:
    """Login and agreement failures ask the user to re-authenticate."""
    api.start_session.side_effect = error
    entry = make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ClientConnectionError(), True),
        (TimeoutError(), True),
        (RequestError(TimeoutError()), True),
        (RequestError("Expected status code '200' but received '401'"), False),
        (RequestError(), False),
        (ValueError("x"), False),
    ],
)
def test_is_connection_error(error: Exception, expected: bool) -> None:
    """Only network failures count as connection errors."""
    assert _is_connection_error(error) is expected


async def test_remove_entry_deletes_tokens(hass: HomeAssistant) -> None:
    """Removing the entry removes the account's token file."""
    entry = make_entry(hass)

    with patch(
        "custom_components.panasonic_cc.async_remove_token_file"
    ) as remove_tokens:
        await hass.config_entries.async_remove(entry.entry_id)

    remove_tokens.assert_awaited_once_with(hass, "user@example.com")


async def test_migrate_v1_to_v3(hass: HomeAssistant, api: MagicMock) -> None:
    """A version 1 entry ends up with only credentials in data, rest in options."""
    entry = make_entry(
        hass,
        data={**CREDENTIALS, CONF_FORCE_OUTSIDE_SENSOR: True},
        version=1,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert entry.minor_version == 1
    assert entry.data == CREDENTIALS
    assert entry.options == {
        CONF_FORCE_OUTSIDE_SENSOR: True,
        CONF_FORCE_ENABLE_NANOE: False,
        CONF_ENABLE_DAILY_ENERGY_SENSOR: False,
        CONF_USE_PANASONIC_PRESET_NAMES: True,
        CONF_DEVICE_FETCH_INTERVAL: 120,
        CONF_ENERGY_FETCH_INTERVAL: 300,
    }


async def test_migrate_v2_prefers_existing_options(
    hass: HomeAssistant, api: MagicMock
) -> None:
    """Options already set win over the old values kept in data."""
    entry = make_entry(
        hass,
        data={
            **CREDENTIALS,
            CONF_DEVICE_FETCH_INTERVAL: 60,
            CONF_ENERGY_FETCH_INTERVAL: 600,
            CONF_FORCE_ENABLE_NANOE: True,
        },
        options={CONF_DEVICE_FETCH_INTERVAL: 30},
        version=2,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert entry.data == CREDENTIALS
    assert entry.options[CONF_DEVICE_FETCH_INTERVAL] == 30
    assert entry.options[CONF_ENERGY_FETCH_INTERVAL] == 600
    assert entry.options[CONF_FORCE_ENABLE_NANOE] is True
