"""Water heater entities for Aquarea and HWS devices."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform

from .aquarea.water_heater import async_setup_entry as aquarea_setup
from .hws.const import SERVICE_SET_HWS_WEEKLY_SCHEDULE
from .hws.water_heater import async_setup_entry as hws_setup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the water heater entities for Aquarea and HWS devices."""
    await aquarea_setup(hass, entry, async_add_entities)
    await hws_setup(hass, entry, async_add_entities)

    platform = entity_platform.current_platform.get()
    if platform is not None:
        platform.async_register_entity_service(
            SERVICE_SET_HWS_WEEKLY_SCHEDULE,
            {vol.Required("weekly_schedule"): vol.All([dict], vol.Length(min=1))},
            "async_set_hws_weekly_schedule",
        )
