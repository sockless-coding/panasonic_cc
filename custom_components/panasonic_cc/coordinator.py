import logging

from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.storage import Store

from .pcomfortcloud.panasonicdevice import PanasonicDevice, PanasonicDeviceInfo
from .pcomfortcloud.apiclient import ApiClient
from .pcomfortcloud.changerequestbuilder import ChangeRequestBuilder
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
        self._store = Store(hass, version=1, key=f"panasonic_cc_{device_info.id}")
        
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
    
    def get_change_request_builder(self):
        return ChangeRequestBuilder(self._device)
    
    async def async_apply_changes(self, request_builder: ChangeRequestBuilder):
        await self._api_client.set_device_raw(self._device, request_builder.build())

    async def async_get_stored_data(self):
        data = await self._store.async_load()
        if data is None:
            data = {}
        return data
    
    async def async_store_data(self, data):
        await self._store.async_save(data)


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
