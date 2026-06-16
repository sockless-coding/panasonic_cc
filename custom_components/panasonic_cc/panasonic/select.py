"""Panasonic select entities."""
from __future__ import annotations

import logging
from typing import Any, Callable
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from aio_panasonic_comfort_cloud import PanasonicDevice, ChangeRequestBuilder, constants

from ..const import DOMAIN
from .base import PanasonicDataEntity
from .coordinator import PanasonicDeviceCoordinator
from .const import DATA_COORDINATORS

_LOGGER = logging.getLogger(__name__)


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
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic select entities."""
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    for coordinator in data_coordinators:
        entities.append(PanasonicSelectEntity(coordinator, HORIZONTAL_SWING_DESCRIPTION))
        entities.append(PanasonicSelectEntity(coordinator, VERTICAL_SWING_DESCRIPTION))

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
