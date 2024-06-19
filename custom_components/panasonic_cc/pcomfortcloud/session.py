'''
Panasonic session, using Panasonic Comfort Cloud app api
'''


from datetime import datetime
import json
import sys
import requests
import os
import urllib
import hashlib
import random
import string
import base64
from bs4 import BeautifulSoup

from . import urls
from . import constants


def _validate_response(response):
    """ Verify that response is OK """
    if response.status_code == 200:
        return
    raise ResponseError(response.status_code, response.text)


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


def load_token_from_file(token_file_name):
    with open(token_file_name, "r") as token_file:
        token = json.load(token_file)
        return token


def generate_random_string(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def generate_random_string_hex(length):
    return ''.join(random.choice(string.hexdigits) for _ in range(length))


auth_0_client = "eyJuYW1lIjoiQXV0aDAuQW5kcm9pZCIsImVudiI6eyJhbmRyb2lkIjoiMzAifSwidmVyc2lvbiI6IjIuOS4zIn0="
app_client_id = "Xmy6xIYIitMxngjB2rHvlm6HSDNnaMJx"
redirect = "panasonic-iot-cfc://authglb.digital.panasonic.com/android/com.panasonic.ACCsmart/callback"


def get_new_token(username, password):
    requests_session = requests.Session()

    # generate state and code_challenge
    state = generate_random_string(20)

    code_verifier = generate_random_string(43)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(
            code_verifier.encode('utf-8')
        ).digest()).split('='.encode('utf-8'))[0].decode('utf-8')

    print("AUTHORIZE")
    # ------------------------------------------------------------------------------------------------------------------
    headers = {
        "user-agent": "okhttp/4.10.0",
    }

    params = {
        "scope": "openid offline_access comfortcloud.control a2w.control",
        "audience": f"https://digital.panasonic.com/{app_client_id}/api/v1/",
        "protocol": "oauth2",
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "auth0Client": auth_0_client,
        "client_id": app_client_id,
        "redirect_uri": redirect,
        "state": state,
    }

    response = requests_session.get(
        'https://authglb.digital.panasonic.com/authorize',
        headers=headers,
        params=params,
        allow_redirects=False)

    # get the "state" querystring parameter from the redirect url
    location = response.headers['Location']
    parsed_url = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed_url.query)
    state_value = params.get('state', [None])[0]
    print('state: ' + state_value)

    print("FOLLOW REDIRECT")
    # ------------------------------------------------------------------------------------------------------------------
    headers = {
        "user-agent": "okhttp/4.10.0",
    }

    response = requests_session.get(
        f"https://authglb.digital.panasonic.com{location}",
        allow_redirects=False)

    # get the "_csrf" cookie
    csrf = response.cookies['_csrf']
    print('_csrf: ' + csrf)

    print("LOGIN")
    # ------------------------------------------------------------------------------------------------------------------
    headers = {
        "Auth0-Client": auth_0_client,
        "user-agent": "okhttp/4.10.0",
    }

    data = {
        "client_id": app_client_id,
        "redirect_uri": redirect,
        "tenant": "pdpauthglb-a1",
        "response_type": "code",
        "scope": "openid offline_access comfortcloud.control a2w.control",
        "audience": f"https://digital.panasonic.com/{app_client_id}/api/v1/",
        "_csrf": csrf,
        "state": state_value,
        "_intstate": "deprecated",
        "username": username,
        "password": password,
        "lang": "en",
        "connection": "PanasonicID-Authentication"
    }

    response = requests_session.post(
        'https://authglb.digital.panasonic.com/usernamepassword/login',
        headers=headers,
        json=data,
        allow_redirects=False)

    # get wa, wresult, wctx from body
    soup = BeautifulSoup(response.content, "html.parser")
    input_lines = soup.find_all("input", {"type": "hidden"})
    parameters = dict()
    for input_line in input_lines:
        parameters[input_line.get("name")] = input_line.get("value")

    auth_0_request_id = response.headers['X-Auth0-RequestId']
    print("Auth0-RequestId: " + auth_0_request_id)

    print("CALLBACK")
    # ------------------------------------------------------------------------------------------------------------------
    user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    user_agent += "(KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36"

    response = requests_session.post(
        url="https://authglb.digital.panasonic.com/login/callback",
        data=parameters,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": user_agent,
        },
        allow_redirects=False)

    print("FOLLOW REDIRECT")
    # ------------------------------------------------------------------------------------------------------------------
    headers = {
        "user-agent": "okhttp/4.10.0",
    }

    location = response.headers['Location']
    response = requests_session.get(
        f"https://authglb.digital.panasonic.com{location}",
        allow_redirects=False)

    location = response.headers['Location']
    parsed_url = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed_url.query)
    code = params.get('code', [None])[0]
    print('code: ' + code)

    print("GET TOKEN")
    # ------------------------------------------------------------------------------------------------------------------
    headers = {
        "Auth0-Client": auth_0_client,
        "user-agent": "okhttp/4.10.0",
    }

    data = {
        "scope": "openid",
        "client_id": app_client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect,
        "code_verifier": code_verifier
    }

    response = requests_session.post(
        'https://authglb.digital.panasonic.com/oauth/token',
        headers=headers,
        json=data,
        allow_redirects=False)
    token = json.loads(response.text)
    return token


def get_and_save_new_token(username, password, token_file_name):
    token = get_new_token(username, password)
    with open(token_file_name, 'w') as tokenFile:
        tokenFile.write(json.dumps(token, indent=4))
    return token


class Session(object):
    def __init__(self, username, password, tokenFileName='~/.panasonic-token', raw=False):
        self._username = username
        self._password = password
        self._tokenFileName = os.path.expanduser(tokenFileName)
        self._token = None
        self._groups = None
        self._devices = None
        self._deviceIndexer = {}
        self._raw = raw
        self._acc_client_id = None

        if os.path.exists(self._tokenFileName):
            self._token = load_token_from_file(self._tokenFileName)
            # try:
            #     self._get_groups()
            # except ResponseError:
            #     if self._raw:
            #         print("--- token probably expired")
            #     self._token = get_and_save_new_token(self._username, self._password, self._tokenFileName)
        else:
            self._token = get_and_save_new_token(self._username, self._password, self._tokenFileName)

    # def __enter__(self):
    #     self.login()
    #     return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def login(self):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        response = requests.post(
            'https://accsmart.panasonic.com/auth/v2/login',
            headers={
                "Content-Type": "application/json;charset=utf-8",
                "User-Agent": "G-RAC",
                "X-APP-NAME": "Comfort Cloud",
                "X-APP-TIMESTAMP": timestamp,
                "X-APP-TYPE": "1",
                "X-APP-VERSION": "1.20.0",
                "X-CFC-API-KEY": generate_random_string_hex(128),
                "X-User-Authorization-V2": "Bearer " + self._token["access_token"]
            },
            json={
                "language": 0
            })
        # print(response.status_code)
        # print(response.headers)
        # print(response.text)
        # print(response.content)

        json_body = json.loads(response.text)
        self._acc_client_id = json_body["clientId"]

        response = requests.get(
            'https://accsmart.panasonic.com/device/group',
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-APP-NAME": "Comfort Cloud",
                "User-Agent": "G-RAC",
                "X-APP-TIMESTAMP": timestamp,
                "X-APP-TYPE": "1",
                "X-APP-VERSION": "1.20.0",
                "X-CFC-API-KEY": "0",
                "X-Client-Id": self._acc_client_id,
                "X-User-Authorization-V2": "Bearer " + self._token["access_token"]
            },
            allow_redirects=False)
        print(response.status_code)
        # print(response.headers)
        print(response.text)
        # print(response.content)

        sys.exit(0)

    def logout(self):
        """ Logout """
        os.remove(self._tokenFileName)

    def _headers(self):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "Content-Type": "application/json; charset=utf-8",
            "X-APP-NAME": "Comfort Cloud",
            "User-Agent": "G-RAC",
            "X-APP-TIMESTAMP": timestamp,
            "X-APP-TYPE": "1",
            "X-APP-VERSION": "1.20.1",
            "X-CFC-API-KEY": "0",
            "X-Client-Id": self._acc_client_id,
            "X-User-Authorization-V2": "Bearer " + self._token["access_token"]
        }

    def _get_groups(self):
        """ Get information about groups """
        response = None

        try:
            response = requests.get(urls.get_groups(),headers=self._headers())

            if 2 != response.status_code // 100:
                raise ResponseError(response.status_code, response.text)

        except requests.exceptions.RequestException as ex:
            raise RequestError(ex)

        _validate_response(response)

        if self._raw:
            print("--- _get_groups()")
            print("--- raw beginning ---")
            print(response.text)
            print("--- raw ending    ---\n")

        self._groups = json.loads(response.text)
        self._devices = None

    def get_devices(self, group=None):
        if self._token is None:
            self.login()

        if self._devices is None:
            self._devices = []

            for group in self._groups['groupList']:
                if 'deviceList' in group:
                    list = group.get('deviceList', [])
                else:
                    list = group.get('deviceIdList', [])

                for device in list:
                    if device:
                        id = None
                        if 'deviceHashGuid' in device:
                            id = device['deviceHashGuid']
                        else:
                            id = hashlib.md5(device['deviceGuid'].encode('utf-8')).hexdigest()

                        self._deviceIndexer[id] = device['deviceGuid']
                        self._devices.append({
                            'id': id,
                            'name': device['deviceName'],
                            'group': group['groupName'],
                            'model': device['deviceModuleNumber'] if 'deviceModuleNumber' in device else ''
                        })

        return self._devices

    def dump(self, id):
        deviceGuid = self._deviceIndexer.get(id)

        if(deviceGuid):
            response = None

            try:
                response = requests.get(urls.status(deviceGuid), headers=self._headers())

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
                'parameters': self._read_parameters(_json['parameters'])
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
