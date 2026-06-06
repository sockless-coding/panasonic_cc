"""Support for Panasonic Nanoe and other switches."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable
from dataclasses import dataclass

import aioaquarea

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from aio_panasonic_comfort_cloud import (
    PanasonicDevice,
    PanasonicDeviceZone,
    ChangeRequestBuilder,
    constants,
)

from . import DOMAIN
from .const import (
    AQUAREA_COORDINATORS,
    CONF_FORCE_ENABLE_NANOE,
    DATA_COORDINATORS,
    DEFAULT_FORCE_ENABLE_NANOE,
)
from .coordinator import PanasonicDeviceCoordinator, AquareaDeviceCoordinator
from .base import PanasonicDataEntity, AquareaDataEntity

_LOGGER = logging.getLogger(__name__)

AQUAREA_SWITCH_DELAY = 10.0


@dataclass(frozen=True, kw_only=True)
class PanasonicSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Panasonic switch entity."""

    on_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    off_func: Callable[[ChangeRequestBuilder], ChangeRequestBuilder]
    get_state: Callable[[PanasonicDevice], bool]
    is_available: Callable[[PanasonicDevice], bool]


NANOE_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="nanoe",
    translation_key="nanoe",
    name="Nanoe",
    icon="mdi:virus-off",
    on_func=lambda builder: builder.set_nanoe_mode(constants.NanoeMode.On),
    off_func=lambda builder: builder.set_nanoe_mode(constants.NanoeMode.Off),
    get_state=lambda device: device.parameters.nanoe_mode
    in [
        constants.NanoeMode.On,
        constants.NanoeMode.ModeG,
        constants.NanoeMode.All,
    ],
    is_available=lambda device: device.has_nanoe,
)
ECONAVI_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-navi",
    translation_key="eco-navi",
    name="ECONAVI",
    icon="mdi:leaf",
    on_func=lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.On),
    off_func=lambda builder: builder.set_eco_navi_mode(constants.EcoNaviMode.Off),
    get_state=lambda device: device.parameters.eco_navi_mode
    == constants.EcoNaviMode.On,
    is_available=lambda device: device.has_eco_navi,
)
ECO_FUNCTION_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="eco-function",
    translation_key="eco-function",
    name="AI ECO",
    icon="mdi:leaf",
    on_func=lambda builder: builder.set_eco_function_mode(
        constants.EcoFunctionMode.On
    ),
    off_func=lambda builder: builder.set_eco_function_mode(
        constants.EcoFunctionMode.Off
    ),
    get_state=lambda device: device.parameters.eco_function_mode
    == constants.EcoFunctionMode.On,
    is_available=lambda device: device.has_eco_function,
)
IAUTOX_DESCRIPTION = PanasonicSwitchEntityDescription(
    key="iauto-x",
    translation_key="iauto-x",
    name="iAUTO-X",
    icon="mdi:snowflake",
    on_func=lambda builder: builder.set_iautox_mode(constants.IAutoXMode.On),
    off_func=lambda builder: builder.set_iautox_mode(constants.IAutoXMode.Off),
    get_state=lambda device: device.parameters.iautox_mode
    == constants.IAutoXMode.On
    and device.parameters.mode == constants.OperationMode.Auto,
    is_available=lambda device: device.has_iauto_x,
)


def create_zone_mode_description(zone: PanasonicDeviceZone) -> PanasonicSwitchEntityDescription:
    """Create a switch description for a zone."""
    return PanasonicSwitchEntityDescription(
        key=f"zone-{zone.id}",
        translation_key=f"zone-{zone.id}",
        name=zone.name,
        icon="mdi:thermostat",
        off_func=lambda builder, z=zone.id: builder.set_zone_mode(
            z, constants.ZoneMode.Off
        ),
        on_func=lambda builder, z=zone.id: builder.set_zone_mode(
            z, constants.ZoneMode.On
        ),
        get_state=lambda device, z=zone.id: device.parameters.get_zone(
            z
        ).mode
        == constants.ZoneMode.On,
        is_available=lambda device: True,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Panasonic and Aquarea switches."""
    devices = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][
        DATA_COORDINATORS
    ]
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][
        AQUAREA_COORDINATORS
    ]
    force_enable_nanoe = entry.options.get(
        CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE
    )
    for data_coordinator in data_coordinators:
        devices.append(
            PanasonicSwitchEntity(
                data_coordinator, NANOE_DESCRIPTION, always_available=force_enable_nanoe
            )
        )
        devices.append(PanasonicSwitchEntity(data_coordinator, ECONAVI_DESCRIPTION))
        devices.append(
            PanasonicSwitchEntity(data_coordinator, ECO_FUNCTION_DESCRIPTION)
        )
        devices.append(PanasonicSwitchEntity(data_coordinator, IAUTOX_DESCRIPTION))
        if data_coordinator.device.has_zones:
            for zone in data_coordinator.device.parameters.zones:
                devices.append(
                    PanasonicSwitchEntity(
                        data_coordinator, create_zone_mode_description(zone)
                    )
                )

    # Aquarea switches
    for coordinator in aquarea_coordinators:
        if coordinator.device.has_tank:
            devices.append(AquareaForceDHWSwitch(coordinator))
        devices.append(AquareaForceHeaterSwitch(coordinator))
        devices.append(AquareaHolidayTimerSwitch(coordinator))

    async_add_entities(devices)


class PanasonicSwitchEntity(PanasonicDataEntity, SwitchEntity):
    """Representation of a Panasonic switch."""

    entity_description: PanasonicSwitchEntityDescription
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicSwitchEntityDescription,
        always_available: bool = False,
    ) -> None:
        """Initialize the switch entity."""
        self.entity_description = description
        self._always_available = always_available
        super().__init__(coordinator, description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._always_available or self.entity_description.is_available(
            self.coordinator.device
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the switch."""
        self._attr_is_on = self.entity_description.get_state(
            self.coordinator.device
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.on_func(builder)
        await self.coordinator.async_apply_changes(builder)
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        builder = self.coordinator.get_change_request_builder()
        self.entity_description.off_func(builder)
        await self.coordinator.async_apply_changes(builder)
        self._attr_is_on = False


# ---------------------------------------------------------------------------
# Aquarea switches
# ---------------------------------------------------------------------------

class AquareaBaseSwitch(AquareaDataEntity, SwitchEntity):
    """Base class for Aquarea switches with optimistic updates."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _optimistic_is_on: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return the switch state."""
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        return self._get_is_on()

    def _get_is_on(self) -> bool:
        """Override in subclass to return the actual state from the device."""
        raise NotImplementedError

    async def _schedule_refresh(self, delay: float = AQUAREA_SWITCH_DELAY) -> None:
        """Schedule a coordinator refresh after a short delay."""
        await asyncio.sleep(delay)
        self._optimistic_is_on = None
        try:
            await self.coordinator.async_request_refresh()
        except aioaquarea.RequestFailedError:
            _LOGGER.exception(
                "Delayed refresh failed for device %s",
                self.coordinator.device.device_id,
            )


class AquareaForceDHWSwitch(AquareaBaseSwitch):
    """Switch to force DHW (domestic hot water) mode on Aquarea devices."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "force_dhw")
        self._attr_translation_key = "force_dhw"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    def _get_is_on(self) -> bool:
        return self.coordinator.device.force_dhw is aioaquarea.ForceDHW.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Force DHW."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.device.set_force_dhw(aioaquarea.ForceDHW.ON)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Force DHW."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.device.set_force_dhw(aioaquarea.ForceDHW.OFF)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""


class AquareaForceHeaterSwitch(AquareaBaseSwitch):
    """Switch to force heater mode on Aquarea devices."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "force_heater")
        self._attr_translation_key = "force_heater"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:hvac" if self.is_on else "mdi:hvac-off"

    def _get_is_on(self) -> bool:
        return self.coordinator.device.force_heater is aioaquarea.ForceHeater.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Force Heater."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.device.set_force_heater(aioaquarea.ForceHeater.ON)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Force Heater."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.device.set_force_heater(aioaquarea.ForceHeater.OFF)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""


class AquareaHolidayTimerSwitch(AquareaBaseSwitch):
    """Switch to enable/disable the holiday timer on Aquarea devices."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "holiday_timer")
        self._attr_translation_key = "holiday_timer"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:timer-check" if self.is_on else "mdi:timer-off"

    def _get_is_on(self) -> bool:
        return self.coordinator.device.holiday_timer is aioaquarea.HolidayTimer.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Holiday Timer."""
        self._optimistic_is_on = True
        self.async_write_ha_state()
        await self.coordinator.device.set_holiday_timer(aioaquarea.HolidayTimer.ON)
        self.hass.async_create_task(self._schedule_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Holiday Timer."""
        self._optimistic_is_on = False
        self.async_write_ha_state()
        await self.coordinator.device.set_holiday_timer(aioaquarea.HolidayTimer.OFF)
        self.hass.async_create_task(self._schedule_refresh())

    def _async_update_attrs(self) -> None:
        """No-op — state is read via is_on property."""
