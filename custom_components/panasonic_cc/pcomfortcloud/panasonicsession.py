import json
import os
import aiohttp
import logging

import aiohttp.client_exceptions
import aiohttp.http_exceptions
import aiohttp.web_exceptions

from . import exceptions
from .panasonicsettings import PanasonicSettings
from .ccappversion import CCAppVersion
from .panasonicauthentication import PanasonicAuthentication
from .panasonicrequestheader import PanasonicRequestHeader
from .constants import BASE_PATH_ACC

_LOGGER = logging.getLogger(__name__)



def check_response(response: aiohttp.ClientResponse, function_description, expected_status):
    
    if response.status != expected_status:
        raise exceptions.ResponseError(
            f"({function_description}: Expected status code {expected_status}, received: {response.status}: " +
            f"{response.text}"
        )


class PanasonicSession:
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
        self._app_version = CCAppVersion(client, self._settings)
        self._authentication = PanasonicAuthentication(client, self._settings, self._app_version)
        self._raw = raw

    async def start_session(self):
        _LOGGER.debug("Starting Session")
        await self._settings.is_ready()
        if (not self._settings.has_refresh_token):
            await self._authentication.authenticate(self._username, self._password)
        if (not self._settings.is_access_token_valid):
            try:
                await self._authentication.refresh_token()
            except:
                await self._authentication.authenticate(self._username, self._password)

    async def stop_session(self):
        _LOGGER.debug("Stopping Session")
        response = await self._client.post(
            f"{BASE_PATH_ACC}/auth/v2/logout",
            headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
        )
        check_response(response, "logout", 200)
        if json.loads(await response.text())["result"] != 0:
            # issue during logout, but do we really care?
            pass
        try:            
            self._settings.clear()
        except FileNotFoundError:
            pass
    
    @property
    def app_version(self):
        return self._settings.version

    async def update_app_version(self):
        await self._app_version.refresh()

    async def execute_post(self, url, json_data, function_description, expected_status_code):
        await self._ensure_valid_token()

        try:
            response = await self._client.post(
                url,
                json = json_data,
                headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
            )
        except (aiohttp.client_exceptions.ClientError,
                aiohttp.http_exceptions.HttpProcessingError,
                aiohttp.web_exceptions.HTTPError) as ex:            
            raise exceptions.RequestError(ex)

        
        self._print_response_if_raw_is_set(response, function_description)
        check_response(response, function_description, expected_status_code)
        response_text = await response.text()
        _LOGGER.debug("POST url: %s, data: %s, response: %s", url, json_data, response_text)
        return json.loads(response_text)

    async def execute_get(self, url, function_description, expected_status_code):
        await self._ensure_valid_token()

        try:
            response = await self._client.get(
                url,
                headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
            )
        except (aiohttp.client_exceptions.ClientError,
                aiohttp.http_exceptions.HttpProcessingError,
                aiohttp.web_exceptions.HTTPError) as ex:
            raise exceptions.RequestError(ex)

        self._print_response_if_raw_is_set(response, function_description)
        check_response(response, function_description, expected_status_code)
        response_text = await response.text()
        _LOGGER.debug("GET url: %s, response: %s", url, response_text)
        return json.loads(response_text)

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
        await self._authentication.refresh_token()
