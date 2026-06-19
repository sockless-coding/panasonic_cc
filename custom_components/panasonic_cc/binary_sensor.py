"""Binary sensor entities for Aquarea devices."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .aquarea.binary_sensor import async_setup_entry as aquarea_setup


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the binary sensor entities for Aquarea devices."""
    await aquarea_setup(hass, entry, async_add_entities)
