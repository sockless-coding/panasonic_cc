from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import aioaquarea

from homeassistant.const import UnitOfEnergy, UnitOfTemperature, EntityCategory
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorExtraStoredData,
)
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from aio_panasonic_comfort_cloud import PanasonicDevice, PanasonicDeviceEnergy, PanasonicDeviceZone, constants
from aioaquarea import Device as AquareaDevice

from .const import (
    DOMAIN,
    DATA_COORDINATORS,
    ENERGY_COORDINATORS,
    AQUAREA_COORDINATORS,
)
from .base import PanasonicDataEntity, PanasonicEnergyEntity, AquareaDataEntity
from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator, AquareaDeviceCoordinator

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class PanasonicSensorEntityDescription(SensorEntityDescription):
    """Describes Panasonic sensor entity."""
    get_state: Callable[[PanasonicDevice], Any] | None = None
    is_available: Callable[[PanasonicDevice], bool] | None = None

@dataclass(frozen=True, kw_only=True)
class PanasonicEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Panasonic sensor entity."""
    get_state: Callable[[PanasonicDeviceEnergy], Any]| None = None

@dataclass(frozen=True, kw_only=True)
class AquareaSensorEntityDescription(SensorEntityDescription):
    """Describes Aquarea sensor entity."""
    get_state: Callable[[AquareaDevice], Any] | None = None
    is_available: Callable[[AquareaDevice], bool]| None = None

INSIDE_TEMPERATURE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="inside_temperature",
    translation_key="inside_temperature",
    name="Inside Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.parameters.inside_temperature,
    is_available=lambda device: device.parameters.inside_temperature is not None,
)
OUTSIDE_TEMPERATURE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="outside_temperature",
    translation_key="outside_temperature",
    name="Outside Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.parameters.outside_temperature,
    is_available=lambda device: device.parameters.outside_temperature is not None,
)
LAST_UPDATE_TIME_DESCRIPTION = PanasonicSensorEntityDescription(
    key="last_update",
    translation_key="last_update",
    name="Last Updated",
    icon="mdi:clock-outline",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=None,
    native_unit_of_measurement=None,
    get_state=lambda device: device.last_update,
    is_available=lambda device: True,
    entity_registry_enabled_default=False,
)
DATA_AGE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="data_age",
    translation_key="data_age",
    name="Cached Data Age",
    icon="mdi:clock-outline",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=None,
    native_unit_of_measurement=None,
    get_state=lambda device: device.timestamp,
    is_available=lambda device: device.info.status_data_mode == constants.StatusDataMode.CACHED,
    entity_registry_enabled_default=False,
)
DATA_MODE_DESCRIPTION = PanasonicSensorEntityDescription(
    key="status_data_mode",
    translation_key="status_data_mode",
    name="Data Mode",
    options=[opt.name for opt in constants.StatusDataMode],
    device_class=SensorDeviceClass.ENUM,
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=None,
    native_unit_of_measurement=None,
    get_state=lambda device: device.info.status_data_mode.name,
    is_available=lambda device: True,
    entity_registry_enabled_default=True,
)
DAILY_ENERGY_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="daily_energy_sensor",
    translation_key="daily_energy_sensor",
    name="Daily Energy",
    icon="mdi:flash",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement="kWh",
    get_state=lambda energy: energy.consumption
)
DAILY_HEATING_ENERGY_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="daily_heating_energy",
    translation_key="daily_heating_energy",
    name="Daily Heating Energy",
    icon="mdi:flash",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement="kWh",
    get_state=lambda energy: energy.heating_consumption
)
DAILY_COOLING_ENERGY_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="daily_cooling_energy",
    translation_key="daily_cooling_energy",
    name="Daily Cooling Energy",
    icon="mdi:flash",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement="kWh",
    get_state=lambda energy: energy.cooling_consumption
)
POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="current_power",
    translation_key="current_power",
    name="Current Extrapolated Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.current_power
)
COOLING_POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="cooling_power",
    translation_key="cooling_power",
    name="Cooling Extrapolated Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.cooling_power
)
HEATING_POWER_DESCRIPTION = PanasonicEnergySensorEntityDescription(
    key="heating_power",
    translation_key="heating_power",
    name="Heating Extrapolated Power",
    icon="mdi:flash",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="W",
    get_state=lambda energy: energy.heating_power
)

AQUAREA_OUTSIDE_TEMPERATURE_DESCRIPTION = AquareaSensorEntityDescription(
    key="outside_temperature",
    translation_key="outside_temperature",
    name="Outside Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.temperature_outdoor,
    is_available=lambda device: device.temperature_outdoor is not None,
)

AQUAREA_TANK_TEMPERATURE_DESCRIPTION = AquareaSensorEntityDescription(
    key="tank_temperature",
    translation_key="tank_temperature",
    name="Tank Temperature",
    icon="mdi:thermometer",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    get_state=lambda device: device.tank.temperature if device.tank is not None else None,
    is_available=lambda device: device.tank is not None,
)

AQUAREA_DIRECTION_DESCRIPTION = AquareaSensorEntityDescription(
    key="direction",
    translation_key="direction",
    name="Direction",
    icon="mdi:compass",
    get_state=lambda device: device.current_direction.name,
    is_available=lambda device: True,
)

AQUAREA_PUMP_STATUS_DESCRIPTION = AquareaSensorEntityDescription(
    key="pump_status",
    translation_key="pump_status",
    name="Pump Status",
    icon="mdi:pump",
    get_state=lambda device: "On" if device.pump_duty == 1 else "Off",
    is_available=lambda device: True,
)

# Energy consumption sensor descriptions for Aquarea
@dataclass(frozen=True, kw_only=True)
class AquareaEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Aquarea energy sensor entity."""
    consumption_type: aioaquarea.ConsumptionType
    exists_fn: Callable[[AquareaDeviceCoordinator], bool] = lambda _: True


AQUAREA_ACCUMULATED_ENERGY_SENSORS = [
    AquareaEnergySensorEntityDescription(
        key="heating_accumulated_energy_consumption",
        translation_key="heating_accumulated_energy_consumption",
        name="Heating Accumulated Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.HEAT,
    ),
    AquareaEnergySensorEntityDescription(
        key="cooling_accumulated_energy_consumption",
        translation_key="cooling_accumulated_energy_consumption",
        name="Cooling Accumulated Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.COOL,
        exists_fn=lambda coordinator: any(zone.cool_mode for zone in coordinator.device.zones.values()),
    ),
    AquareaEnergySensorEntityDescription(
        key="tank_accumulated_energy_consumption",
        translation_key="tank_accumulated_energy_consumption",
        name="Tank Accumulated Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.WATER_TANK,
        exists_fn=lambda coordinator: coordinator.device.has_tank,
    ),
    AquareaEnergySensorEntityDescription(
        key="accumulated_energy_consumption",
        translation_key="accumulated_energy_consumption",
        name="Accumulated Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.TOTAL,
    ),
]

AQUAREA_ENERGY_SENSORS = [
    AquareaEnergySensorEntityDescription(
        key="heating_energy_consumption",
        translation_key="heating_energy_consumption",
        name="Heating Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.HEAT,
        entity_registry_enabled_default=False,
    ),
    AquareaEnergySensorEntityDescription(
        key="tank_energy_consumption",
        translation_key="tank_energy_consumption",
        name="Tank Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.WATER_TANK,
        exists_fn=lambda coordinator: coordinator.device.has_tank,
        entity_registry_enabled_default=False,
    ),
    AquareaEnergySensorEntityDescription(
        key="cooling_energy_consumption",
        translation_key="cooling_energy_consumption",
        name="Cooling Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.COOL,
        exists_fn=lambda coordinator: any(zone.cool_mode for zone in coordinator.device.zones.values()),
        entity_registry_enabled_default=False,
    ),
    AquareaEnergySensorEntityDescription(
        key="energy_consumption",
        translation_key="energy_consumption",
        name="Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        consumption_type=aioaquarea.ConsumptionType.TOTAL,
        entity_registry_enabled_default=False,
    ),
]

# Daily edge counter descriptions
@dataclass(frozen=True, kw_only=True)
class AquareaDailyCounterEntityDescription(SensorEntityDescription):
    """Describes Aquarea daily counter sensor entity."""
    detector: Callable[[AquareaDevice], bool]


AQUAREA_DAILY_COUNTERS = [
    AquareaDailyCounterEntityDescription(
        key="dhw_cycles_today",
        translation_key="dhw_cycles_today",
        name="DHW Cycles Today",
        icon="mdi:water-boiler",
        device_class=SensorDeviceClass.ENUM,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        detector=lambda device: device.current_direction == aioaquarea.DeviceDirection.WATER,
    ),
    AquareaDailyCounterEntityDescription(
        key="zone_cycles_today",
        translation_key="zone_cycles_today",
        name="Zone Cycles Today",
        icon="mdi:radiator",
        device_class=SensorDeviceClass.ENUM,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        detector=lambda device: (
            device.current_direction == aioaquarea.DeviceDirection.PUMP
            and any(zone.operation_status == aioaquarea.OperationStatus.ON for zone in device.zones.values())
        ),
    ),
    AquareaDailyCounterEntityDescription(
        key="defrost_cycles_today",
        translation_key="defrost_cycles_today",
        name="Defrost Cycles Today",
        icon="mdi:snowflake-melt",
        device_class=SensorDeviceClass.ENUM,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        detector=lambda device: device.device_mode_status is aioaquarea.DeviceModeStatus.DEFROST,
    ),
]


def create_zone_temperature_description(zone: PanasonicDeviceZone):
    return PanasonicSensorEntityDescription(
        key = f"zone-{zone.id}-temperature",
        translation_key=f"zone-{zone.id}-temperature",
        name = f"{zone.name} Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        get_state=lambda device: zone.temperature,
        is_available=lambda device: zone.has_temperature
    )


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    data_coordinators: list[PanasonicDeviceCoordinator] = hass.data[DOMAIN][DATA_COORDINATORS]
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = hass.data[DOMAIN][ENERGY_COORDINATORS]
    aquarea_coordinators: list[AquareaDeviceCoordinator] = hass.data[DOMAIN][AQUAREA_COORDINATORS]

    for coordinator in data_coordinators:
        entities.append(PanasonicSensorEntity(coordinator, INSIDE_TEMPERATURE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, OUTSIDE_TEMPERATURE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, LAST_UPDATE_TIME_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, DATA_AGE_DESCRIPTION))
        entities.append(PanasonicSensorEntity(coordinator, DATA_MODE_DESCRIPTION))
        if coordinator.device.has_zones:
            for zone in coordinator.device.parameters.zones:
                entities.append(PanasonicSensorEntity(
                    coordinator,
                    create_zone_temperature_description(zone)))

    for coordinator in energy_coordinators:
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_COOLING_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, DAILY_HEATING_ENERGY_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, POWER_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, COOLING_POWER_DESCRIPTION))
        entities.append(PanasonicEnergySensorEntity(coordinator, HEATING_POWER_DESCRIPTION))

    for coordinator in aquarea_coordinators:
        entities.append(AquareaSensorEntity(coordinator, AQUAREA_OUTSIDE_TEMPERATURE_DESCRIPTION))
        entities.append(AquareaPumpDirectionSensor(coordinator))
        entities.append(AquareaPumpStatusSensor(coordinator))
        if coordinator.device.has_tank:
            entities.append(AquareaSensorEntity(coordinator, AQUAREA_TANK_TEMPERATURE_DESCRIPTION))
        # Daily edge counters
        for desc in AQUAREA_DAILY_COUNTERS:
            entities.append(AquareaDailyCounterSensor(coordinator, desc))
        # Accumulated energy sensors (month-to-date)
        for desc in AQUAREA_ACCUMULATED_ENERGY_SENSORS:
            if desc.exists_fn(coordinator):
                entities.append(AquareaEnergyAccumulatedConsumptionSensor(coordinator, desc))
        # Today's energy sensors (disabled by default)
        for desc in AQUAREA_ENERGY_SENSORS:
            if desc.exists_fn(coordinator):
                entities.append(AquareaEnergyConsumptionSensor(coordinator, desc))

    async_add_entities(entities)


class PanasonicSensorEntityBase(SensorEntity):
    """Base class for all sensor entities."""

    entity_description: PanasonicSensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

class PanasonicSensorEntity(PanasonicDataEntity, PanasonicSensorEntityBase):
    """Representation of a Panasonic sensor."""

    def __init__(
        self,
        coordinator: PanasonicDeviceCoordinator,
        description: PanasonicSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        super().__init__(coordinator, description.key)

    @property  # type: ignore[reportIncompatibleOverride]
    def available(self) -> bool:
        """Return if entity is available."""
        if self.entity_description.is_available is None:
            return True
        return self.entity_description.is_available(self.coordinator.device)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        if self.entity_description.is_available:
            self._attr_available = self.entity_description.is_available(self.coordinator.device)
        if self.entity_description.get_state:
            state = self.entity_description.get_state(self.coordinator.device)
            self._attr_native_value = state


class PanasonicEnergySensorEntity(PanasonicEnergyEntity, SensorEntity):
    """Representation of a Panasonic energy sensor."""

    entity_description: PanasonicEnergySensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(self, coordinator: PanasonicDeviceEnergyCoordinator, description: PanasonicEnergySensorEntityDescription):
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        super().__init__(coordinator, description.key)

    @property  # type: ignore[reportIncompatibleOverride]
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available
    
    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        energy = self.coordinator.energy
        if energy is None:
            return
        if self.entity_description.get_state is None:
            return
        value = self.entity_description.get_state(energy)
        self._attr_available = value is not None
        self._attr_native_value = value  # type: ignore[assignment]

class AquareaSensorEntity(AquareaDataEntity, SensorEntity):

    entity_description: AquareaSensorEntityDescription  # type: ignore[reportIncompatibleVariableOverride]

    def __init__(self, coordinator: AquareaDeviceCoordinator, description: AquareaSensorEntityDescription):
        self.entity_description = description  # type: ignore[reportIncompatibleVariableOverride]
        super().__init__(coordinator, description.key)

    @property  # type: ignore[reportIncompatibleOverride]
    def available(self) -> bool:
        """Return if entity is available."""
        if self.entity_description.is_available:
            return self.entity_description.is_available(self.coordinator.device)
        return True

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        if self.entity_description.is_available:
            self._attr_available = self.entity_description.is_available(self.coordinator.device)
        if self.entity_description.get_state:
            self._attr_native_value = self.entity_description.get_state(self.coordinator.device)


class AquareaPumpDirectionSensor(AquareaDataEntity, SensorEntity):
    """Sensor for the Aquarea pump direction."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "direction")
        self._attr_translation_key = "direction"
        self._attr_icon = "mdi:compass"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.device.current_direction.name
        super()._handle_coordinator_update()

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_native_value = self.coordinator.device.current_direction.name


class AquareaPumpStatusSensor(AquareaDataEntity, SensorEntity):
    """Sensor for the Aquarea pump status."""

    def __init__(self, coordinator: AquareaDeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "pump_status")
        self._attr_translation_key = "pump_status"
        self._attr_icon = "mdi:pump"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = "On" if self.coordinator.device.pump_duty == 1 else "Off"
        super()._handle_coordinator_update()

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        self._attr_native_value = "On" if self.coordinator.device.pump_duty == 1 else "Off"


class AquareaDailyCounterSensor(AquareaDataEntity, SensorEntity, RestoreEntity):
    """Sensor that counts daily edge transitions (DHW cycles, zone cycles, defrost cycles)."""

    entity_description: AquareaDailyCounterEntityDescription

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: AquareaDailyCounterEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_icon = description.icon
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_state_class = SensorStateClass.TOTAL
        self._count: int = 0
        self._last_state: bool = False
        self._last_date: datetime.date | None = None

    async def async_added_to_hass(self) -> None:
        """Restore count from previous session."""
        restored = await self.async_get_last_state()
        if restored is not None and restored.state not in (None, "unknown", "unavailable"):
            try:
                self._count = int(restored.state)
            except ValueError:
                self._count = 0
        await super().async_added_to_hass()

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        device = self.coordinator.device
        now = dt_util.now()
        today = now.date()

        # Reset counter at midnight
        if self._last_date is None or self._last_date != today:
            self._count = 0
            self._last_date = today
            self._last_state = False

        current_state = self.entity_description.detector(device)

        # Count rising edge transitions
        if current_state and not self._last_state:
            self._count += 1

        self._last_state = current_state
        self._attr_native_value = self._count


class AquareaEnergyAccumulatedConsumptionSensor(AquareaDataEntity, SensorEntity, RestoreEntity):
    """Sensor for accumulated (month-to-date) energy consumption from the Aquarea device."""

    entity_description: AquareaEnergySensorEntityDescription

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: AquareaEnergySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_suggested_display_precision = description.suggested_display_precision

    async def async_added_to_hass(self) -> None:
        """Restore value from previous session."""
        restored = await self.async_get_last_state()
        if restored is not None and restored.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_native_value = float(restored.state)
            except ValueError:
                self._attr_native_value = 0
        else:
            self._attr_native_value = 0
        await super().async_added_to_hass()

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        device = self.coordinator.device
        # Get consumption data via the device's method
        now = dt_util.now()
        # Try to get month-to-date consumption
        try:
            consumption = device.get_or_schedule_consumption(
                now, self.entity_description.consumption_type
            )
            if consumption is not None:
                self._attr_native_value = float(consumption)
        except aioaquarea.DataNotAvailableError:
            pass  # Keep last known value
        except Exception:
            pass  # Keep last known value


class AquareaEnergyConsumptionSensor(AquareaDataEntity, SensorEntity, RestoreEntity):
    """Sensor for today's energy consumption from the Aquarea device."""

    entity_description: AquareaEnergySensorEntityDescription

    def __init__(
        self,
        coordinator: AquareaDeviceCoordinator,
        description: AquareaEnergySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_suggested_display_precision = description.suggested_display_precision
        self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Restore value from previous session."""
        restored = await self.async_get_last_state()
        if restored is not None and restored.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_native_value = float(restored.state)
            except ValueError:
                self._attr_native_value = 0
        else:
            self._attr_native_value = 0
        await super().async_added_to_hass()

    def _async_update_attrs(self) -> None:
        """Update the attributes of the sensor."""
        device = self.coordinator.device
        now = dt_util.now()
        try:
            consumption = device.get_or_schedule_consumption(
                now, self.entity_description.consumption_type
            )
            if consumption is not None:
                self._attr_native_value = float(consumption)
        except aioaquarea.DataNotAvailableError:
            pass  # Keep last known value
        except Exception:
            pass  # Keep last known value