"""Aquarea device setup and coordination."""
from __future__ import annotations

import asyncio
import logging

from aio_panasonic_comfort_cloud import ApiClient, PanasonicDeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from ..const import (
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    DOMAIN,
    MANUFACTURER,
)
from .const import AQUAREA_COORDINATORS, AQUAREA_ENERGY_COORDINATORS
from .coordinator import AquareaConsumptionCoordinator, AquareaDeviceCoordinator

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
    """Set up Aquarea devices: build coordinators from the shared ApiClient session and register devices."""
    aquarea_devices = panasonic_api.aquarea_devices
    if not aquarea_devices:
        hass.data[DOMAIN][AQUAREA_COORDINATORS] = []
        hass.data[DOMAIN][AQUAREA_ENERGY_COORDINATORS] = []
        return []

    config = {**entry.data, **entry.options}
    enable_daily_energy_sensor = entry.options.get(
        CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR
    )

    aquarea_coordinators: list[AquareaDeviceCoordinator] = []
    energy_coordinators: list[AquareaConsumptionCoordinator] = []
    aquarea_coordinators_uninitialized: list[tuple[AquareaDeviceCoordinator, PanasonicDeviceInfo]] = []

    for device_info in aquarea_devices:
        try:
            aquarea_coordinator = AquareaDeviceCoordinator(
                hass, config, panasonic_api, device_info
            )
            aquarea_coordinators_uninitialized.append((aquarea_coordinator, device_info))
            if enable_daily_energy_sensor:
                energy_coordinators.append(
                    AquareaConsumptionCoordinator(hass, config, panasonic_api, device_info)
                )
        except Exception as exc:
            _LOGGER.warning(
                "Failed to create coordinator for Aquarea device %s: %s",
                device_info.name,
                exc,
                exc_info=True,
            )

    # Refresh all Aquarea coordinators in parallel
    async def _init_aquarea(coordinator: AquareaDeviceCoordinator, device_info: PanasonicDeviceInfo) -> None:
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
    hass.data[DOMAIN][AQUAREA_ENERGY_COORDINATORS] = energy_coordinators

    # Register devices in device registry
    device_registry = dr.async_get(hass)
    for coordinator in aquarea_coordinators:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator._device_info.name,
            manufacturer=MANUFACTURER,
            model=coordinator._device_info.model,
            sw_version=coordinator.api_client.app_version,
        )

    # Refresh energy coordinators (best-effort — failures shouldn't block device setup)
    await asyncio.gather(
        *(energy.async_config_entry_first_refresh() for energy in energy_coordinators),
        return_exceptions=True,
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
