'''
Panasonic session, using Panasonic Comfort Cloud app api
'''

import hashlib
import re
import aiohttp
from urllib.parse import quote_plus

from . import constants
from . import panasonicsession


class ApiClient(panasonicsession.PanasonicSession):
    def __init__(self,
                 username,
                 password,
                 client: aiohttp.ClientSession,
                 token_file_name='~/.panasonic-settings',
                 raw=False):
        super().__init__(username, password, client, token_file_name, raw)

        self._groups = None
        self._devices = None
        self._device_indexer = {}
        self._raw = raw
        self._acc_client_id = None

    async def start_session(self):
        await super().start_session()
        await self._get_groups()

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

            for group in self._groups['groupList']:
                if 'deviceList' in group:
                    device_list = group.get('deviceList', [])
                else:
                    device_list = group.get('deviceIdList', [])

                for device in device_list:
                    if device:
                        if 'deviceHashGuid' in device:
                            device_id = device['deviceHashGuid']
                        else:
                            device_id = hashlib.md5(device['deviceGuid'].encode('utf-8')).hexdigest()

                        self._device_indexer[device_id] = device['deviceGuid']
                        self._devices.append({
                            'id': device_id,
                            'name': device['deviceName'],
                            'group': group['groupName'],
                            'model': device['deviceModuleNumber'] if 'deviceModuleNumber' in device else ''
                        })
        return self._devices

    def dump(self, device_id):
        device_guid = self._device_indexer.get(device_id)
        if device_guid:
            return self.execute_get(self._get_device_status_url(device_guid), "dump", 200)
        return None

    async def history(self, device_id, mode, date, time_zone="+01:00"):
        device_guid = self._device_indexer.get(device_id)

        if device_guid:
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
        return None

    async def get_device(self, device_id):
        device_guid = self._device_indexer.get(device_id)

        if device_guid:
            json_response = await self.execute_get(self._get_device_status_url(device_guid), "get_device", 200)
            return {
                'id': device_id,
                'parameters': self._read_parameters(json_response['parameters'])
            }
        return None

    async def set_device(self, device_id, **kwargs):
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

        # routine to set the auto mode of fan (either horizontal, vertical, both or disabled)
        if air_x is not None or air_y is not None:
            fan_auto = 0
            device = self.get_device(device_id)

            if device and device['parameters']['airSwingHorizontal'].value == -1:
                fan_auto = fan_auto | 1

            if device and device['parameters']['airSwingVertical'].value == -1:
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

        device_guid = self._device_indexer.get(device_id)
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
            base_url=panasonicsession.PanasonicSession.BASE_PATH_ACC
        )

    def _get_device_status_url(self, guid):
        return '{base_url}/deviceStatus/{guid}'.format(
            base_url=panasonicsession.PanasonicSession.BASE_PATH_ACC,
            guid=re.sub('(?i)2f', 'f', quote_plus(guid))
        )

    def _get_device_status_now_url(self, guid):
        return '{base_url}/deviceStatus/now/{guid}'.format(
            base_url=panasonicsession.PanasonicSession.BASE_PATH_ACC,
            guid=re.sub('(?i)2f', 'f', quote_plus(guid))
        )

    def _get_device_status_control_url(self):
        return '{base_url}/deviceStatus/control'.format(
            base_url=panasonicsession.PanasonicSession.BASE_PATH_ACC
        )

    def _get_device_history_url(self):
        return '{base_url}/deviceHistoryData'.format(
            base_url=panasonicsession.PanasonicSession.BASE_PATH_ACC,
        )
