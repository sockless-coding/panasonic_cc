"""Support for the Panasonic Comfort Cloud."""
from __future__ import annotations

import logging

from aio_panasonic_comfort_cloud import ApiClient
from homeassistant.components.persistent_notification import async_dismiss
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .const import (
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_ENERGY_FETCH_INTERVAL,
    CONF_FORCE_ENABLE_NANOE,
    CONF_FORCE_OUTSIDE_SENSOR,
    CONF_USE_PANASONIC_PRESET_NAMES,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    DEFAULT_FORCE_ENABLE_NANOE,
    DEFAULT_FORCE_OUTSIDE_SENSOR,
    DEFAULT_USE_PANASONIC_PRESET_NAMES,
    DOMAIN,
    MANUFACTURER,
    NOTIFICATION_AUTH_EXPIRED,
    STARTUP,
    COMPONENT_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a config entry."""
    _LOGGER.debug("Migrating config entry from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1:
        # VERSION 1 → 2: Data structure is compatible, no changes needed.
        new_data = {**entry.data}
        new_data.setdefault(CONF_FORCE_OUTSIDE_SENSOR, False)
        new_data.setdefault(CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE)
        new_data.setdefault(
            CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR
        )
        new_data.setdefault(
            CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL
        )
        new_data.setdefault(
            CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL
        )

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            version=2,
            minor_version=1,
        )

    if entry.version <= 2:
        # VERSION 2 → 3: Move configurable settings from entry.data to entry.options.
        new_data = {
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
        }

        new_options = {
            CONF_FORCE_OUTSIDE_SENSOR: entry.options.get(
                CONF_FORCE_OUTSIDE_SENSOR,
                entry.data.get(CONF_FORCE_OUTSIDE_SENSOR, DEFAULT_FORCE_OUTSIDE_SENSOR),
            ),
            CONF_FORCE_ENABLE_NANOE: entry.options.get(
                CONF_FORCE_ENABLE_NANOE,
                entry.data.get(CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE),
            ),
            CONF_ENABLE_DAILY_ENERGY_SENSOR: entry.options.get(
                CONF_ENABLE_DAILY_ENERGY_SENSOR,
                entry.data.get(CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR),
            ),
            CONF_USE_PANASONIC_PRESET_NAMES: entry.options.get(
                CONF_USE_PANASONIC_PRESET_NAMES,
                entry.data.get(CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES),
            ),
            CONF_DEVICE_FETCH_INTERVAL: entry.options.get(
                CONF_DEVICE_FETCH_INTERVAL,
                entry.data.get(CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL),
            ),
            CONF_ENERGY_FETCH_INTERVAL: entry.options.get(
                CONF_ENERGY_FETCH_INTERVAL,
                entry.data.get(CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL),
            ),
        }

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=3,
            minor_version=1,
        )

    _LOGGER.debug("Successfully migrated config entry to version 3.1")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Panasonic Comfort Cloud from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    client = async_get_clientsession(hass)
    api = ApiClient(username, password, client)

    try:
        await api.start_session()
    except Exception as err:
        error_msg = str(err).lower()
        if any(kw in error_msg for kw in ["401", "unauthorized", "authentication", "token", "expired"]):
            _LOGGER.error(
                "Authentication has expired or is invalid. Please re-authenticate by removing and re-adding the integration with valid credentials."
            )
        else:
            _LOGGER.error("Authentication failed: %s", err)
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

    # Dismiss any stale auth expired notification on successful setup
    async_dismiss(hass, NOTIFICATION_AUTH_EXPIRED)

    devices = api.get_devices()

    if not devices and not api.has_unknown_devices:
        _LOGGER.error("Could not find any Panasonic Comfort Cloud Heat Pumps")
        return False

    # Set up Panasonic slice
    from .panasonic import async_setup_panasonic
    data_coordinators, energy_coordinators = await async_setup_panasonic(hass, entry)

    # Set up Aquarea slice (if there are unknown devices)
    from .aquarea import async_setup_aquarea
    aquarea_coordinators = await async_setup_aquarea(hass, entry, api)

    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info(STARTUP, integration.version)

    # Forward setup to all platforms (thin router files delegate to each slice)
    await hass.config_entries.async_forward_entry_setups(entry, COMPONENT_TYPES)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, COMPONENT_TYPES)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    # Clean up any stored data if needed
    pass
