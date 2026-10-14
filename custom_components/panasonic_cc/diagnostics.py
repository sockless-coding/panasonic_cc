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
    HWS_COORDINATORS,
)
from .panasonic.const import WEEKLY_TIMER_COORDINATORS
from .aquarea.const import AQUAREA_WEEKLY_TIMER_COORDINATORS

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "access_token",
    "refresh_token",
    "token",
    "deviceGuid",
    "gwid",
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
            aquarea_params = coordinator._device.parameters
            aquarea_devices.append(
                {
                    "id": coordinator.device_id,
                    "name": coordinator._device_info.name,
                    "model": coordinator._device_info.model,
                    "operation_mode": aquarea_params.operation_mode.name if aquarea_params.operation_mode else None,
                    "has_tank": aquarea_params.has_tank,
                    "zone_count": len(aquarea_params.zones),
                }
            )

    hws_coordinators = hass.data[DOMAIN].get(HWS_COORDINATORS, [])
    hws_devices = []
    for coordinator in hws_coordinators:
        if coordinator._device is not None:
            hws_params = coordinator._device.parameters
            hws_capabilities = coordinator._device.device_parameters
            hws_devices.append(
                {
                    "id": coordinator.device_id,
                    "name": coordinator._device_info.name,
                    "model": coordinator._device_info.model,
                    "hpu_operation_status": hws_params.hpu_operation_status.name,
                    "operation_mode": hws_params.operation_mode.name,
                    "boost_mode": hws_params.boost_mode.name,
                    "tank_temperature": hws_params.tank_temperature,
                    "outdoor_temperature": hws_params.outdoor_temperature,
                    "weekly_settings": [day.to_dict() for day in hws_params.weekly_settings or []],
                    "permission": hws_capabilities.permission,
                    "weekly_mode": hws_capabilities.weekly_mode,
                    "pv_mode": hws_capabilities.pv_mode,
                    "holiday_mode": hws_capabilities.holiday_mode,
                }
            )

    weekly_timers = []
    for coordinator in (
        *hass.data[DOMAIN].get(WEEKLY_TIMER_COORDINATORS, []),
        *hass.data[DOMAIN].get(AQUAREA_WEEKLY_TIMER_COORDINATORS, []),
    ):
        if coordinator._weekly_timer is not None:
            weekly_timers.append(
                {
                    "id": coordinator.device_id,
                    "weekly_timer": coordinator._weekly_timer.to_dict(),
                }
            )

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "devices": devices,
            "energy_data": energy_data,
            "aquarea_devices": aquarea_devices,
            "hws_devices": hws_devices,
            "weekly_timers": weekly_timers,
        },
        TO_REDACT,
    )
