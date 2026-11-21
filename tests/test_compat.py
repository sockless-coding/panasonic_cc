"""Tests for the native temperature compatibility mixin."""
from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import UnitOfTemperature

from custom_components.panasonic_cc.aquarea.climate import AquareaClimateEntity
from custom_components.panasonic_cc.aquarea.water_heater import AquareaWaterHeater
from custom_components.panasonic_cc.compat import NativeTemperatureCompat
from custom_components.panasonic_cc.hws.water_heater import HwsWaterHeater
from custom_components.panasonic_cc.panasonic.climate import PanasonicClimateEntity


class _Climate(NativeTemperatureCompat, ClimateEntity):
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS


class _WaterHeater(NativeTemperatureCompat, WaterHeaterEntity):
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS


def _native_values(entity) -> tuple:
    """Read the temperatures the way the running Home Assistant does."""
    if hasattr(entity, "native_temperature_unit"):
        return (
            entity.native_temperature_unit,
            entity.native_current_temperature,
            entity.native_target_temperature,
        )
    return entity.temperature_unit, entity.current_temperature, entity.target_temperature


def test_climate_serves_native_temperatures() -> None:
    entity = _Climate()
    assert _native_values(entity) == (UnitOfTemperature.CELSIUS, None, None)
    entity._attr_native_current_temperature = 21.5
    entity._attr_native_target_temperature = 23
    assert _native_values(entity) == (UnitOfTemperature.CELSIUS, 21.5, 23)


def test_water_heater_serves_native_temperatures() -> None:
    entity = _WaterHeater()
    entity._attr_native_current_temperature = 48
    entity._attr_native_target_temperature = 50
    assert _native_values(entity) == (UnitOfTemperature.CELSIUS, 48, 50)


def test_entities_use_the_mixin() -> None:
    for cls in (
        PanasonicClimateEntity,
        AquareaClimateEntity,
        AquareaWaterHeater,
        HwsWaterHeater,
    ):
        assert cls.__mro__[1] is NativeTemperatureCompat
