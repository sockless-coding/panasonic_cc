"""Support for Panasonic and Aquarea climate entities."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import (
    AQUAREA_COORDINATORS,
    CONF_USE_PANASONIC_PRESET_NAMES,
    DATA_COORDINATORS,
    DEFAULT_USE_PANASONIC_PRESET_NAMES,
    DOMAIN,
    SERVICE_SET_SWING_LR_MODE,
)

from .entities.panasonic_climate import (
    PanasonicClimateEntity,
    PANASONIC_CLIMATE_DESCRIPTION,
)
from .entities.aquarea_climate import (
    AquareaClimateEntity,
    AquareaClimateEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic and Aquarea climate entities."""
    entities = []
    data_coordinators = hass.data[DOMAIN][DATA_COORDINATORS]
    aquarea_coordinators = hass.data[DOMAIN][AQUAREA_COORDINATORS]
    use_panasonic_preset_names = entry.options.get(
        CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES
    )
    for coordinator in data_coordinators:
        entities.append(
            PanasonicClimateEntity(
                coordinator, PANASONIC_CLIMATE_DESCRIPTION, use_panasonic_preset_names
            )
        )
    for aquarea_coordinator in aquarea_coordinators:
        for zone_id in aquarea_coordinator.device.zones:
            zone = aquarea_coordinator.device.zones.get(zone_id)
            if zone is None:
                continue
            entities.append(
                AquareaClimateEntity(
                    aquarea_coordinator,
                    AquareaClimateEntityDescription(
                        zone_id=zone_id,
                        name=zone.name,
                        key=f"zone-{zone_id}-climate",
                        translation_key=f"zone-{zone_id}-climate",
                    ),
                )
            )
    platform = entity_platform.current_platform.get()
    if platform is not None:
        platform.async_register_entity_service(
            SERVICE_SET_SWING_LR_MODE,
            {vol.Required("swing_mode"): cv.string},
            "async_set_horizontal_swing_mode",
        )
    async_add_entities(entities)
