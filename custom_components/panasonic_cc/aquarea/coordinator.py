"""Coordinators for Aquarea devices."""
import asyncio
import logging
from datetime import timedelta

from aiohttp import ClientResponseError
from homeassistant.components.persistent_notification import async_create
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo

from aioaquarea import (
    Client as AquareaApiClient,
    Device as AquareaDevice,
)
from aioaquarea.data import DeviceInfo as AquareaDeviceInfo

from ..const import (
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENERGY_FETCH_INTERVAL,
    DOMAIN,
    NOTIFICATION_AUTH_EXPIRED,
)
from ..error_handler import classify_error, FriendlyError, ErrorCategory

MAX_CONSECUTIVE_FAILURES = 5
BACKOFF_MULTIPLIER = 2
MAX_UPDATE_INTERVAL = 600  # seconds

_LOGGER = logging.getLogger(__name__)


def _is_auth_error(err: Exception) -> bool:
    """Check if an exception is caused by authentication failure."""
    if isinstance(err, ClientResponseError) and err.status == 401:
        return True
    error_str = str(err).lower()
    return any(kw in error_str for kw in ["401", "unauthorized", "authentication", "token", "expired", "invalid session"])


def _create_auth_expired_notification(hass: HomeAssistant) -> None:
    """Create a persistent notification for expired authentication."""
    async_create(
        hass,
        message="Panasonic Comfort Cloud authentication has expired. Please re-authenticate by removing and re-adding the integration.",
        title="Panasonic Comfort Cloud - Authentication Expired",
        notification_id=NOTIFICATION_AUTH_EXPIRED,
    )


class AquareaDeviceCoordinator(DataUpdateCoordinator[int]):
    """Aquarea device data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        api_client: AquareaApiClient,
        device_info: AquareaDeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        self._base_interval = config.get(
            CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"Aquarea Device Coordinator ({device_info.name})",
            update_interval=timedelta(seconds=self._base_interval),
        )
        self._api_client = api_client
        self._device_info = device_info
        self._device: AquareaDevice | None = None
        self._update_id = 0
        self._config = dict(config)
        self._refresh_task: asyncio.Task | None = None
        self._consecutive_failures = 0
        self._auth_failed = False
        self._last_device_state_hash: int | None = None
        self._last_error: FriendlyError | None = None

    @property
    def last_error(self) -> FriendlyError | None:
        """Return the last error that occurred."""
        return self._last_error

    @property
    def connection_status(self) -> str:
        """Return the current connection status."""
        if self._auth_failed:
            return "authentication_error"
        if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return "disconnected"
        if self._consecutive_failures > 0:
            return "degraded"
        return "connected"

    @property
    def device(self) -> AquareaDevice:
        """Return the current device state."""
        if self._device is None:
            raise ValueError("Device has not been initialized")
        return self._device

    @property
    def api_client(self) -> AquareaApiClient:
        """Return the API client."""
        return self._api_client

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return self.device.device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=self.device.manufacturer,
            model=self.device.model or "",
            name=self.device.device_name,
            sw_version=self.device.firmware_version,
        )

    def _device_state_hash(self) -> int:
        """Compute a hash of the device state for change detection."""
        if self._device is None:
            return 0
        state = (
            self._device.mode,
            self._device.current_direction,
            self._device.special_status,
            self._device.force_dhw,
            self._device.force_heater,
            self._device.quiet_mode,
            self._device.powerful_time,
            self._device.tank.target_temperature if self._device.tank else None,
            self._device.tank.temperature if self._device.tank else None,
            self._device.tank.operation_status if self._device.tank else None,
            tuple(
                (
                    z.operation_status,
                    z.temperature,
                    z.heat_target_temperature,
                    z.cool_target_temperature,
                )
                for z in self._device.zones.values()
            ),
        )
        return hash(state)

    async def _async_update_data(self) -> int:
        """Fetch data from API."""
        if self._auth_failed:
            raise UpdateFailed("Authentication failed — coordinator disabled")

        try:
            if self._device is None:
                self._device = await self._api_client.get_device(
                    device_info=self._device_info,
                    consumption_refresh_interval=timedelta(
                        seconds=self._config.get(CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL)
                    ),
                )
                self._update_id = 1
                self._last_device_state_hash = self._device_state_hash()
                self._reset_backoff()
                return self._update_id
            await self._device.refresh_data()
            current_hash = self._device_state_hash()
            if current_hash != self._last_device_state_hash:
                self._last_device_state_hash = current_hash
                self._update_id += 1
                self._reset_backoff()
                return self._update_id
            self._reset_backoff()
        except Exception as err:
            if _is_auth_error(err):
                self._auth_failed = True
                device_name = self.device.device_name if self._device else self._device_info.name
                _LOGGER.error(
                    "%s Authentication has expired or is invalid. Please re-authenticate by removing and re-adding the integration.",
                    device_name,
                    exc_info=True,
                )
                _create_auth_expired_notification(self.hass)
                raise UpdateFailed("Authentication failed — coordinator disabled") from err
            self._handle_failure(err)
            friendly = classify_error(err)
            raise UpdateFailed(f"{friendly.title}: {friendly.message}") from err
        return self._update_id

    def _reset_backoff(self) -> None:
        """Reset circuit breaker and restore base polling interval."""
        if self._consecutive_failures > 0:
            _LOGGER.debug(
                "%s API recovered after %d consecutive failure(s)",
                self._device_info.name,
                self._consecutive_failures,
            )
        self._consecutive_failures = 0
        self._last_error = None
        self.update_interval = timedelta(seconds=self._base_interval)

    def _handle_failure(self, err: Exception | None = None) -> None:
        """Handle API failure with exponential backoff."""
        self._consecutive_failures += 1
        new_interval = min(
            self._base_interval * (BACKOFF_MULTIPLIER ** self._consecutive_failures),
            MAX_UPDATE_INTERVAL,
        )
        self.update_interval = timedelta(seconds=new_interval)
        if err is not None:
            self._last_error = classify_error(err)
            _LOGGER.warning(
                "%s API failure %d/%d — %s: %s — polling interval increased to %ds",
                self._device_info.name,
                self._consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
                self._last_error.title,
                self._last_error.message,
                new_interval,
            )
        else:
            _LOGGER.warning(
                "%s API failure %d/%d — polling interval increased to %ds",
                self._device_info.name,
                self._consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
                new_interval,
            )

    async def async_schedule_refresh(self) -> None:
        """Schedule a debounced refresh of device data."""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None

        async def _delayed_refresh() -> None:
            try:
                await asyncio.sleep(2)
                await self.async_request_refresh()
            except asyncio.CancelledError:
                pass
            finally:
                self._refresh_task = None

        self._refresh_task = self.hass.async_create_task(_delayed_refresh())
