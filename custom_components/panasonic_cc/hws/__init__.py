"""HWS (standalone Heat Pump Hot Water tank) device setup and coordination."""
from __future__ import annotations

import asyncio
import logging

from aio_panasonic_comfort_cloud import ApiClient, PanasonicDeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from ..const import DOMAIN, MANUFACTURER
from .const import HWS_COORDINATORS
from .coordinator import HwsDeviceCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms that the HWS slice provides
PLATFORMS = [
    "sensor",
    "switch",
    "water_heater",
]


async def async_setup_hws(
    hass: HomeAssistant,
    entry: ConfigEntry,
    panasonic_api: ApiClient,
) -> list[HwsDeviceCoordinator]:
    """Set up HWS devices: build coordinators from the shared ApiClient session and register devices."""
    hws_devices = panasonic_api.hws_devices
    if not hws_devices:
        hass.data[DOMAIN][HWS_COORDINATORS] = []
        return []

    config = {**entry.data, **entry.options}

    hws_coordinators: list[HwsDeviceCoordinator] = []
    hws_coordinators_uninitialized: list[tuple[HwsDeviceCoordinator, PanasonicDeviceInfo]] = []

    for device_info in hws_devices:
        try:
            hws_coordinator = HwsDeviceCoordinator(hass, config, panasonic_api, device_info)
            hws_coordinators_uninitialized.append((hws_coordinator, device_info))
        except Exception as exc:
            _LOGGER.warning(
                "Failed to create coordinator for HWS device %s: %s",
                device_info.name,
                exc,
                exc_info=True,
            )

    # Refresh all HWS coordinators in parallel
    async def _init_hws(coordinator: HwsDeviceCoordinator, device_info: PanasonicDeviceInfo) -> None:
        try:
            await coordinator.async_config_entry_first_refresh()
            hws_coordinators.append(coordinator)
        except Exception as exc:
            _LOGGER.warning(
                "Failed to setup HWS device %s: %s",
                device_info.name,
                exc,
                exc_info=True,
            )

    await asyncio.gather(
        *(_init_hws(coordinator, device_info) for coordinator, device_info in hws_coordinators_uninitialized),
        return_exceptions=True,
    )

    hass.data[DOMAIN][HWS_COORDINATORS] = hws_coordinators

    # Register devices in device registry
    device_registry = dr.async_get(hass)
    for coordinator in hws_coordinators:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator._device_info.name,
            manufacturer=MANUFACTURER,
            model=coordinator._device_info.model,
            sw_version=coordinator.api_client.app_version,
        )

    return hws_coordinators


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    panasonic_api: ApiClient,
) -> bool:
    """Set up HWS from a config entry."""
    hws_coordinators = await async_setup_hws(hass, entry, panasonic_api)

    if not hws_coordinators:
        return True  # Not an error, just no HWS devices

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
