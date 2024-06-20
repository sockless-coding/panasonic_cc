import base64
import datetime
import hashlib
import json
import os
import random
import string
import time
import urllib
import aiohttp
import logging

import requests
from bs4 import BeautifulSoup

from . import exceptions
from .panasonicsettings import PanasonicSettings
from .ccappversion import CCAppVersion

_LOGGER = logging.getLogger(__name__)

def generate_random_string(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def generate_random_string_hex(length):
    return ''.join(random.choice(string.hexdigits) for _ in range(length))


def check_response(response: aiohttp.ClientResponse, function_description, expected_status):
    
    if response.status != expected_status:
        raise exceptions.ResponseError(
            f"({function_description}: Expected status code {expected_status}, received: {response.status}: " +
            f"{response.text}"
        )


def get_querystring_parameter_from_header_entry_url(response: aiohttp.ClientResponse, header_entry, querystring_parameter):
    header_entry_value = response.headers[header_entry]
    parsed_url = urllib.parse.urlparse(header_entry_value)
    params = urllib.parse.parse_qs(parsed_url.query)
    return params.get(querystring_parameter, [None])[0]


class PanasonicSession:
    APP_CLIENT_ID = "Xmy6xIYIitMxngjB2rHvlm6HSDNnaMJx"
    AUTH_0_CLIENT = "eyJuYW1lIjoiQXV0aDAuQW5kcm9pZCIsImVudiI6eyJhbmRyb2lkIjoiMzAifSwidmVyc2lvbiI6IjIuOS4zIn0="
    REDIRECT_URI = "panasonic-iot-cfc://authglb.digital.panasonic.com/android/com.panasonic.ACCsmart/callback"
    BASE_PATH_AUTH = "https://authglb.digital.panasonic.com"
    BASE_PATH_ACC = "https://accsmart.panasonic.com"
    X_APP_VERSION = "1.20.0"

    # token:
    # - access_token
    # - refresh_token
    # - id_token
    # - unix_timestamp_token_received
    # - expires_in_sec
    # - acc_client_id
    # - scope

    def __init__(self, username, password, client: aiohttp.ClientSession, settingsFileName='~/.panasonic-settings', raw=False):
        self._username = username
        self._password = password
        self._client = client
        self._settings = PanasonicSettings(os.path.expanduser(settingsFileName))
        self._appVersion = CCAppVersion(client, self._settings)
        self._raw = raw

    async def start_session(self):
        if (not self._settings.has_refresh_token):
            await self._get_new_token()
        if (not self._settings.is_access_token_valid):
            await self._refresh_token()


    async def _get_new_token(self):
        

        # generate initial state and code_challenge
        state = generate_random_string(20)
        code_verifier = generate_random_string(43)

        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(
                code_verifier.encode('utf-8')
            ).digest()).split('='.encode('utf-8'))[0].decode('utf-8')

        # --------------------------------------------------------------------
        # AUTHORIZE
        # --------------------------------------------------------------------

        response = await self._client.get(
            f'{PanasonicSession.BASE_PATH_AUTH}/authorize',
            headers={
                "user-agent": "okhttp/4.10.0",
            },
            params={
                "scope": "openid offline_access comfortcloud.control a2w.control",
                "audience": f"https://digital.panasonic.com/{PanasonicSession.APP_CLIENT_ID}/api/v1/",
                "protocol": "oauth2",
                "response_type": "code",
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "auth0Client": PanasonicSession.AUTH_0_CLIENT,
                "client_id": PanasonicSession.APP_CLIENT_ID,
                "redirect_uri": PanasonicSession.REDIRECT_URI,
                "state": state,
            },
            allow_redirects=False)
        check_response(response, 'authorize', 302)

        # -------------------------------------------------------------------
        # FOLLOW REDIRECT
        # -------------------------------------------------------------------

        location = response.headers['Location']
        state = get_querystring_parameter_from_header_entry_url(
            response, 'Location', 'state')

        response = await self._client.get(
            f"{PanasonicSession.BASE_PATH_AUTH}/{location}",
            allow_redirects=False)
        check_response(response, 'authorize_redirect', 200)

        # get the "_csrf" cookie
        csrf = response.cookies['_csrf']

        # -------------------------------------------------------------------
        # LOGIN
        # -------------------------------------------------------------------

        response = await self._client.post(
            f'{PanasonicSession.BASE_PATH_AUTH}/usernamepassword/login',
            headers={
                "Auth0-Client": PanasonicSession.AUTH_0_CLIENT,
                "user-agent": "okhttp/4.10.0",
            },
            json={
                "client_id": PanasonicSession.APP_CLIENT_ID,
                "redirect_uri": PanasonicSession.REDIRECT_URI,
                "tenant": "pdpauthglb-a1",
                "response_type": "code",
                "scope": "openid offline_access comfortcloud.control a2w.control",
                "audience": f"https://digital.panasonic.com/{PanasonicSession.APP_CLIENT_ID}/api/v1/",
                "_csrf": csrf,
                "state": state,
                "_intstate": "deprecated",
                "username": self._username,
                "password": self._password,
                "lang": "en",
                "connection": "PanasonicID-Authentication"
            },
            allow_redirects=False)
        check_response(response, 'login', 200)

        # -------------------------------------------------------------------
        # CALLBACK
        # -------------------------------------------------------------------

        # get wa, wresult, wctx from body
        soup = BeautifulSoup(await response.text(), "html.parser")
        input_lines = soup.find_all("input", {"type": "hidden"})
        parameters = dict()
        for input_line in input_lines:
            parameters[input_line.get("name")] = input_line.get("value")

        user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
        user_agent += "(KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36"

        response = await self._client.post(
            url=f"{PanasonicSession.BASE_PATH_AUTH}/login/callback",
            data=parameters,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": user_agent,
            },
            allow_redirects=False)
        check_response(response, 'login_callback', 302)

        # ------------------------------------------------------------------
        # FOLLOW REDIRECT
        # ------------------------------------------------------------------

        location = response.headers['Location']

        response = await self._client.get(
            f"{PanasonicSession.BASE_PATH_AUTH}/{location}",
            allow_redirects=False)
        check_response(response, 'login_redirect', 302)

        # ------------------------------------------------------------------
        # GET TOKEN
        # ------------------------------------------------------------------

        code = get_querystring_parameter_from_header_entry_url(
            response, 'Location', 'code')

        # do before, so that timestamp is older rather than newer
        now = datetime.datetime.now()
        unix_time_token_received = time.mktime(now.timetuple())

        response = await self._client.post(
            f'{PanasonicSession.BASE_PATH_AUTH}/oauth/token',
            headers={
                "Auth0-Client": PanasonicSession.AUTH_0_CLIENT,
                "user-agent": "okhttp/4.10.0",
            },
            json={
                "scope": "openid",
                "client_id": PanasonicSession.APP_CLIENT_ID,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": PanasonicSession.REDIRECT_URI,
                "code_verifier": code_verifier
            },
            allow_redirects=False)
        check_response(response, 'get_token', 200)

        token_response = json.loads(await response.text())

        # ------------------------------------------------------------------
        # RETRIEVE ACC_CLIENT_ID
        # ------------------------------------------------------------------
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        response = await self._client.post(
            f'{PanasonicSession.BASE_PATH_ACC}/auth/v2/login',
            headers={
                "Content-Type": "application/json;charset=utf-8",
                "User-Agent": "G-RAC",
                "X-APP-NAME": "Comfort Cloud",
                "X-APP-TIMESTAMP": timestamp,
                "X-APP-TYPE": "1",
                "X-APP-VERSION": PanasonicSession.X_APP_VERSION,
                "X-CFC-API-KEY": generate_random_string_hex(128),
                "X-User-Authorization-V2": "Bearer " + token_response["access_token"]
            },
            json={
                "language": 0
            })
        check_response(response, 'get_acc_client_id', 200)

        json_body = json.loads(await response.text())
        acc_client_id = json_body["clientId"]

        self._settings.clientId = acc_client_id
        self._settings.set_token(
            token_response["access_token"], 
            token_response["refresh_token"],
            unix_time_token_received + token_response["expires_in"],
            token_response["scope"])



    async def stop_session(self):
        response = await self._client.post(
            f"{PanasonicSession.BASE_PATH_ACC}/auth/v2/logout",
            headers=await self._get_header_for_api_calls()
        )
        check_response(response, "logout", 200)
        if json.loads(await response.text())["result"] != 0:
            # issue during logout, but do we really care?
            pass
        try:            
            self._settings.clear()
        except FileNotFoundError:
            pass

    async def _refresh_token(self):
        # do before, so that timestamp is older rather than newer
        now = datetime.datetime.now()
        unix_time_token_received = time.mktime(now.timetuple())

        response = await self._client.post(
            f'{PanasonicSession.BASE_PATH_AUTH}/oauth/token',
            headers={
                "Auth0-Client": PanasonicSession.AUTH_0_CLIENT,
                "user-agent": "okhttp/4.10.0",
            },
            json={
                "scope": self._settings.scope,
                "client_id": PanasonicSession.APP_CLIENT_ID,
                "refresh_token": self._settings.refresh_token,
                "grant_type": "refresh_token"
            },
            allow_redirects=False)
        check_response(response, 'refresh_token', 200)
        token_response = json.loads(await response.text())

        self._settings.set_token(
            token_response["access_token"], 
            token_response["refresh_token"],
            unix_time_token_received + token_response["expires_in"],
            token_response["scope"])




    async def _get_header_for_api_calls(self):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        _LOGGER.debug(f"Header ClientId: {self._settings.clientId}")
        _LOGGER.debug(f"Header Token: {self._settings.access_token}")
        return {
            "Content-Type": "application/json;charset=utf-8",
            "X-APP-NAME": "Comfort Cloud",
            "User-Agent": "G-RAC",
            "X-APP-TIMESTAMP": timestamp,
            "X-APP-TYPE": "1",
            "X-APP-VERSION": await self._appVersion.get(),
            # Seems to work by either setting X-CFC-API-KEY to 0 or to a 128-long hex string
            # "X-CFC-API-KEY": "0",
            "X-CFC-API-KEY": generate_random_string_hex(128),
            "X-Client-Id": self._settings.clientId,
            "X-User-Authorization-V2": "Bearer " + self._settings.access_token
        }

    async def _get_user_info(self):
        response = await self._client.get(
            f'{PanasonicSession.BASE_PATH_AUTH}/userinfo',
            headers={
                "Auth0-Client": self.AUTH_0_CLIENT,
                "Authorization": "Bearer " + self._settings.access_token
            })
        check_response(response, 'userinfo', 200)

    async def execute_post(self, url, json_data, function_description, expected_status_code):
        await self._ensure_valid_token()

        try:
            response = await self._client.post(
                url,
                json=json_data,
                headers= await self._get_header_for_api_calls()
            )
        except requests.exceptions.RequestException as ex:
            raise exceptions.RequestError(ex)

        self._print_response_if_raw_is_set(response, function_description)
        check_response(response, function_description, expected_status_code)
        return json.loads(await response.text())

    async def execute_get(self, url, function_description, expected_status_code):
        await self._ensure_valid_token()

        try:
            response = await self._client.get(
                url,
                headers=await self._get_header_for_api_calls()
            )
        except requests.exceptions.RequestException as ex:
            raise exceptions.RequestError(ex)

        self._print_response_if_raw_is_set(response, function_description)
        check_response(response, function_description, expected_status_code)
        return json.loads(await response.text())

    def _print_response_if_raw_is_set(self, response, function_description):
        if self._raw:
            print("=" * 79)
            print(f"Response: {function_description}")
            print("=" * 79)
            print(f"Status: {response.status_code}")
            print("-" * 79)
            print("Headers:")
            for header in response.headers:
                print(f'{header}: {response.headers[header]}')
            print("-" * 79)
            print("Response body:")
            print(response.text)
            print("-" * 79)

    async def _ensure_valid_token(self):
        if self._settings.is_access_token_valid:
            return
        await self._refresh_token()
