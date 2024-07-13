import logging

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .pcomfortcloud.panasonicdevice import PanasonicDevice, PanasonicDeviceInfo
from .pcomfortcloud.apiclient import ApiClient
from .const import DEFAULT_DEVICE_FETCH_INTERVAL, CONF_DEVICE_FETCH_INTERVAL

_LOGGER = logging.getLogger(__name__)

class PanasonicDeviceCoordinator(DataUpdateCoordinator[PanasonicDevice]):

    def __init__(self, hass: HomeAssistant, config: dict, api_client: ApiClient, device: PanasonicDeviceInfo):
        super().__init__(
            hass,
            _LOGGER,
            name="Panasonic Device Coordinator",
            update_interval=timedelta(seconds=config.get(CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL))
        )
        self._hass = hass
        self._config = config
        self._api_client = api_client
        self._device = device
        
    @property
    def device(self) -> PanasonicDeviceInfo:
        return self._device

    async def _async_update_data(self):
        try:
            if self.data is None:
                return await self._api_client.get_device(self._device.id)
            if await self._api_client.try_update_device(self.data):
               return self.data
        except BaseException as e:
            raise UpdateFailed(f"Invalid response from API: {e}") from e
