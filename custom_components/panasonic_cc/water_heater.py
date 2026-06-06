"""Support for the Aquarea Tank."""
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

from .base import AquareaDataEntity
from .coordinator import AquareaDeviceCoordinator
from .const import DOMAIN, AQUAREA_COORDINATORS
from aioaquarea.data import DeviceAction, OperationStatus

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AquareaWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    """Describes a Aquarea Water Heater entity."""


AQUAREA_WATER_TANK_DESCRIPTION = AquareaWaterHeaterEntityDescription(
    key="tank",
    translation_key="tank",
    name="Tank",
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the Aquarea water heater."""
    entities = []
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]
    for aquarea_coordinator in aquarea_coordinators:
        if aquarea_coordinator.device.tank is None:
            continue
        entities.append(AquareaWaterHeater(aquarea_coordinator, AQUAREA_WATER_TANK_DESCRIPTION))
    async_add_entities(entities)


class AquareaWaterHeater(AquareaDataEntity, WaterHeaterEntity):
    """Representation of a Aquarea Water Tank."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.OPERATION_MODE
    _attr_operation_list = [STATE_HEAT_PUMP, STATE_OFF]
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 1
    _attr_min_temp = 40
    _attr_max_temp = 65

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: AquareaWaterHeaterEntityDescription,
    ) -> None:
        """Initialize the water heater entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update attributes."""
        device = self.coordinator.device

        if device.tank is None:
            self._attr_available = False
            return

        self._attr_min_temp = device.tank.heat_min
        self._attr_max_temp = device.tank.heat_max
        self._attr_target_temperature = device.tank.target_temperature
        self._attr_current_temperature = device.tank.temperature

        if device.tank.operation_status == OperationStatus.OFF:
            self._attr_current_operation = STATE_OFF
        else:
            self._attr_current_operation = STATE_HEAT_PUMP

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature: float | None = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if self.coordinator.device.tank is None:
            return
        await self.coordinator.device.tank.set_target_temperature(int(temperature))

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        if self.coordinator.device.tank is None:
            return
        if operation_mode == STATE_HEAT_PUMP:
            await self.coordinator.device.tank.turn_on()
        elif operation_mode == STATE_OFF:
            await self.coordinator.device.tank.turn_off()