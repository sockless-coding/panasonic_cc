"""Aquarea device setup and coordination."""
from __future__ import annotations

import logging

from aio_panasonic_comfort_cloud import ApiClient
from aioaquarea import Client as AquareaApiClient
from aioaquarea.data import DeviceInfo as AquareaDeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CONF_DEVICE_FETCH_INTERVAL,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DOMAIN,
)
from .const import AQUAREA_COORDINATORS
from .coordinator import AquareaDeviceCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms that the Aquarea slice provides
PLATFORMS = [
    "climate",
    "sensor",
    "switch",
    "button",
    "select",
    "binary_sensor",
    "water_heater",
]


async def async_setup_aquarea(
    hass: HomeAssistant,
    entry: ConfigEntry,
    panasonic_api: ApiClient,
) -> list[AquareaDeviceCoordinator]:
    """Set up Aquarea devices: create API client, coordinators, and register devices."""
    if not panasonic_api.has_unknown_devices:
        hass.data[DOMAIN][AQUAREA_COORDINATORS] = []
        return []

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    config = {**entry.data, **entry.options}

    client = async_get_clientsession(hass)

    try:
        aquarea_api = AquareaApiClient(client, username, password)
        await aquarea_api.login()
        aquarea_devices = await aquarea_api.get_devices()
    except Exception as exc:
        _LOGGER.warning("Failed to setup Aquarea devices: %s", exc, exc_info=True)
        hass.data[DOMAIN][AQUAREA_COORDINATORS] = []
        return []

    aquarea_coordinators: list[AquareaDeviceCoordinator] = []
    aquarea_coordinators_uninitialized: list[tuple[AquareaDeviceCoordinator, AquareaDeviceInfo]] = []

    for aquarea_device in aquarea_devices:
        try:
            aquarea_coordinator = AquareaDeviceCoordinator(
                hass, config, aquarea_api, aquarea_device
            )
            aquarea_coordinators_uninitialized.append((aquarea_coordinator, aquarea_device))
        except Exception as exc:
            _LOGGER.warning(
                "Failed to create coordinator for Aquarea device %s: %s",
                aquarea_device.name,
                exc,
                exc_info=True,
            )

    # Refresh all Aquarea coordinators in parallel
    async def _init_aquarea(coordinator: AquareaDeviceCoordinator, device_info: AquareaDeviceInfo) -> None:
        try:
            await coordinator.async_config_entry_first_refresh()
            aquarea_coordinators.append(coordinator)
        except Exception as exc:
            _LOGGER.warning(
                "Failed to setup Aquarea device %s: %s",
                device_info.name,
                exc,
                exc_info=True,
            )

    await asyncio.gather(
        *(_init_aquarea(coordinator, device_info) for coordinator, device_info in aquarea_coordinators_uninitialized),
        return_exceptions=True,
    )

    hass.data[DOMAIN][AQUAREA_COORDINATORS] = aquarea_coordinators

    # Register devices in device registry
    device_registry = dr.async_get(hass)
    for coordinator in aquarea_coordinators:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator.device.device_name,
            manufacturer=coordinator.device.manufacturer,
            model="",
            sw_version=coordinator.device.firmware_version,
        )

    return aquarea_coordinators


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    panasonic_api: ApiClient,
) -> bool:
    """Set up Aquarea from a config entry."""
    aquarea_coordinators = await async_setup_aquarea(hass, entry, panasonic_api)

    if not aquarea_coordinators:
        return True  # Not an error, just no Aquarea devices

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
