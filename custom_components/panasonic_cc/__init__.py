"""Support for the Panasonic Comfort Cloud."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_panasonic_comfort_cloud import ApiClient
from aioaquarea import Client as AquareaApiClient, AquareaEnvironment
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.persistent_notification import async_dismiss
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .const import (
    AQUAREA_COORDINATORS,
    COMPONENT_TYPES,
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_ENERGY_FETCH_INTERVAL,
    CONF_FORCE_ENABLE_NANOE,
    CONF_FORCE_OUTSIDE_SENSOR,
    CONF_USE_PANASONIC_PRESET_NAMES,
    CONF_UPDATE_INTERVAL_VERSION,
    DATA_COORDINATORS,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    DEFAULT_FORCE_ENABLE_NANOE,
    DEFAULT_FORCE_OUTSIDE_SENSOR,
    DEFAULT_USE_PANASONIC_PRESET_NAMES,
    DOMAIN,
    ENERGY_COORDINATORS,
    MANUFACTURER,
    NOTIFICATION_AUTH_EXPIRED,
    STARTUP,
)
from .coordinator import (
    AquareaDeviceCoordinator,
    PanasonicDeviceCoordinator,
    PanasonicDeviceEnergyCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a config entry."""
    _LOGGER.debug("Migrating config entry from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1:
        # VERSION 1 → 2: Data structure is compatible, no changes needed.
        # Both versions store the same keys in entry.data:
        # CONF_USERNAME, CONF_PASSWORD, CONF_FORCE_OUTSIDE_SENSOR,
        # CONF_FORCE_ENABLE_NANOE, CONF_ENABLE_DAILY_ENERGY_SENSOR,
        # CONF_USE_PANASONIC_PRESET_NAMES, CONF_DEVICE_FETCH_INTERVAL,
        # CONF_ENERGY_FETCH_INTERVAL.
        # Ensure all expected keys have defaults for safety.
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
        # Only credentials (username/password) stay in entry.data.
        # This fixes a bug where settings were stored in data but read from options.
        new_data = {
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
        }

        new_options = {
            CONF_FORCE_OUTSIDE_SENSOR: entry.data.get(CONF_FORCE_OUTSIDE_SENSOR, DEFAULT_FORCE_OUTSIDE_SENSOR),
            CONF_FORCE_ENABLE_NANOE: entry.data.get(CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE),
            CONF_ENABLE_DAILY_ENERGY_SENSOR: entry.data.get(CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR),
            CONF_USE_PANASONIC_PRESET_NAMES: entry.data.get(CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES),
            CONF_DEVICE_FETCH_INTERVAL: entry.data.get(CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL),
            CONF_ENERGY_FETCH_INTERVAL: entry.data.get(CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL),
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
    # Register entry version migration
    if entry.version < 2:
        hass.config_entries.async_update_entry(
            entry,
            version=2,
            data={
                **entry.data,
                CONF_UPDATE_INTERVAL_VERSION: 2,
                CONF_DEVICE_FETCH_INTERVAL: entry.data.get(
                    CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL
                ),
                CONF_ENERGY_FETCH_INTERVAL: entry.data.get(
                    CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL
                ),
            },
        )

    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    enable_daily_energy_sensor = entry.options.get(
        CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR
    )

    # Merge data and options so coordinators can read fetch intervals from options
    config = {**entry.data, **entry.options}

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

    _LOGGER.info("Got %s devices", len(devices))

    data_coordinators: list[PanasonicDeviceCoordinator] = []
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = []
    aquarea_coordinators: list[AquareaDeviceCoordinator] = []

    for device in devices:
        try:
            device_coordinator = PanasonicDeviceCoordinator(hass, config, api, device)
            await device_coordinator.async_config_entry_first_refresh()
            data_coordinators.append(device_coordinator)
            if enable_daily_energy_sensor:
                energy_coordinators.append(
                    PanasonicDeviceEnergyCoordinator(hass, config, api, device)
                )
        except Exception as exc:
            _LOGGER.warning("Failed to setup device %s: %s", device.name, exc, exc_info=True)

    # Handle Aquarea (Panasonic heat pump) devices
    if api.has_unknown_devices:
        try:
            aquarea_api = AquareaApiClient(client, username, password)
            await aquarea_api.login()
            aquarea_devices = await aquarea_api.get_devices()
            for aquarea_device in aquarea_devices:
                try:
                    aquarea_coordinator = AquareaDeviceCoordinator(
                        hass, config, aquarea_api, aquarea_device
                    )
                    await aquarea_coordinator.async_config_entry_first_refresh()
                    aquarea_coordinators.append(aquarea_coordinator)
                except Exception as exc:
                    _LOGGER.warning(
                        "Failed to setup Aquarea device %s: %s",
                        aquarea_device.name,
                        exc,
                        exc_info=True,
                    )
        except Exception as exc:
            _LOGGER.warning("Failed to setup Aquarea devices: %s", exc, exc_info=True)

    hass.data[DOMAIN][DATA_COORDINATORS] = data_coordinators
    hass.data[DOMAIN][ENERGY_COORDINATORS] = energy_coordinators
    hass.data[DOMAIN][AQUAREA_COORDINATORS] = aquarea_coordinators

    # Refresh energy coordinators
    await asyncio.gather(
        *(data.async_config_entry_first_refresh() for data in energy_coordinators),
        return_exceptions=True,
    )

    # Register devices in device registry
    device_registry = dr.async_get(hass)
    for coordinator in data_coordinators:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator._device_info.name,
            manufacturer=MANUFACTURER,
            model=coordinator._device_info.model,
            sw_version=coordinator.api_client.app_version,
        )
    for coordinator in aquarea_coordinators:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator.device.device_name,
            manufacturer=coordinator.device.manufacturer,
            model="",
            sw_version=coordinator.device.firmware_version,
        )

    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info(STARTUP, integration.version)

    await hass.config_entries.async_forward_entry_setups(entry, COMPONENT_TYPES)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, COMPONENT_TYPES)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    # Clean up any stored data if needed
    pass
