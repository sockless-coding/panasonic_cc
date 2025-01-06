'''
Panasonic session, using Panasonic Comfort Cloud app api
'''

import logging
import aiohttp
import time
from datetime import datetime
from urllib.parse import quote_plus
import json


from . import constants, testdata
from . import panasonicsession
from .panasonicdevice import PanasonicDevice, PanasonicDeviceInfo, PanasonicDeviceEnergy


_LOGGER = logging.getLogger(__name__)

_current_time_zone = None
_current_time_zone_date = None

def get_current_time_zone():
    global _current_time_zone
    today_date = datetime.now().date()
    if _current_time_zone is not None and today_date == _current_time_zone_date:
        return _current_time_zone
    local_offset_seconds = -time.timezone
    if time.localtime().tm_isdst:
        local_offset_seconds += 3600
    hours, remainder = divmod(abs(local_offset_seconds), 3600)
    minutes = remainder // 60
    _current_time_zone = f"{'+' if local_offset_seconds >= 0 else '-'}{int(hours):02}:{int(minutes):02}"
    _current_time_zone_date = today_date
    return _current_time_zone
    


class ApiClient(panasonicsession.PanasonicSession):
    def __init__(self,
                 username,
                 password,
                 client: aiohttp.ClientSession,
                 token_file_name='~/.panasonic-settings',
                 raw=False):
        super().__init__(username, password, client, token_file_name, raw)

        self._groups = None
        self._devices: list[PanasonicDeviceInfo] = None
        self._unknown_devices: list[PanasonicDeviceInfo] = []
        self._cache_devices = {}

        self._device_indexer = {}
        self._raw = raw
        self._acc_client_id = None

    @property
    def unknown_devices(self):
        return self._unknown_devices
    
    @property
    def has_unknown_devices(self):
        return len(self._unknown_devices) > 0

    async def start_session(self):
        await super().start_session()
        try:
            await self._get_groups()
        except Exception as ex:
            _LOGGER.warning("Could not get groups, trying to re-authenticate", exc_info= ex)
            await self.reauthenticate()
            await self._get_groups()

    async def reauthenticate(self):
        await super().reauthenticate()
        await self._get_groups()    


    async def refresh_token(self):
        await super().start_session()

    async def _get_groups(self):
        self._groups = await self.execute_get(
            self._get_group_url(),
            "get_groups",
            200
        )
        self._devices = None

    def get_devices(self):
        if self._devices is None:
            self._devices = []
            self._unknown_devices = []

            for group in self._groups['groupList']:
                if 'deviceList' in group:
                    device_list = group.get('deviceList', [])
                else:
                    device_list = group.get('deviceIdList', [])

                for device in device_list:
                    if device:
                        device_info = PanasonicDeviceInfo(device)
                        if device_info.is_valid:
                            self._device_indexer[device_info.id] = device_info.guid
                            self._devices.append(device_info)
                        else:
                            self._unknown_devices.append(device_info)

            #self._unknown_devices.append(PanasonicDeviceInfo(get_dummy_aquarea_device_json()))
        return self._devices

    def dump(self, device_id):
        device_guid = self._device_indexer.get(device_id)
        if device_guid:
            return self.execute_get(self._get_device_status_url(device_guid), "dump", 200)
        return None
    
    async def check_aquarea(self):
        if self.has_unknown_devices:

            _LOGGER.warning(f"""Found {len(self.unknown_devices)} unknown device(s):
{"\n ".join(json.dumps(obj.raw) for obj in self.unknown_devices)}
Submit this log to https://github.com/sockless-coding/panasonic_cc/issues/310
""")
            for device in self.unknown_devices:
                try:
                    aqua_device = await self.get_aquarea_device(device)
                    _LOGGER.warning(f"""Got aquarea device info for: {device.guid}:
{json.dumps(aqua_device)}
Submit this log to https://github.com/sockless-coding/panasonic_cc/issues/310""")
                except Exception as e:
                    _LOGGER.warning(f"""Failed to get aquarea device info for {device.guid}
Submit this log to https://github.com/sockless-coding/panasonic_cc/issues/310""", exc_info=e)

    async def history(self, device_id, mode, date, time_zone=""):
        device_guid = self._device_indexer.get(device_id)
        if not device_guid:
            return None
        if not time_zone:
            time_zone = get_current_time_zone()
        try:
            data_mode = constants.DataMode[mode].value
        except KeyError:
            raise Exception("Wrong mode parameter")

        payload = {
            "deviceGuid": device_guid,
            "dataMode": data_mode,
            "date": date,
            "osTimezone": time_zone
        }

        json_response = await self.execute_post(self._get_device_history_url(), payload, "history", 200)

        return {
            'id': device_id,
            'parameters': self._read_parameters(json_response)
        }
    
    
    async def _get_device_status(self, device_info: PanasonicDeviceInfo):
        if (device_info.status_data_mode == constants.StatusDataMode.LIVE 
            or (device_info.id in self._cache_devices and self._cache_devices[device_info.id] <= 0)):
            try:
                json_response = await self.execute_get(self._get_device_status_url(device_info.guid), "get_status", 200)
                device_info.status_data_mode = constants.StatusDataMode.LIVE
                return json_response
            except Exception as e:
                _LOGGER.warning("Failed to get live status for device {} switching to cached data.".format(device_info.guid))
                device_info.status_data_mode = constants.StatusDataMode.CACHED
                self._cache_devices[device_info.id] = 10
        json_response = await self.execute_get(self._get_device_status_now_url(device_info.guid), "get_status", 200)
        self._cache_devices[device_info.id] -= 1   
        return json_response

    async def get_device(self, device_info: PanasonicDeviceInfo) -> PanasonicDevice:
        json_response = await self._get_device_status(device_info)
        return PanasonicDevice(device_info, json_response)
    
    async def try_update_device(self, device: PanasonicDevice) -> bool:
        json_response = await self._get_device_status(device.info)
        return device.load(json_response)
    
    async def get_aquarea_device(self, device_info: PanasonicDeviceInfo):
        id_cookies = dict(selectedGwid=device_info.guid)
        id_response = await self.execute_aqua_post(
            url="https://aquarea-smart.panasonic.com/remote/contract",
            function_description="Get Aquarea device id",
            expected_status_code=200,
            cookies=id_cookies,
        )
        device_id = id_response.cookies.get("selectedDeviceId").value
        _LOGGER.debug("Aquarea Device ID for {} is {}".format(device_info.guid, device_id))
        status_response = await self.execute_aqua_get(
            self._get_aquarea_device_info_url(device_id), 
            "Get Aquarea device info", 200)
        response_text = await status_response.text()
        _LOGGER.debug("Got response: %s", response_text)
        return json.loads(response_text)
    
    async def async_get_energy(self, device_info: PanasonicDeviceInfo) -> PanasonicDeviceEnergy | None:
        todays_item = await self._async_get_todays_energy(device_info)
        if todays_item is None:
            return None
        return PanasonicDeviceEnergy(device_info, todays_item)
    
    async def async_try_update_energy(self, energy: PanasonicDeviceEnergy) -> bool:
        todays_item = await self._async_get_todays_energy(energy.info)
        return energy.load(todays_item)
    
    async def _async_get_todays_energy(self, device_info: PanasonicDeviceInfo):
        today = datetime.now().strftime("%Y%m%d")
        device_guid = device_info.guid
        if not device_guid:
            return None


        payload = {
            "deviceGuid": device_guid,
            "dataMode": constants.DataMode.Month.value,
            "date": today,
            "osTimezone": get_current_time_zone()
        }

        history = await self.execute_post(self._get_device_history_url(), payload, "get_todays_energy", 200)

        if history is None:
            return None
        if 'historyDataList' not in history:
            return None
        history_items = history['historyDataList']
        todays_item = None
        for item in history_items:
            if 'dataTime' not in item:
                continue
            if item['dataTime'] != today:
                continue
            todays_item = item
            break
        return todays_item
        
    
    async def set_horizontal_swing(self, device:PanasonicDevice, new_value: str | constants.AirSwingLR):
        """ Set horizontal swing"""
        if isinstance(new_value, str):
            new_value = constants.AirSwingLR[new_value]
        fan_auto = (constants.AirSwingAutoMode.AirSwingLR 
                    if new_value == constants.AirSwingLR.Auto 
                    else constants.AirSwingAutoMode.Disabled)
        if device.parameters.vertical_swing_mode == constants.AirSwingUD.Auto:
            fan_auto = (constants.AirSwingAutoMode.Both 
                        if new_value == constants.AirSwingLR.Auto 
                        else constants.AirSwingAutoMode.AirSwingUD)

        await self.set_device_raw(
            device,
            { 
                "operate": constants.Power.On,
                "airSwingLR": new_value.value,
                "fanAutoMode": fan_auto.value
            })
        
    async def set_vertical_swing(self, device:PanasonicDevice, new_value: str | constants.AirSwingUD):
        """ Set vertical swing"""
        if isinstance(new_value, str):
            new_value = constants.AirSwingUD[new_value]
        fan_auto = (constants.AirSwingAutoMode.AirSwingUD 
                    if new_value == constants.AirSwingUD.Auto 
                    else constants.AirSwingAutoMode.Disabled)
        if device.parameters.horizontal_swing_mode == constants.AirSwingLR.Auto:
            fan_auto = (constants.AirSwingAutoMode.Both 
                        if new_value == constants.AirSwingUD.Auto 
                        else constants.AirSwingAutoMode.AirSwingLR)

        await self.set_device_raw(
            device,
            { 
                "operate": constants.Power.On,
                "airSwingUD": new_value.value,
                "fanAutoMode": fan_auto.value
            })
        
    async def set_nanoe_mode(self, device:PanasonicDevice, new_value: str | constants.NanoeMode):
        """ Set Nanoe mode"""
        if isinstance(new_value, str):
            new_value = constants.NanoeMode[new_value]
        await self.set_device_raw(
            device,
            {
                "nanoe", new_value.value
            })
        
    async def set_eco_navi_mode(self, device:PanasonicDevice, new_value: str | constants.EcoNaviMode):
        """ Set EcoNavi mode"""
        if isinstance(new_value, str):
            new_value = constants.EcoNaviMode[new_value]
        await self.set_device_raw(
            device,
            {
                "ecoNavi", new_value.value
            })
        
    async def set_eco_function_mode(self, device:PanasonicDevice, new_value: str | constants.EcoFunctionMode):
        """ Set EcoFunction mode"""
        if isinstance(new_value, str):
            new_value = constants.EcoFunctionMode[new_value]
        await self.set_device_raw(
            device,
            {
                "ecoFunctionData", new_value.value
            })

    async def set_device_raw(self, device:PanasonicDevice, parameters):
        """ Set parameters of device"""
        payload = {
            "deviceGuid": device.info.guid,
            "parameters": parameters
        }
        await self.execute_post(self._get_device_status_control_url(), payload, "set_device", 200)


    async def set_device(self, device_info: PanasonicDeviceInfo, **kwargs):
        """ Set parameters of device

        Args:
            device_id  (str): Id of the device
            kwargs   : {temperature=float}, {mode=OperationMode}, {fanSpeed=FanSpeed}, {power=Power},
                       {airSwingHorizontal=}, {airSwingVertical=}, {eco=EcoMode}
        """

        parameters = {}
        air_x = None
        air_y = None

        if kwargs is not None:
            for key, value in kwargs.items():
                if key == 'power' and isinstance(value, constants.Power):
                    parameters['operate'] = value.value

                if key == 'temperature':
                    parameters['temperatureSet'] = value

                if key == 'mode' and isinstance(value, constants.OperationMode):
                    parameters['operationMode'] = value.value

                if key == 'fanSpeed' and isinstance(value, constants.FanSpeed):
                    parameters['fanSpeed'] = value.value

                if key == 'airSwingHorizontal' and isinstance(value, constants.AirSwingLR):
                    air_x = value

                if key == 'airSwingVertical' and isinstance(value, constants.AirSwingUD):
                    air_y = value

                if key == 'eco' and isinstance(value, constants.EcoMode):
                    parameters['ecoMode'] = value.value

                if key == 'nanoe' and \
                        isinstance(value, constants.NanoeMode) and \
                        value != constants.NanoeMode.Unavailable:
                    parameters['nanoe'] = value.value

                if key == 'ecoNavi' and isinstance(value, constants.EcoNaviMode):
                    parameters['ecoNavi'] = value.value

                if key == 'ecoFunctionData' and isinstance(value, constants.EcoFunctionMode):
                    parameters['ecoFunctionData'] = value.value

                if key == 'zoneParameters' and value is not None:
                    parameters['zoneParameters'] = value

        # routine to set the auto mode of fan (either horizontal, vertical, both or disabled)
        if air_x is not None or air_y is not None:
            fan_auto = 0
            device = await self.get_device(device_info)

            if device and device.parameters.horizontal_swing_mode == constants.AirSwingLR.Auto:
                fan_auto = fan_auto | 1

            if device and device.parameters.vertical_swing_mode == constants.AirSwingUD.Auto:
                fan_auto = fan_auto | 2

            if air_x is not None:
                if air_x.value == -1:
                    fan_auto = fan_auto | 1
                else:
                    fan_auto = fan_auto & ~1
                    parameters['airSwingLR'] = air_x.value

            if air_y is not None:
                if air_y.value == -1:
                    fan_auto = fan_auto | 2
                else:
                    fan_auto = fan_auto & ~2
                    print(air_y.name)
                    parameters['airSwingUD'] = air_y.value

            if fan_auto == 3:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.Both.value
            elif fan_auto == 1:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.AirSwingLR.value
            elif fan_auto == 2:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.AirSwingUD.value
            else:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.Disabled.value

        device_guid = device_info.guid
        if device_guid:
            payload = {
                "deviceGuid": device_guid,
                "parameters": parameters
            }
            _ = await self.execute_post(self._get_device_status_control_url(), payload, "set_device", 200)
            return True
        return False

    def _read_parameters(self, parameters=dict()):
        value = dict()

        _convert = {
            'insideTemperature': 'temperatureInside',
            'outTemperature': 'temperatureOutside',
            'temperatureSet': 'temperature',
            'currencyUnit': 'currencyUnit',
            'energyConsumption': 'energyConsumption',
            'estimatedCost': 'estimatedCost',
            'historyDataList': 'historyDataList',
        }
        for key in _convert:
            if key in parameters:
                value[_convert[key]] = parameters[key]

        if 'operate' in parameters:
            value['power'] = constants.Power(parameters['operate'])

        if 'operationMode' in parameters:
            value['mode'] = constants.OperationMode(
                parameters['operationMode'])

        if 'fanSpeed' in parameters:
            value['fanSpeed'] = constants.FanSpeed(parameters['fanSpeed'])

        if 'airSwingLR' in parameters:
            value['airSwingHorizontal'] = constants.AirSwingLR(
                parameters['airSwingLR'])

        if 'airSwingUD' in parameters:
            value['airSwingVertical'] = constants.AirSwingUD(
                parameters['airSwingUD'])

        if 'ecoMode' in parameters:
            value['eco'] = constants.EcoMode(parameters['ecoMode'])

        if 'nanoe' in parameters:
            value['nanoe'] = constants.NanoeMode(parameters['nanoe'])

        if 'fanAutoMode' in parameters:
            if parameters['fanAutoMode'] == constants.AirSwingAutoMode.Both.value:
                value['airSwingHorizontal'] = constants.AirSwingLR.Auto
                value['airSwingVertical'] = constants.AirSwingUD.Auto
            elif parameters['fanAutoMode'] == constants.AirSwingAutoMode.AirSwingLR.value:
                value['airSwingHorizontal'] = constants.AirSwingLR.Auto
            elif parameters['fanAutoMode'] == constants.AirSwingAutoMode.AirSwingUD.value:
                value['airSwingVertical'] = constants.AirSwingUD.Auto

        return value

    def _get_group_url(self):
        return '{base_url}/device/group'.format(
            base_url=constants.BASE_PATH_ACC
        )

    def _get_device_status_url(self, guid):
        return '{base_url}/deviceStatus/{guid}'.format(
            base_url=constants.BASE_PATH_ACC,
            guid=self._prepare_device_guid(guid)
        )

    def _get_device_status_now_url(self, guid):
        return '{base_url}/deviceStatus/now/{guid}'.format(
            base_url=constants.BASE_PATH_ACC,
            guid=self._prepare_device_guid(guid)
        )
    
    def _get_aquarea_device_info_url(self, device_id):
        return '{base_url}/remote/v1/api/devices/{device_id}?var.deviceDirect=1'.format(
            base_url="https://aquarea-smart.panasonic.com",
            device_id=device_id
        )

    def _get_device_status_control_url(self):
        return '{base_url}/deviceStatus/control'.format(
            base_url=constants.BASE_PATH_ACC
        )

    def _get_device_history_url(self):
        return '{base_url}/deviceHistoryData'.format(
            base_url=constants.BASE_PATH_ACC,
        )
    
    def _prepare_device_guid(self, device_guid: str):
        device_guid = device_guid.replace("/", "f")
        return quote_plus(device_guid, encoding='utf-8')
