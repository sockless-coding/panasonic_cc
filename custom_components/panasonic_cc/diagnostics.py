"""Diagnostics support for Panasonic Comfort Cloud."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    AQUAREA_COORDINATORS,
    DATA_COORDINATORS,
    DOMAIN,
    ENERGY_COORDINATORS,
)
from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator, AquareaDeviceCoordinator

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "access_token",
    "refresh_token",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data_coordinators = hass.data[DOMAIN].get(DATA_COORDINATORS, [])
    energy_coordinators = hass.data[DOMAIN].get(ENERGY_COORDINATORS, [])
    aquarea_coordinators = hass.data[DOMAIN].get(AQUAREA_COORDINATORS, [])

    devices = []
    for coordinator in data_coordinators:
        device_info = {
            "id": coordinator.device_id,
            "name": coordinator._device_info.name,
            "model": coordinator._device_info.model,
        }
        if coordinator._device is not None:
            panasonic_device = coordinator._device
            device_info["state"] = {
                "operation_mode": panasonic_device.parameters.mode.name
                if panasonic_device.parameters.mode
                else None,
                "inside_temperature": panasonic_device.parameters.inside_temperature,
                "outside_temperature": panasonic_device.parameters.outside_temperature,
                "target_temperature": panasonic_device.parameters.target_temperature,
                "fan_mode": panasonic_device.parameters.fan_speed.name
                if panasonic_device.parameters.fan_speed
                else None,
                "swing_mode": panasonic_device.parameters.vertical_swing_mode.name
                if panasonic_device.parameters.vertical_swing_mode
                else None,
                "has_nanoe": panasonic_device.has_nanoe,
                "has_eco_navi": panasonic_device.has_eco_navi,
                "has_eco_function": panasonic_device.has_eco_function,
            }
        devices.append(device_info)

    energy_data = []
    for coordinator in energy_coordinators:
        if coordinator._energy is not None:
            energy_data.append(
                {
                    "device_id": coordinator.device_id,
                    "daily_energy": coordinator._energy.consumption,
                    "current_power": coordinator._energy.current_power,
                }
            )

    aquarea_devices = []
    for coordinator in aquarea_coordinators:
        if coordinator._device is not None:
            aquarea_device = coordinator._device
            aquarea_devices.append(
                {
                    "id": coordinator.device_id,
                    "name": aquarea_device.device_name,
                    "model": aquarea_device.model or "",
                    "firmware_version": aquarea_device.firmware_version,
                    "manufacturer": aquarea_device.manufacturer,
                }
            )

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "devices": devices,
            "energy_data": energy_data,
            "aquarea_devices": aquarea_devices,
        },
        TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    # Find the device ID from the device registry entry
    device_id = None
    for identifiers in device.identifiers:
        if identifiers[0] == DOMAIN:
            device_id = identifiers[1]
            break

    if device_id is None:
        return async_redact_data({"error": "Device not found"}, TO_REDACT)

    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN].get(DATA_COORDINATORS, [])
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = hass.data[DOMAIN].get(ENERGY_COORDINATORS, [])
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN].get(AQUAREA_COORDINATORS, [])

    # Check Panasonic device coordinators
    for coordinator in data_coordinators:
        if coordinator.device_id == device_id:
            device_info = {
                "id": coordinator.device_id,
                "name": coordinator._device_info.name,
                "model": coordinator._device_info.model,
                "api_app_version": coordinator.api_client.app_version,
            }
            if coordinator._device is not None:
                panasonic_device = coordinator._device
                device_info["state"] = {
                    "operation_mode": panasonic_device.parameters.mode.name
                    if panasonic_device.parameters.mode
                    else None,
                    "inside_temperature": panasonic_device.parameters.inside_temperature,
                    "outside_temperature": panasonic_device.parameters.outside_temperature,
                    "target_temperature": panasonic_device.parameters.target_temperature,
                    "fan_mode": panasonic_device.parameters.fan_speed.name
                    if panasonic_device.parameters.fan_speed
                    else None,
                    "swing_mode": panasonic_device.parameters.vertical_swing_mode.name
                    if panasonic_device.parameters.vertical_swing_mode
                    else None,
                    "has_nanoe": panasonic_device.has_nanoe,
                    "has_eco_navi": panasonic_device.has_eco_navi,
                    "has_eco_function": panasonic_device.has_eco_function,
                }

            # Get energy data for this device
            energy_info = None
            for energy_coord in energy_coordinators:
                if energy_coord.device_id == device_id and energy_coord._energy is not None:
                    energy_info = {
                        "daily_energy": energy_coord._energy.consumption,
                        "current_power": energy_coord._energy.current_power,
                    }
                    break

            return async_redact_data(
                {
                    "device": device_info,
                    "energy": energy_info,
                },
                TO_REDACT,
            )

    # Check Aquarea device coordinators
    for coordinator in aquarea_coordinators:
        if coordinator.device_id == device_id:
            if coordinator._device is not None:
                aquarea_device = coordinator._device
                device_info = {
                    "id": coordinator.device_id,
                    "name": aquarea_device.device_name,
                    "model": aquarea_device.model or "",
                    "firmware_version": aquarea_device.firmware_version,
                    "manufacturer": aquarea_device.manufacturer,
                }
                return async_redact_data(
                    {
                        "device": device_info,
                    },
                    TO_REDACT,
                )

    return async_redact_data({"error": "Device coordinator not found"}, TO_REDACT)
