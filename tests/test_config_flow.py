"""Tests for the Panasonic Comfort Cloud config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_panasonic_comfort_cloud.exceptions import (
    AgreementNotAcceptedError,
    MFARequiredError,
)
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.panasonic_cc.const import DOMAIN

OLD_CREDENTIALS = {CONF_USERNAME: "old@example.com", CONF_PASSWORD: "old-password"}
NEW_CREDENTIALS = {CONF_USERNAME: "old@example.com", CONF_PASSWORD: "new-password"}


@pytest.fixture
def api() -> Generator[MagicMock]:
    """Patch the Comfort Cloud client used by the config flow."""
    with patch("custom_components.panasonic_cc.config_flow.ApiClient") as client_cls:
        client = client_cls.return_value
        client.has_devices = True
        client.start_session = AsyncMock()
        client.reauthenticate = AsyncMock()
        client.accept_agreements = AsyncMock()
        client.get_pending_agreements = AsyncMock(
            return_value=[{"type": 1, "version": 7, "content": "Terms"}]
        )
        yield client


@pytest.fixture(autouse=True)
def setup_entry() -> Generator[AsyncMock]:
    """Stop the flows from setting up the real integration."""
    with patch(
        "custom_components.panasonic_cc.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a loaded config entry holding the old credentials."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=OLD_CREDENTIALS[CONF_USERNAME],
        data=OLD_CREDENTIALS,
        version=3,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def test_user_flow_creates_entry(hass: HomeAssistant, api: MagicMock) -> None:
    """A fresh setup stores the credentials and the default options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OLD_CREDENTIALS
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "old@example.com"
    assert result["data"] == OLD_CREDENTIALS
    assert "auto_power_on" in result["options"]


async def test_user_flow_rejects_duplicate_account(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry
) -> None:
    """The same Panasonic ID cannot be added twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], NEW_CREDENTIALS
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (Exception("invalid_user_password"), "invalid_user_password"),
        (TimeoutError(), "device_timeout"),
        (RuntimeError("boom"), "device_fail"),
    ],
)
async def test_user_flow_shows_login_errors(
    hass: HomeAssistant, api: MagicMock, error: Exception, expected: str
) -> None:
    """Login failures are shown on the user form."""
    api.start_session.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OLD_CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected}


async def test_user_flow_without_devices(hass: HomeAssistant, api: MagicMock) -> None:
    """An account without devices is reported instead of creating an entry."""
    api.has_devices = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OLD_CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_reconfigure_updates_entry(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry, setup_entry: AsyncMock
) -> None:
    """Reconfigure saves the new password on the existing entry and reloads it."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    setup_entry.reset_mock()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], NEW_CREDENTIALS
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == NEW_CREDENTIALS
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    setup_entry.assert_awaited_once()


async def test_reconfigure_can_change_account(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry
) -> None:
    """Changing the Panasonic ID also changes the entry title."""
    credentials = {CONF_USERNAME: "new@example.com", CONF_PASSWORD: "secret"}
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], credentials
    )
    await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.data == credentials
    assert entry.title == "new@example.com"


async def test_reconfigure_keeps_options(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry
) -> None:
    """Reconfigure leaves the options of the entry alone."""
    hass.config_entries.async_update_entry(entry, options={"auto_power_on": True})
    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(result["flow_id"], NEW_CREDENTIALS)
    await hass.async_block_till_done()

    assert entry.options == {"auto_power_on": True}


async def test_reconfigure_invalid_password_keeps_entry(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry
) -> None:
    """A rejected password is shown on the form and the entry is unchanged."""
    api.start_session.side_effect = Exception("invalid_user_password")
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], NEW_CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_user_password"}
    assert entry.data == OLD_CREDENTIALS


async def test_reconfigure_with_otp(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry
) -> None:
    """The 2FA step returns to the reconfigure path and updates the entry."""
    api.start_session.side_effect = [MFARequiredError("token"), None]
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], NEW_CREDENTIALS
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"otp_code": "123456"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == NEW_CREDENTIALS
    api.start_session.assert_awaited_with("123456")


async def test_reconfigure_with_agreements(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry
) -> None:
    """Accepting pending agreements finishes the reconfigure flow."""
    api.start_session.side_effect = [AgreementNotAcceptedError([1]), None]
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], NEW_CREDENTIALS
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "agreements"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"accept_agreements": True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == NEW_CREDENTIALS
    api.accept_agreements.assert_awaited_once_with([{"type": 1, "version": 7}])


async def test_reauth_updates_entry(
    hass: HomeAssistant, api: MagicMock, entry: MockConfigEntry
) -> None:
    """Reauth uses a fresh login and stores the new password."""
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == NEW_CREDENTIALS
    api.reauthenticate.assert_awaited_once()
    api.start_session.assert_not_awaited()
