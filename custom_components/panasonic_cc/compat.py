"""Compatibility helpers for older Home Assistant releases."""
from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.water_heater import WaterHeaterEntity

# Home Assistant 2026.11 moved climate and water heater temperatures to the
# native_* API. Entities set the _attr_native_* attributes; on older releases
# the mixin below serves them through the old property names.
# Remove once the minimum supported version is 2026.11 or newer.
HAS_NATIVE_TEMPERATURE_API = hasattr(
    ClimateEntity, "native_temperature_unit"
) and hasattr(WaterHeaterEntity, "native_temperature_unit")

if HAS_NATIVE_TEMPERATURE_API:

    class NativeTemperatureCompat:
        """Nothing to do, Home Assistant reads the native attributes itself."""

else:

    class NativeTemperatureCompat:  # type: ignore[no-redef]
        """Serve the native temperature attributes through the old properties."""

        _attr_native_temperature_unit: str
        _attr_native_current_temperature: float | None = None
        _attr_native_target_temperature: float | None = None

        @property
        def temperature_unit(self) -> str:
            """Return the unit of measurement."""
            return self._attr_native_temperature_unit

        @property
        def current_temperature(self) -> float | None:
            """Return the current temperature."""
            return self._attr_native_current_temperature

        @property
        def target_temperature(self) -> float | None:
            """Return the target temperature."""
            return self._attr_native_target_temperature
