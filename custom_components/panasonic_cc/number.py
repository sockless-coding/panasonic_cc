"""Number entities for Panasonic devices."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .panasonic.number import async_setup_entry as panasonic_setup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the number entities for Panasonic devices."""
    await panasonic_setup(hass, entry, async_add_entities)
