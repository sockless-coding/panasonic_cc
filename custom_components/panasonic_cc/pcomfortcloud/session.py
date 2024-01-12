'''
Panasonic session, using Panasonic Comfort Cloud app api
'''

import json
import requests
import os
import urllib3
import hashlib
import logging
import datetime

from . import urls
from . import constants
from .settings import PanasonicSettings

def _validate_response(response):
    """ Verify that response is OK """
    if response.status_code == 200:
        return
    raise ResponseError(response.status_code, response.text)

_LOGGER = logging.getLogger(__name__)

class Error(Exception):
    ''' Panasonic session error '''
    pass

class RequestError(Error):
    ''' Wrapped requests.exceptions.RequestException '''
    pass


class LoginError(Error):
    ''' Login failed '''
    pass

class ResponseError(Error):
    ''' Unexcpected response '''
    def __init__(self, status_code, text):
        super(ResponseError, self).__init__(
            'Invalid response'
            ', status code: {0} - Data: {1}'.format(
                status_code,
                text))
        self.status_code = status_code
        self.text = text


class Session(object):
    """ Verisure app session

    Args:
        username (str): Username used to login to verisure app
        password (str): Password used to login to verisure app

    """

    def __init__(self, username, password, settingsFileName='~/.panasonic-settings', raw=False, verifySsl=True):
        self._username = username
        self._password = password
        self._settings = PanasonicSettings(os.path.expanduser(settingsFileName))
        self._vid = None
        
        self._appVersion = self._settings._version
        self._groups = None
        self._devices = None
        self._deviceIndexer = {}
        self._raw = raw


        if verifySsl == False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self._verifySsl = verifySsl
        else:
            self._verifySsl = os.path.join(os.path.dirname(__file__),
                    "certificatechain.pem")

        

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def login(self):
        """ Login to verisure app api """
        
        if self._settings.token is not None:
            self._vid = self._settings.token
            if self._raw: print("--- token found")

            try:
                self._get_groups()

            except ResponseError:
                if self._raw: print("--- token probably expired")

                self._vid = None
                self._devices = None
                self._settings.token = None

        if self._vid is None:
            self._create_token()
            self._settings.token = self._vid

            self._get_groups()

    def logout(self):
        """ Logout """

    def _headers(self):
        if self._settings.version_expired:
            self._updateAppVersion()
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')        
        return {
            "X-APP-TYPE": "1",
            "X-APP-VERSION": self._appVersion,
            "X-User-Authorization": self._vid,
            "X-APP-NAME": "Comfort Cloud",
            "X-APP-TIMESTAMP":formatted_time,
            "X-CFC-API-KEY":"0",
            "User-Agent": "G-RAC",
            "Accept": "application/json; charset=utf-8",
            "Content-Type": "application/json; charset=utf-8"
        }

    def _updateAppVersion(self):
        
        if self._raw: print("--- auto detecting latest app version")
        try:            
            data = requests.get("https://itunes.apple.com/lookup?id=1348640525").json()
            version = data['results'][0]['version']
            if version is not None:
                if self._raw: print("--- found version: {}".format(version))
                self._appVersion = version
                self._settings.version = version
                return
        except Exception as e:
            _LOGGER.warning(f"Get version: {e}")
            pass
        if self._raw: print("--- failed to detect app version using version: {}".format(self._appVersion))

    def _create_token(self):
        response = None
        
        payload = {
            "clientId": self._settings.clientId,
            "language": 0,
            "loginId": self._username,
            "password": self._password
        }
        
        if self._raw: 
            print("--- creating token by authenticating")
            print("--- Using version: {}".format(self._appVersion))

        try:
            response = requests.post(urls.login(), json=payload, headers=self._headers(), verify=self._verifySsl)
            if 2 != response.status_code // 100:
                raise ResponseError(response.status_code, response.text)

        except requests.exceptions.RequestException as ex:
            raise LoginError(ex)

        _validate_response(response)

        if(self._raw is True):
            print("--- raw beginning ---")
            print(response.text)
            print("--- raw ending    ---\n")

        responseObj = json.loads(response.text)
        self._vid = responseObj['uToken']
        if 'clientId' in responseObj:
            self._settings.clientId = responseObj['clientId']

    def _get_groups(self):
        """ Get information about groups """
        response = None

        try:
            response = requests.get(urls.get_groups(),headers=self._headers(), verify=self._verifySsl)

            if 2 != response.status_code // 100:
                raise ResponseError(response.status_code, response.text)

        except requests.exceptions.RequestException as ex:
            raise RequestError(ex)

        _validate_response(response)

        if(self._raw is True):
            print("--- _get_groups()")
            print("--- raw beginning ---")
            print(response.text)
            print("--- raw ending    ---\n")

        self._groups = json.loads(response.text)
        self._devices = None

    def get_devices(self, group=None):
        if self._vid is None:
            self.login()

        if self._devices is None:
            self._devices = []

            for group in self._groups['groupList']:
                if 'deviceList' in group:
                    list = group.get('deviceList', [])
                else:
                    list = group.get('deviceIdList', [])

                for index, device in enumerate(list):
                    if device:
                        id = None
                        if 'deviceHashGuid' in device:
                            id = device['deviceHashGuid']
                        else:
                            id = hashlib.md5(device['deviceGuid'].encode('utf-8')).hexdigest()

                        self._deviceIndexer[id] = device['deviceGuid']
                        self._devices.append({
                            'id': id,
                            'name': device['deviceName'] if 'deviceName' in device else f"Unnamed Device #{index}",
                            'group': group['groupName'],
                            'model': device['deviceModuleNumber'] if 'deviceModuleNumber' in device else ''
                        })

        return self._devices

    def dump(self, id):
        deviceGuid = self._deviceIndexer.get(id)

        if(deviceGuid):
            response = None

            try:
                response = requests.get(urls.status(deviceGuid), headers=self._headers(), verify=self._verifySsl)

                if 2 != response.status_code // 100:
                    raise ResponseError(response.status_code, response.text)

            except requests.exceptions.RequestException as ex:
                raise RequestError(ex)

            _validate_response(response)
            return json.loads(response.text)

        return None

    def history(self, id, mode, date, tz="+01:00"):
        deviceGuid = self._deviceIndexer.get(id)

        if(deviceGuid):
            response = None

            try:
                dataMode = constants.dataMode[mode].value
            except KeyError:
                raise Exception("Wrong mode parameter")

            payload = {
                "deviceGuid": deviceGuid,
                "dataMode": dataMode,
                "date": date,
                "osTimezone": tz
            }
            print(f'payload: {json.dumps(payload)}')

            try:
                response = requests.post(urls.history(), json=payload, headers=self._headers(), verify=self._verifySsl)

                if 2 != response.status_code // 100:
                    raise ResponseError(response.status_code, response.text)

            except requests.exceptions.RequestException as ex:
                raise RequestError(ex)

            _validate_response(response)

            if(self._raw is True):
                print("--- history()")
                print("--- raw beginning ---")
                print(response.text)
                print("--- raw ending    ---")

            _json = json.loads(response.text)
            return {
                'id': id,
                'parameters': self._read_parameters(_json)
            }

        return None

    def get_device(self, id):
        deviceGuid = self._deviceIndexer.get(id)

        if(deviceGuid):
            response = None

            try:
                response = requests.get(urls.status(deviceGuid), headers=self._headers(), verify=self._verifySsl)

                if 2 != response.status_code // 100:
                    raise ResponseError(response.status_code, response.text)

            except requests.exceptions.RequestException as ex:
                raise RequestError(ex)

            _validate_response(response)

            if(self._raw is True):
                print("--- get_device()")
                print("--- raw beginning ---")
                print(response.text)
                print("--- raw ending    ---")


            _json = json.loads(response.text)
            return {
                'id': id,
                'parameters': self._read_parameters(_json['parameters']),
                'features': self._read_features(_json)
            }

        return None

    def set_device(self, id, **kwargs):
        """ Set parameters of device

        Args:
            id  (str): Id of the device
            kwargs   : {temperature=float}, {mode=OperationMode}, {fanSpeed=FanSpeed}, {power=Power}, {airSwingHorizontal=}, {airSwingVertical=}, {eco=EcoMode}
        """

        parameters = {}
        airX = None
        airY = None

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
                    airX = value

                if key == 'airSwingVertical' and isinstance(value, constants.AirSwingUD):
                    airY = value
                
                if key == 'eco' and isinstance(value, constants.EcoMode):
                    parameters['ecoMode'] = value.value

                if key == 'ecoFunctionData':
                    parameters['ecoFunctionData'] = value

                if key == 'nanoe' and isinstance(value, constants.NanoeMode) and value != constants.NanoeMode.Unavailable:
                    parameters['nanoe'] = value.value


        # routine to set the auto mode of fan (either horizontal, vertical, both or disabled)
        if airX is not None or airY is not None:
            fanAuto = 0
            device = self.get_device(id)

            if device and device['parameters']['airSwingHorizontal'].value == -1:
                fanAuto = fanAuto | 1

            if device and device['parameters']['airSwingVertical'].value == -1:
                fanAuto = fanAuto | 2

            if airX is not None:
                if airX.value == -1:
                    fanAuto = fanAuto | 1
                else:
                    fanAuto = fanAuto & ~1
                    parameters['airSwingLR'] = airX.value

            if airY is not None:
                if airY.value == -1:
                    fanAuto = fanAuto | 2
                else:
                    fanAuto = fanAuto & ~2
                    print(airY.name)
                    parameters['airSwingUD'] = airY.value

            if fanAuto == 3:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.Both.value
            elif fanAuto == 1:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.AirSwingLR.value
            elif fanAuto == 2:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.AirSwingUD.value
            else:
                parameters['fanAutoMode'] = constants.AirSwingAutoMode.Disabled.value

        deviceGuid = self._deviceIndexer.get(id)
        if(deviceGuid):
            response = None

            payload = {
                "deviceGuid": deviceGuid,
                "parameters": parameters
            }

            if(self._raw is True):
                print("--- set_device()")
                print("--- raw out beginning ---")
                print(payload)
                print("--- raw out ending    ---")

            try:
                response = requests.post(urls.control(), json=payload, headers=self._headers(), verify=self._verifySsl)

                if 2 != response.status_code // 100:
                    raise ResponseError(response.status_code, response.text)

            except requests.exceptions.RequestException as ex:
                raise RequestError(ex)

            _validate_response(response)

            if(self._raw is True):
                print("--- raw in beginning ---")
                print(response.text)
                print("--- raw in ending    ---\n")

            _json = json.loads(response.text)

            return True

        return False

    def _read_parameters(self, parameters = {}):
        value = {}

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
            value['mode'] = constants.OperationMode(parameters['operationMode'])

        if 'fanSpeed' in parameters:
            value['fanSpeed'] = constants.FanSpeed(parameters['fanSpeed'])

        if 'airSwingLR' in parameters:
            value['airSwingHorizontal'] = constants.AirSwingLR(parameters['airSwingLR'])

        if 'airSwingUD' in parameters:
            value['airSwingVertical'] = constants.AirSwingUD(parameters['airSwingUD'])

        if 'ecoMode' in parameters:
            value['eco'] = constants.EcoMode(parameters['ecoMode'])

        if 'ecoFunctionData' in parameters:
            value['ecoFunctionData'] = constants.ecoFunctionData(parameters['ecoFunctionData'])

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

    def _read_features(self, data = {}):
        value = {
            'leftRightSwing': 'airSwingLR' in data and data['airSwingLR'],
            'nanoe': 'nanoe' in data and data['nanoe'],
            'autoMode': 'autoMode' in data and data['autoMode'],
            'upDownAllSwing': 'autoSwingUD' in data and data['autoSwingUD'],
            'ecoNavi': 'ecoNavi' in data and data['ecoNavi'],
            'iAutoX': 'iAutoX' in data and data['iAutoX'],
            'quietMode': 'quietMode' in data and data['quietMode'],
            'powerfulMode': 'powerfulMode' in data and data['powerfulMode'],
            'fanMode': 'fanMode' in data and data['fanMode'],
            'coolMode': 'coolMode' in data and data['coolMode'],
            'dryMode': 'dryMode' in data and data['dryMode'],
            'nanoeStandAlone': 'nanoeStandAlone' in data and data['nanoeStandAlone'],
            'heatMode': 'heatMode' in data and data['heatMode']
        }
        

        return value
