"""Tests for the per-account token files."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.panasonic_cc.const import DOMAIN
from custom_components.panasonic_cc.token_storage import (
    async_migrate_legacy_token_file,
    async_remove_token_file,
    get_token_file,
)

USERNAME = "user@example.com"


def add_entry(hass: HomeAssistant, username: str = USERNAME) -> MockConfigEntry:
    """Add a config entry for the account without setting it up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=username,
        data={CONF_USERNAME: username, CONF_PASSWORD: "secret"},
        version=3,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(autouse=True)
def config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Give each test its own config dir so token files don't leak between tests."""
    config = tmp_path / "config"
    (config / ".storage").mkdir(parents=True)
    hass.config.config_dir = str(config)
    return config


@pytest.fixture
def legacy_file(tmp_path: Path) -> Path:
    """Point the legacy shared token file at a temporary path."""
    path = tmp_path / "legacy-settings"
    with patch(
        "custom_components.panasonic_cc.token_storage.LEGACY_TOKEN_FILE", str(path)
    ):
        yield path


def test_token_file_is_per_account(hass: HomeAssistant) -> None:
    """Each account gets its own slugified file under .storage."""
    first = get_token_file(hass, "User@Example.com")
    second = get_token_file(hass, "other@example.com")

    assert first == hass.config.path(".storage", "panasonic_cc_user_example_com.tokens")
    assert first != second


async def test_migrates_legacy_file_for_single_entry(
    hass: HomeAssistant, legacy_file: Path
) -> None:
    """With one entry the shared file is copied to the account's file."""
    add_entry(hass)
    legacy_file.write_text("legacy tokens")

    await async_migrate_legacy_token_file(hass, USERNAME)

    assert Path(get_token_file(hass, USERNAME)).read_text() == "legacy tokens"
    assert legacy_file.exists()


async def test_migration_keeps_existing_account_file(
    hass: HomeAssistant, legacy_file: Path
) -> None:
    """An account file that already exists is never overwritten."""
    add_entry(hass)
    legacy_file.write_text("legacy tokens")
    token_file = Path(get_token_file(hass, USERNAME))
    token_file.write_text("current tokens")

    await async_migrate_legacy_token_file(hass, USERNAME)

    assert token_file.read_text() == "current tokens"


async def test_no_migration_with_several_entries(
    hass: HomeAssistant, legacy_file: Path
) -> None:
    """With several accounts it's unknown whose the shared file is."""
    add_entry(hass)
    add_entry(hass, "other@example.com")
    legacy_file.write_text("legacy tokens")

    await async_migrate_legacy_token_file(hass, USERNAME)

    assert not os.path.exists(get_token_file(hass, USERNAME))


async def test_no_migration_without_legacy_file(
    hass: HomeAssistant, legacy_file: Path
) -> None:
    """Nothing happens when there is no shared file to migrate."""
    add_entry(hass)

    await async_migrate_legacy_token_file(hass, USERNAME)

    assert not os.path.exists(get_token_file(hass, USERNAME))


async def test_migration_error_is_logged(
    hass: HomeAssistant, legacy_file: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing copy is logged instead of breaking setup."""
    add_entry(hass)
    legacy_file.write_text("legacy tokens")

    with patch(
        "custom_components.panasonic_cc.token_storage.shutil.copyfile",
        side_effect=OSError("disk full"),
    ):
        await async_migrate_legacy_token_file(hass, USERNAME)

    assert "Failed to migrate legacy token file: disk full" in caplog.text


async def test_remove_token_file(hass: HomeAssistant) -> None:
    """The account's token file is deleted."""
    token_file = Path(get_token_file(hass, USERNAME))
    token_file.write_text("tokens")

    await async_remove_token_file(hass, USERNAME)

    assert not token_file.exists()


async def test_remove_missing_token_file(hass: HomeAssistant) -> None:
    """Removing a file that isn't there is not an error."""
    await async_remove_token_file(hass, USERNAME)


async def test_remove_error_is_logged(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing delete is logged instead of raised."""
    token_file = Path(get_token_file(hass, USERNAME))
    token_file.write_text("tokens")

    with patch(
        "custom_components.panasonic_cc.token_storage.os.remove",
        side_effect=OSError("busy"),
    ):
        await async_remove_token_file(hass, USERNAME)

    assert "Failed to remove token file" in caplog.text
