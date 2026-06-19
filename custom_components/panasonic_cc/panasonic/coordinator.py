"""Coordinators for Panasonic Comfort Cloud devices."""
import asyncio
import logging
from datetime import timedelta

from aiohttp import ClientResponseError
from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.storage import Store

from aio_panasonic_comfort_cloud import (
    ApiClient,
    PanasonicDevice,
    PanasonicDeviceInfo,
    PanasonicDeviceEnergy,
    ChangeRequestBuilder,
)

from ..const import (
    DOMAIN,
    MANUFACTURER,
    NOTIFICATION_AUTH_EXPIRED,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENERGY_FETCH_INTERVAL,
)

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


class PanasonicDeviceCoordinator(DataUpdateCoordinator[int]):
    """Panasonic device data coordinator."""

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
            name=f"Panasonic Device Coordinator ({device_info.name})",
            update_interval=timedelta(seconds=self._base_interval),
        )
        self._api_client = api_client
        self._device_info = device_info
        self._device: PanasonicDevice | None = None
        self._update_id = 0
        self._store = Store(hass, version=1, key=f"panasonic_cc_{device_info.id}")
        self._refresh_task: asyncio.Task | None = None
        self._consecutive_failures = 0
        self._auth_failed = False

    @property
    def device(self) -> PanasonicDevice:
        """Return the current device state."""
        if self._device is None:
            raise ValueError("Device has not been initialized")
        return self._device

    @property
    def api_client(self) -> ApiClient:
        """Return the API client."""
        return self._api_client

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

    def get_change_request_builder(self) -> ChangeRequestBuilder:
        """Get a change request builder for the current device."""
        return ChangeRequestBuilder(self.device)

    async def async_apply_changes(self, request_builder: ChangeRequestBuilder) -> None:
        """Apply changes to the device."""
        await self._api_client.set_device_raw(self.device, request_builder.build())

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

    async def async_get_stored_data(self) -> dict:
        """Get stored data."""
        data = await self._store.async_load()
        return data if data is not None else {}

    async def async_store_data(self, data: dict) -> None:
        """Store data."""
        await self._store.async_save(data)

    async def _async_update_data(self) -> int:
        """Fetch data from API."""
        if self._auth_failed:
            raise UpdateFailed("Authentication failed — coordinator disabled")

        try:
            if self._device is None:
                self._device = await self._api_client.get_device(self._device_info)
                _LOGGER.debug(
                    "%s Device features - Nanoe: %s, Eco Navi: %s, AI Eco: %s",
                    self._device_info.name,
                    self._device.has_nanoe,
                    self._device.has_eco_navi,
                    self._device.has_eco_function,
                )
                self._update_id = 1
                self._reset_backoff()
                return self._update_id
            if await self._api_client.try_update_device(self._device):
                self._update_id += 1
                self._reset_backoff()
                return self._update_id
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
            self._handle_failure()
            raise UpdateFailed(f"Invalid response from API: {err}") from err
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
        self.update_interval = timedelta(seconds=self._base_interval)

    def _handle_failure(self) -> None:
        """Handle API failure with exponential backoff."""
        self._consecutive_failures += 1
        new_interval = min(
            self._base_interval * (BACKOFF_MULTIPLIER ** self._consecutive_failures),
            MAX_UPDATE_INTERVAL,
        )
        self.update_interval = timedelta(seconds=new_interval)
        _LOGGER.warning(
            "%s API failure %d/%d — polling interval increased to %ds",
            self._device_info.name,
            self._consecutive_failures,
            MAX_CONSECUTIVE_FAILURES,
            new_interval,
        )


class PanasonicDeviceEnergyCoordinator(DataUpdateCoordinator[int]):
    """Panasonic device energy data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        api_client: ApiClient,
        device_info: PanasonicDeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        self._base_interval = config.get(
            CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"Panasonic Energy Coordinator ({device_info.name})",
            update_interval=timedelta(seconds=self._base_interval),
        )
        self._api_client = api_client
        self._device_info = device_info
        self._energy: PanasonicDeviceEnergy | None = None
        self._update_id = 0
        self._consecutive_failures = 0
        self._auth_failed = False

    @property
    def api_client(self) -> ApiClient:
        """Return the API client."""
        return self._api_client

    @property
    def device_id(self) -> str:
        """Return the device ID."""
        return self._device_info.id

    @property
    def energy(self) -> PanasonicDeviceEnergy | None:
        """Return the current energy data."""
        return self._energy

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

    async def _async_update_data(self) -> int:
        """Fetch energy data from API."""
        if self._auth_failed:
            raise UpdateFailed("Authentication failed — coordinator disabled")

        try:
            if self._energy is None:
                self._energy = await self._api_client.async_get_energy(self._device_info)
                self._update_id = 1
                self._reset_backoff()
                return self._update_id
            if await self._api_client.async_try_update_energy(self._energy):
                self._update_id += 1
                self._reset_backoff()
                return self._update_id
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
            self._handle_failure()
            raise UpdateFailed(f"Invalid response from API: {err}") from err
        return self._update_id

    def _reset_backoff(self) -> None:
        """Reset circuit breaker and restore base polling interval."""
        if self._consecutive_failures > 0:
            _LOGGER.debug(
                "%s Energy API recovered after %d consecutive failure(s)",
                self._device_info.name,
                self._consecutive_failures,
            )
        self._consecutive_failures = 0
        self.update_interval = timedelta(seconds=self._base_interval)

    def _handle_failure(self) -> None:
        """Handle API failure with exponential backoff."""
        self._consecutive_failures += 1
        new_interval = min(
            self._base_interval * (BACKOFF_MULTIPLIER ** self._consecutive_failures),
            MAX_UPDATE_INTERVAL,
        )
        self.update_interval = timedelta(seconds=new_interval)
        _LOGGER.warning(
            "%s Energy API failure %d/%d — polling interval increased to %ds",
            self._device_info.name,
            self._consecutive_failures,
            MAX_CONSECUTIVE_FAILURES,
            new_interval,
        )
