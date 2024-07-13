import logging

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .pcomfortcloud.panasonicdevice import PanasonicDevice, PanasonicDeviceInfo
from .pcomfortcloud.apiclient import ApiClient
from .const import DEFAULT_DEVICE_FETCH_INTERVAL, CONF_DEVICE_FETCH_INTERVAL

_LOGGER = logging.getLogger(__name__)

class PanasonicDeviceCoordinator(DataUpdateCoordinator[int]):

    def __init__(self, hass: HomeAssistant, config: dict, api_client: ApiClient, device_info: PanasonicDeviceInfo):
        super().__init__(
            hass,
            _LOGGER,
            name="Panasonic Device Coordinator",
            update_interval=timedelta(seconds=config.get(CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL)),
            update_method=self._fetch_device_data,
        )
        self._hass = hass
        self._config = config
        self._api_client = api_client
        self._device_info = device_info
        self._device = None
        
    @property
    def device(self) -> PanasonicDevice:
        return self._device

    async def _fetch_device_data(self)->int:
        try:
            if self._device is None:
                self._device = await self._api_client.get_device(self._device_info.id)
                return 1
            if await self._api_client.try_update_device(self._device):
               return self.data+1
        except BaseException as e:
            raise UpdateFailed(f"Invalid response from API: {e}") from e
        return self.data
