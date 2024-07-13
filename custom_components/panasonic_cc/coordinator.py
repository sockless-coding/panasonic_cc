import logging

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo

from .pcomfortcloud.panasonicdevice import PanasonicDevice, PanasonicDeviceInfo
from .pcomfortcloud.apiclient import ApiClient
from .const import DOMAIN,MANUFACTURER, DEFAULT_DEVICE_FETCH_INTERVAL, CONF_DEVICE_FETCH_INTERVAL

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
        self._panasonic_device_info = device_info
        self._device:PanasonicDevice = None
        
    @property
    def device(self) -> PanasonicDevice:
        return self._device
    
    @property
    def api_client(self) -> ApiClient:
        return self._api_client
    
    @property
    def device_info(self)->DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._panasonic_device_info.id )},
            manufacturer=MANUFACTURER,
            model=self._panasonic_device_info.model,
            name=self._panasonic_device_info.name,
            sw_version=self._api_client.app_version
        )

    async def _fetch_device_data(self)->int:
        try:
            if self._device is None:
                self._device = await self._api_client.get_device(self._panasonic_device_info)
                return 1
            if await self._api_client.try_update_device(self._device):
               return self.data+1
        except BaseException as e:
            raise UpdateFailed(f"Invalid response from API: {e}") from e
        return self.data
