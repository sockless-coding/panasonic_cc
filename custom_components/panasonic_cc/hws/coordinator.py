"""Coordinators for HWS (standalone Heat Pump Hot Water tank) devices."""
import asyncio
import logging
from datetime import timedelta

from aiohttp import ClientResponseError
from homeassistant.components.persistent_notification import async_create
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo

from aio_panasonic_comfort_cloud import ApiClient, HwsDevice, PanasonicDeviceInfo

from ..const import (
    DEFAULT_DEVICE_FETCH_INTERVAL,
    CONF_DEVICE_FETCH_INTERVAL,
    DOMAIN,
    MANUFACTURER,
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


class HwsDeviceCoordinator(DataUpdateCoordinator[int]):
    """HWS device data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        api_client: ApiClient,
        device_info: PanasonicDeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        self._base_interval = config.get(
            CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"HWS Device Coordinator ({device_info.name})",
            update_interval=timedelta(seconds=self._base_interval),
        )
        self._api_client = api_client
        self._device_info = device_info
        self._device: HwsDevice | None = None
        self._update_id = 0
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
    def device(self) -> HwsDevice:
        """Return the current device state."""
        if self._device is None:
            raise ValueError("Device has not been initialized")
        return self._device

    @property
    def api_client(self) -> ApiClient:
        """Return the API client."""
        return self._api_client

    @property
    def info(self) -> PanasonicDeviceInfo:
        """Return the raw device info used for ApiClient.set_hws_* calls."""
        return self._device_info

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return self._device_info.id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_info.id)},
            manufacturer=MANUFACTURER,
            model=self._device_info.model,
            name=self._device_info.name,
            sw_version=self._api_client.app_version,
        )

    def _device_state_hash(self) -> int:
        """Compute a hash of the device state for change detection."""
        if self._device is None:
            return 0
        params = self._device.parameters
        return hash((
            params.hpu_operation_status,
            params.operation_mode,
            params.boost_mode,
            params.tank_temperature,
        ))

    async def _async_update_data(self) -> int:
        """Fetch data from API."""
        if self._auth_failed:
            raise UpdateFailed("Authentication failed — coordinator disabled")

        try:
            if self._device is None:
                self._device = self._api_client.get_hws_device(self._device_info)
                self._update_id = 1
                self._last_device_state_hash = self._device_state_hash()
                self._reset_backoff()
                return self._update_id
            if await self._api_client.try_update_hws_device(self._device):
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
                _LOGGER.error(
                    "%s Authentication has expired or is invalid. Please re-authenticate by removing and re-adding the integration.",
                    self._device_info.name,
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
