"""Switch entities for Panasonic and Aquarea devices."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .panasonic.switch import async_setup_entry as panasonic_setup
from .aquarea.switch import async_setup_entry as aquarea_setup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the switch entities for both Panasonic and Aquarea."""
    await panasonic_setup(hass, entry, async_add_entities)
    await aquarea_setup(hass, entry, async_add_entities)
