"""Climate entities for Panasonic and Aquarea devices."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import DOMAIN, SERVICE_SET_SWING_LR_MODE

from .panasonic.climate import async_setup_entry as panasonic_setup
from .aquarea.climate import async_setup_entry as aquarea_setup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the climate entities for both Panasonic and Aquarea."""
    await panasonic_setup(hass, entry, async_add_entities)
    await aquarea_setup(hass, entry, async_add_entities)

    platform = entity_platform.current_platform.get()
    if platform is not None:
        platform.async_register_entity_service(
            SERVICE_SET_SWING_LR_MODE,
            {vol.Required("swing_mode"): cv.string},
            "async_set_horizontal_swing_mode",
        )
