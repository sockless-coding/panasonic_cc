"""HWS (standalone Heat Pump Hot Water tank) water heater entities."""
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityDescription,
    WaterHeaterEntityFeature,
    STATE_HEAT_PUMP,
    STATE_OFF,
)
from homeassistant.const import UnitOfTemperature, PRECISION_WHOLE, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from aio_panasonic_comfort_cloud.constants import AquareaOperationStatus

from ..const import DOMAIN
from .base import HwsDataEntity
from .coordinator import HwsDeviceCoordinator
from .const import HWS_COORDINATORS

_LOGGER = logging.getLogger(__name__)

# The API reports no min/max bounds for the tank temperature — assumed from
# the same range used for Aquarea's tank (aquarea/water_heater.py), not
# provided by the API.
DEFAULT_MIN_TEMP = 40
DEFAULT_MAX_TEMP = 65


@dataclass(frozen=True, kw_only=True)
class HwsWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Describes an HWS Water Heater entity."""


HWS_WATER_TANK_DESCRIPTION = HwsWaterHeaterEntityDescription(
    key="tank",
    translation_key="tank",
    name="Tank",
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the HWS water heater."""
    entities = []
    hws_coordinators: list[HwsDeviceCoordinator] = hass.data[DOMAIN][HWS_COORDINATORS]
    for coordinator in hws_coordinators:
        entities.append(HwsWaterHeater(coordinator, HWS_WATER_TANK_DESCRIPTION))
    async_add_entities(entities)


class HwsWaterHeater(HwsDataEntity, WaterHeaterEntity):
    """Representation of an HWS hot water tank.

    ``tank_temperature`` is the only value the API reports, and it's also
    the field ``set_hws_tank_temperature`` writes — there's no separate
    sensed-vs-setpoint distinction in the payload (unlike Aquarea's tank),
    so it's treated purely as the target temperature here.
    """

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.OPERATION_MODE
    _attr_operation_list = [STATE_HEAT_PUMP, STATE_OFF]
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 1
    _attr_min_temp = DEFAULT_MIN_TEMP
    _attr_max_temp = DEFAULT_MAX_TEMP

    def __init__(
        self,
        coordinator: HwsDeviceCoordinator,
        description: HwsWaterHeaterEntityDescription,
    ) -> None:
        """Initialize the water heater entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        params = self.coordinator.device.parameters
        self._attr_target_temperature = params.tank_temperature

        if params.hpu_operation_status == AquareaOperationStatus.Off:
            self._attr_current_operation = STATE_OFF
        else:
            self._attr_current_operation = STATE_HEAT_PUMP

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature: float | None = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.api_client.set_hws_tank_temperature(self.coordinator.info, float(temperature))

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        if operation_mode == STATE_HEAT_PUMP:
            await self.coordinator.api_client.set_hws_operation_status(self.coordinator.info, AquareaOperationStatus.On)
        elif operation_mode == STATE_OFF:
            await self.coordinator.api_client.set_hws_operation_status(self.coordinator.info, AquareaOperationStatus.Off)
