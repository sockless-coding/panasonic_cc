"""Switch entities for Panasonic and Aquarea devices."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform

from .panasonic.const import SERVICE_SET_WEEKLY_TIMER_DAY
from .panasonic.switch import (
    WEEKLY_TIMER_FAN_SPEEDS,
    WEEKLY_TIMER_MODES,
    WEEKLY_TIMER_POWER,
    WEEKLY_TIMER_WEEKDAYS,
    async_setup_entry as panasonic_setup,
)
from .aquarea.switch import async_setup_entry as aquarea_setup
from .hws.switch import async_setup_entry as hws_setup

# Matches WEEKLY_TIMER_PATTERNS_PER_DAY in the library.
MAX_WEEKLY_TIMER_PATTERNS = 6

WEEKLY_TIMER_PATTERN_SCHEMA = vol.Schema(
    {
        vol.Required("start_time"): cv.string,
        vol.Optional("power"): vol.In(list(WEEKLY_TIMER_POWER)),
        vol.Optional("mode"): vol.In(list(WEEKLY_TIMER_MODES)),
        vol.Optional("temperature"): vol.Coerce(float),
        vol.Optional("fan_speed"): vol.In(list(WEEKLY_TIMER_FAN_SPEEDS)),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the switch entities for Panasonic, Aquarea and HWS."""
    await panasonic_setup(hass, entry, async_add_entities)
    await aquarea_setup(hass, entry, async_add_entities)
    await hws_setup(hass, entry, async_add_entities)

    platform = entity_platform.current_platform.get()
    if platform is not None:
        platform.async_register_entity_service(
            SERVICE_SET_WEEKLY_TIMER_DAY,
            {
                vol.Required("weekdays"): vol.All(
                    cv.ensure_list, vol.Length(min=1), [vol.In(list(WEEKLY_TIMER_WEEKDAYS))]
                ),
                vol.Required("patterns"): vol.All(
                    cv.ensure_list,
                    vol.Length(max=MAX_WEEKLY_TIMER_PATTERNS),
                    [WEEKLY_TIMER_PATTERN_SCHEMA],
                ),
                vol.Optional("enabled", default=True): cv.boolean,
            },
            "async_set_weekly_timer_day",
        )
