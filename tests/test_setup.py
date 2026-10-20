"""Regression tests for setup failures during Panasonic cloud outages.

Run with: python -m pytest tests/test_setup.py
Dependencies: requirements.txt, homeassistant, pytest, pytest-asyncio.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aio_panasonic_comfort_cloud.exceptions import (
    AgreementNotAcceptedError,
    LoginError,
    MFARequiredError,
    ResponseError,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import pytest

from custom_components import panasonic_cc


@pytest.fixture
def setup_entry(monkeypatch):
    """Isolate session startup without contacting Panasonic or touching tokens."""
    api = MagicMock()
    api.start_session = AsyncMock()
    monkeypatch.setattr(panasonic_cc, "ApiClient", lambda *args, **kwargs: api)
    monkeypatch.setattr(panasonic_cc, "async_get_clientsession", lambda hass: None)
    monkeypatch.setattr(panasonic_cc, "async_migrate_legacy_token_file", AsyncMock())
    monkeypatch.setattr(panasonic_cc, "get_token_file", lambda *args: "unused.json")
    hass = SimpleNamespace(data={})
    entry = SimpleNamespace(
        data={"username": "test@example.com", "password": "test-password"},
        options={},
    )
    return hass, entry, api


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 501, 502, 503, 504, 599])
async def test_server_error_retries_setup(setup_entry, status):
    """A service failure must not send the user through authentication."""
    hass, entry, api = setup_entry
    error = ResponseError(
        f"(get_acc_client_id: Expected status code 200, received: {status}: "
        '{"message":"10/20/2026 01:00 ～ 10/20/2026 04:00 (UTC ± 00)",'
        '"code":5300}'
    )
    api.start_session.side_effect = error

    with pytest.raises(ConfigEntryNotReady, match="temporarily unavailable") as raised:
        await panasonic_cc.async_setup_entry(hass, entry)

    assert raised.value.__cause__ is error
    api.start_session.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ResponseError('(login: Expected status code 200, received: 401: {"code":503})'),
        ResponseError(
            '(login: Expected status code 200, received: 403: {"code":5300})'
        ),
        ResponseError(
            '(login: Expected status code 200, received: 400: {"error":"invalid_user_password"})'
        ),
        LoginError("Invalid credentials"),
        MFARequiredError(),
        AgreementNotAcceptedError(),
        Exception("Unexpected error 503"),
    ],
)
async def test_other_errors_keep_authentication_path(setup_entry, error):
    """Preserve existing handling outside verified HTTP server errors."""
    hass, entry, api = setup_entry
    api.start_session.side_effect = error

    with pytest.raises(ConfigEntryAuthFailed) as raised:
        await panasonic_cc.async_setup_entry(hass, entry)

    assert raised.value.__cause__ is error
