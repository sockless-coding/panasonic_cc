import json
import os
import aiohttp
import logging
import asyncio

import aiohttp.client_exceptions
import aiohttp.http_exceptions
import aiohttp.web_exceptions

from . import exceptions
from .panasonicsettings import PanasonicSettings
from .ccappversion import CCAppVersion
from .panasonicauthentication import PanasonicAuthentication
from .panasonicrequestheader import PanasonicRequestHeader
from .constants import BASE_PATH_ACC
from .exceptions import LoginError
from .helpers import has_new_version_been_published, check_response


_LOGGER = logging.getLogger(__name__)




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
        self._request_semaphore = asyncio.Semaphore(1)
        self._aqua_cookies = aiohttp.CookieJar()

    async def start_session(self):
        _LOGGER.debug("Starting Session")
        await self._settings.is_ready()
        if (not self._settings.has_refresh_token):
            _LOGGER.debug("No refresh token found")
            await self._authentication.authenticate(self._username, self._password)
        if (not self._settings.is_access_token_valid):
            _LOGGER.debug("Access token is not valid")
            try:
                await self._authentication.refresh_token()
            except Exception as ex:
                _LOGGER.debug("Failed to refresh token, trying to reauthenticate", exc_info= ex)
                await self._authentication.authenticate(self._username, self._password)
        if (not self._settings.is_access_token_valid):
            _LOGGER.critical("Unable to create a valid access token")
            raise LoginError()
        _LOGGER.debug("Access token is valid")


    async def reauthenticate(self):
        _LOGGER.debug("Reauthenticating")
        await self._authentication.authenticate(self._username, self._password)

    async def stop_session(self):
        _LOGGER.debug("Stopping Session")
        response = await self._client.post(
            f"{BASE_PATH_ACC}/auth/v2/logout",
            headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
        )
        await check_response(response, "logout", 200)
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
        async with self._request_semaphore:
            await self._ensure_valid_token()

            try:
                response = await self._client.post(
                    url,
                    json = json_data,
                    headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
                )
                if await has_new_version_been_published(response):
                    _LOGGER.info("New version of acc client id has been published")
                    await self._app_version.refresh()
                    response = await self._client.post(
                        url,
                        json = json_data,
                        headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
                    )
            except (aiohttp.client_exceptions.ClientError,
                    aiohttp.http_exceptions.HttpProcessingError,
                    aiohttp.web_exceptions.HTTPError) as ex:
                _LOGGER.error("POST url: %s, data: %s", url, json_data)
                raise exceptions.RequestError(ex)

            
            self._print_response_if_raw_is_set(response, function_description)
            await check_response(response, function_description, expected_status_code, payload=json_data)
            response_text = await response.text()
            _LOGGER.debug("POST url: %s, data: %s, response: %s", url, json_data, response_text)
            return json.loads(response_text)

    async def execute_get(self, url, function_description, expected_status_code):
        async with self._request_semaphore:
            await self._ensure_valid_token()

            try:
                response = await self._client.get(
                    url,
                    headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
                )
                if await has_new_version_been_published(response):
                    _LOGGER.info("New version of acc client id has been published")
                    await self._app_version.refresh()
                    response = await self._client.get(
                        url,
                        headers = await PanasonicRequestHeader.get(self._settings, self._app_version)
                    )
            except (aiohttp.client_exceptions.ClientError,
                    aiohttp.http_exceptions.HttpProcessingError,
                    aiohttp.web_exceptions.HTTPError) as ex:
                raise exceptions.RequestError(ex)

            self._print_response_if_raw_is_set(response, function_description)
            await check_response(response, function_description, expected_status_code)
            response_text = await response.text()
            _LOGGER.debug("GET url: %s, response: %s", url, response_text)
            return json.loads(response_text)
        
    async def execute_aqua_get(
            self, 
            url, 
            function_description, 
            expected_status_code,
            content_type: str = "application/x-www-form-urlencoded",
            cookies: dict = {}):
        async with self._request_semaphore:
            await self._ensure_valid_token()
            old_cookie_jar = self._client.cookie_jar
            try:
                self._client._cookie_jar = self._aqua_cookies  
                cookies["accessToken"] = self._settings.access_token
                response = await self._client.get(
                    url,
                    headers = PanasonicRequestHeader.get_aqua_headers(content_type=content_type),
                    cookies=cookies
                )
            except (aiohttp.client_exceptions.ClientError,
                    aiohttp.http_exceptions.HttpProcessingError,
                    aiohttp.web_exceptions.HTTPError) as ex:
                raise exceptions.RequestError(ex)
            finally:
                self._client._cookie_jar = old_cookie_jar

            self._print_response_if_raw_is_set(response, function_description)
            await check_response(response, function_description, expected_status_code)
            return response
    
    async def execute_aqua_post(
            self, 
            url, 
            function_description, 
            expected_status_code,
            content_type: str = "application/x-www-form-urlencoded",
            cookies: dict = {}):
        async with self._request_semaphore:
            await self._ensure_valid_token()
            old_cookie_jar = self._client.cookie_jar
            try:
                self._client._cookie_jar = self._aqua_cookies
                _LOGGER.debug(f"Aqua access token: {self._settings.access_token}")
                cookies["accessToken"] = self._settings.access_token
                
                response = await self._client.post(
                    url,
                    headers = PanasonicRequestHeader.get_aqua_headers(content_type=content_type),
                    cookies=cookies
                )
                
            except (aiohttp.client_exceptions.ClientError,
                    aiohttp.http_exceptions.HttpProcessingError,
                    aiohttp.web_exceptions.HTTPError) as ex:
                raise exceptions.RequestError(ex)
            finally:
                self._client._cookie_jar = old_cookie_jar

            self._print_response_if_raw_is_set(response, function_description)
            await check_response(response, function_description, expected_status_code)
            return response

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
