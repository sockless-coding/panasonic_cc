"""Diagnostics support for Panasonic Comfort Cloud."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    AQUAREA_COORDINATORS,
    DATA_COORDINATORS,
    DOMAIN,
    ENERGY_COORDINATORS,
)

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
