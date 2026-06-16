from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable
from dataclasses import dataclass

import aioaquarea
from aioaquarea import PowerfulTime, QuietMode

from homeassistant.core import HomeAssistant
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from .const import DOMAIN, DATA_COORDINATORS, AQUAREA_COORDINATORS
from aio_panasonic_comfort_cloud import PanasonicDevice, ChangeRequestBuilder, constants

from .coordinator import PanasonicDeviceCoordinator, AquareaDeviceCoordinator
from .base import PanasonicDataEntity, AquareaDataEntity

_LOGGER = logging.getLogger(__name__)

AQUAREA_SELECT_DELAY = 10.0

QUIET_MODE_LOOKUP = {
    "level1": QuietMode.LEVEL1,
    "level2": QuietMode.LEVEL2,
    "level3": QuietMode.LEVEL3,
    "off": QuietMode.OFF,
}

QUIET_MODE_REVERSE_LOOKUP = {v: k for k, v in QUIET_MODE_LOOKUP.items()}

POWERFUL_TIME_LOOKUP = {
    "on-30m": PowerfulTime.ON_30MIN,
    "on-60m": PowerfulTime.ON_60MIN,
    "on-90m": PowerfulTime.ON_90MIN,
    "off": PowerfulTime.OFF,
}

POWERFUL_TIME_REVERSE_LOOKUP = {v: k for k, v in POWERFUL_TIME_LOOKUP.items()}


@dataclass(frozen=True, kw_only=True)
class PanasonicSelectEntityDescription(SelectEntityDescription):
    """Description of a select entity."""

    set_option: Callable[[ChangeRequestBuilder, str], ChangeRequestBuilder]
    get_current_option: Callable[[PanasonicDevice], str]
    is_available: Callable[[PanasonicDevice], bool]
    get_options: Callable[[PanasonicDevice], list[str]] | None = None


HORIZONTAL_SWING_DESCRIPTION = PanasonicSelectEntityDescription(
    key="horizontal_swing",
    translation_key="horizontal_swing",
    icon="mdi:swap-horizontal",
    name="Horizontal Swing Mode",
    options=[
        opt.name
        for opt in constants.AirSwingLR
        if opt != constants.AirSwingLR.Unavailable
    ],
    set_option=lambda builder, new_value: builder.set_horizontal_swing(new_value),
    get_current_option=lambda device: device.parameters.horizontal_swing_mode.name,
    is_available=lambda device: device.has_horizontal_swing,
)
VERTICAL_SWING_DESCRIPTION = PanasonicSelectEntityDescription(
    key="vertical_swing",
    translation_key="vertical_swing",
    icon="mdi:swap-vertical",
    name="Vertical Swing Mode",
    get_options=lambda device: [
        opt.name
        for opt in constants.AirSwingUD
        if opt != constants.AirSwingUD.Swing or device.features.auto_swing_ud
    ],
    set_option=lambda builder, new_value: builder.set_vertical_swing(new_value),
    get_current_option=lambda device: device.parameters.vertical_swing_mode.name,
    is_available=lambda device: True,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic and Aquarea select entities."""
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]
    for coordinator in data_coordinators:
        entities.append(PanasonicSelectEntity(coordinator, HORIZONTAL_SWING_DESCRIPTION))
        entities.append(PanasonicSelectEntity(coordinator, VERTICAL_SWING_DESCRIPTION))

    # Aquarea selects
    for coordinator in aquarea_coordinators:
        entities.append(AquareaQuietModeSelect(coordinator))
        entities.append(AquareaPowerfulTimeSelect(coordinator))

    async_add_entities(entities)


class PanasonicSelectEntity(PanasonicDataEntity, SelectEntity):
    """Representation of a Panasonic select entity."""

    entity_description: PanasonicSelectEntityDescription

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        self.entity_description = description
        if description.get_options is not None:
            self._attr_options = description.get_options(coordinator.device)
        super().__init__(coordinator, description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.entity_description.is_available(self.coordinator.device)

    async def async_select_option(self, option: str) -> None:
        """Select a new option."""
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.set_option(builder, option)
        await self.coordinator.async_apply_changes(builder)
        await self.coordinator.async_schedule_refresh()
        self._attr_current_option = option

    def _async_update_attrs(self) -> None:
        """Update the attributes of the select entity."""
        self._attr_current_option = self.entity_description.get_current_option(
            self.coordinator.device
        )


# ---------------------------------------------------------------------------
# Aquarea selects
# ---------------------------------------------------------------------------

class AquareaQuietModeSelect(AquareaDataEntity, SelectEntity):
    """Select entity to configure the Aquarea device's quiet mode."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, "quiet_mode")
        self._attr_translation_key = "quiet_mode"
        self._attr_options = list(QUIET_MODE_LOOKUP.keys())
        self._attr_icon = "mdi:volume-off"
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str:
        """The current select option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
        return QUIET_MODE_REVERSE_LOOKUP.get(
            self.coordinator.device.quiet_mode, "off"
        )

    async def _schedule_refresh(self, delay: float = AQUAREA_SELECT_DELAY) -> None:
        """Clear optimistic state and request a coordinator refresh after a short delay."""
        await asyncio.sleep(delay)
        self._optimistic_option = None
        await self.coordinator.async_request_refresh()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if (quiet_mode := QUIET_MODE_LOOKUP.get(option)) is None:
            return
        if quiet_mode is self.coordinator.device.quiet_mode:
            return
        _LOGGER.debug(
            "Setting Quiet Mode of device %s, from %s to %s",
            self.coordinator.device.device_id,
            str(self.coordinator.device.quiet_mode),
            str(quiet_mode),
        )
        self._optimistic_option = option
        self.async_write_ha_state()
        await self.coordinator.device.set_quiet_mode(quiet_mode)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """Update the attributes of the select entity."""
        pass


class AquareaPowerfulTimeSelect(AquareaDataEntity, SelectEntity):
    """Select entity to configure the Aquarea device's powerful time."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, "powerful_time")
        self._attr_translation_key = "powerful_time"
        self._attr_options = list(POWERFUL_TIME_LOOKUP.keys())
        self._optimistic_option: str | None = None

    @property
    def icon(self) -> str:
        """Return the icon."""
        current = self.current_option
        return "mdi:fire" if current != "off" else "mdi:fire-off"

    @property
    def current_option(self) -> str:
        """The current select option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
        return POWERFUL_TIME_REVERSE_LOOKUP.get(
            self.coordinator.device.powerful_time, "off"
        )

    async def _schedule_refresh(self, delay: float = AQUAREA_SELECT_DELAY) -> None:
        """Clear optimistic state and request a coordinator refresh after a short delay."""
        await asyncio.sleep(delay)
        self._optimistic_option = None
        await self.coordinator.async_request_refresh()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if (powerful_time := POWERFUL_TIME_LOOKUP.get(option)) is None:
            return
        if powerful_time is self.coordinator.device.powerful_time:
            return
        _LOGGER.debug(
            "Setting Powerful Time of device %s, from %s to %s",
            self.coordinator.device.device_id,
            str(self.coordinator.device.powerful_time),
            str(powerful_time),
        )
        self._optimistic_option = option
        self.async_write_ha_state()
        await self.coordinator.device.set_powerful_time(powerful_time)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """Update the attributes of the select entity."""
        pass
