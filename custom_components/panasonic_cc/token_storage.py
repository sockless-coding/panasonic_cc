"""Per-account token file handling for the Panasonic Comfort Cloud library."""
from __future__ import annotations

import logging
import os
import shutil

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Where the library stores tokens when no file name is given. Every config
# entry used to share it, so separate accounts overwrote each other's tokens.
LEGACY_TOKEN_FILE = "~/.panasonic-settings"


def get_token_file(hass: HomeAssistant, username: str) -> str:
    """Return the token file path for an account.

    Keyed by username rather than entry id so the config flow (which has no
    entry yet) and the entry setup share the tokens obtained during login,
    including any MFA-backed session.
    """
    return hass.config.path(".storage", f"{DOMAIN}_{slugify(username)}.tokens")


async def async_migrate_legacy_token_file(hass: HomeAssistant, username: str) -> None:
    """Copy the old shared token file to the account's own file, once.

    Only done when there's a single config entry, because with several
    accounts there's no telling which one the shared file belongs to.
    """
    if len(hass.config_entries.async_entries(DOMAIN)) != 1:
        return

    token_file = get_token_file(hass, username)
    legacy_file = os.path.expanduser(LEGACY_TOKEN_FILE)

    def _migrate() -> bool:
        if os.path.exists(token_file) or not os.path.exists(legacy_file):
            return False
        shutil.copyfile(legacy_file, token_file)
        return True

    try:
        if await hass.async_add_executor_job(_migrate):
            _LOGGER.debug("Migrated legacy token file to '%s'", token_file)
    except OSError as err:
        _LOGGER.warning("Failed to migrate legacy token file: %s", err)


async def async_remove_token_file(hass: HomeAssistant, username: str) -> None:
    """Delete the account's token file."""
    token_file = get_token_file(hass, username)

    def _remove() -> None:
        if os.path.exists(token_file):
            os.remove(token_file)

    try:
        await hass.async_add_executor_job(_remove)
    except OSError as err:
        _LOGGER.warning("Failed to remove token file '%s': %s", token_file, err)
