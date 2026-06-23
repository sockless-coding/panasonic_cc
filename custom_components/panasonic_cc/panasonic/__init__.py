"""Panasonic Comfort Cloud device setup and coordination."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aio_panasonic_comfort_cloud import ApiClient, PanasonicDevice, PanasonicDeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_ENERGY_FETCH_INTERVAL,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)
from .const import DATA_COORDINATORS, ENERGY_COORDINATORS
from .coordinator import (
    PanasonicDeviceCoordinator,
    PanasonicDeviceEnergyCoordinator,
)

_LOGGER = logging.getLogger(__name__)


def _patch_missing_timestamp() -> None:
    """Patch aio-panasonic-comfort-cloud to handle missing timestamp payloads."""
    if getattr(PanasonicDevice.load, "_panasonic_cc_patched", False):
        return

    original_load = PanasonicDevice.load

    def _panasonic_cc_safe_load(self: PanasonicDevice, json_data: Any) -> bool:
        if isinstance(json_data, dict) and "timestamp" not in json_data:
            import time

            json_data = {**json_data, "timestamp": int(time.time())}
        return original_load(self, json_data)

    setattr(_panasonic_cc_safe_load, "_panasonic_cc_patched", True)
    PanasonicDevice.load = _panasonic_cc_safe_load


_patch_missing_timestamp()

# Platforms that the Panasonic slice provides
PLATFORMS = [
    "climate",
    "sensor",
    "switch",
    "button",
    "number",
    "select",
]


async def async_setup_panasonic(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> tuple[list[PanasonicDeviceCoordinator], list[PanasonicDeviceEnergyCoordinator]]:
    """Set up Panasonic devices: create API client, coordinators, and register devices."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    enable_daily_energy_sensor = entry.options.get(
        CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR
    )

    # Merge data and options so coordinators can read fetch intervals from options
    config = {**entry.data, **entry.options}

    client = async_get_clientsession(hass)
    api = ApiClient(username, password, client)

    await api.start_session()

    devices = api.get_devices()
    _LOGGER.info("Got %s Panasonic devices", len(devices))

    data_coordinators: list[PanasonicDeviceCoordinator] = []
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = []

    # Create all device coordinators first
    device_coordinators_uninitialized: list[tuple[PanasonicDeviceCoordinator, PanasonicDeviceInfo]] = []
    for device in devices:
        try:
            device_coordinator = PanasonicDeviceCoordinator(hass, config, api, device)
            device_coordinators_uninitialized.append((device_coordinator, device))
            if enable_daily_energy_sensor:
                energy_coordinators.append(
                    PanasonicDeviceEnergyCoordinator(hass, config, api, device)
                )
        except Exception as exc:
            _LOGGER.warning("Failed to create coordinator for device %s: %s", device.name, exc, exc_info=True)

    # Refresh all device coordinators in parallel
    async def _init_device(coordinator: PanasonicDeviceCoordinator, device_info: PanasonicDeviceInfo) -> None:
        try:
            await coordinator.async_config_entry_first_refresh()
            data_coordinators.append(coordinator)
        except Exception as exc:
            _LOGGER.warning("Failed to setup device %s: %s", device_info.name, exc, exc_info=True)

    await asyncio.gather(
        *(_init_device(coordinator, device_info) for coordinator, device_info in device_coordinators_uninitialized),
        return_exceptions=True,
    )

    hass.data[DOMAIN][DATA_COORDINATORS] = data_coordinators
    hass.data[DOMAIN][ENERGY_COORDINATORS] = energy_coordinators

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

    # Refresh energy coordinators
    await asyncio.gather(
        *(data.async_config_entry_first_refresh() for data in energy_coordinators),
        return_exceptions=True,
    )

    return data_coordinators, energy_coordinators


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Panasonic from a config entry."""
    data_coordinators, energy_coordinators = await async_setup_panasonic(hass, entry)

    if not data_coordinators:
        _LOGGER.error("Could not find any Panasonic Comfort Cloud Heat Pumps")
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
