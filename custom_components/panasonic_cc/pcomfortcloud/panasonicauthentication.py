import aiohttp
import base64
import hashlib
import logging
import random
import string
import urllib
import datetime
import time
import json

from bs4 import BeautifulSoup

from .panasonicsettings import PanasonicSettings
from .ccappversion import CCAppVersion
from .panasonicrequestheader import PanasonicRequestHeader
from . import exceptions
from .constants import (APP_CLIENT_ID, AUTH_0_CLIENT, BASE_PATH_ACC, BASE_PATH_AUTH, REDIRECT_URI, AUTH_API_USER_AGENT, AUTH_BROWSER_USER_AGENT)

_LOGGER = logging.getLogger(__name__)

def generate_random_string(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

async def check_response(response: aiohttp.ClientResponse, function_description, expected_status):
    
    if response.status != expected_status:
        response_text = await response.text()
        _LOGGER.error("%s: Expected status code %s, received: %s: %s", function_description, expected_status, response.status, response_text)
        raise exceptions.ResponseError(
            f"({function_description}: Expected status code {expected_status}, received: {response.status}: " +
            f"{response_text}"
        )
    
def get_querystring_parameter_from_header_entry_url(response: aiohttp.ClientResponse, header_entry, querystring_parameter):
    header_entry_value = response.headers[header_entry]
    parsed_url = urllib.parse.urlparse(header_entry_value)
    params = urllib.parse.parse_qs(parsed_url.query)
    return params.get(querystring_parameter, [None])[0]

class PanasonicAuthentication:

    def __init__(self, client: aiohttp.ClientSession, settings: PanasonicSettings, app_version:CCAppVersion):
        self._client = client
        self._settings = settings
        self._app_version = app_version

    async def authenticate(self, username: str, password: str):

        # generate initial state and code_challenge
        code_verifier = generate_random_string(43)

        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(
                code_verifier.encode('utf-8')
            ).digest()).split('='.encode('utf-8'))[0].decode('utf-8')
        
        authorization_response = await self._authorize(code_challenge)
        authorization_redirect = authorization_response.headers['Location']
        # check if the user can skip the authentication workflows - in that case, 
        # the location is directly pointing to the redirect url with the "code"
        # query parameter included
        if authorization_redirect.startswith(REDIRECT_URI):
            code = get_querystring_parameter_from_header_entry_url(
                authorization_response, 'Location', 'code')
        else:
            code = await self._login(authorization_response, username, password)
        
        await self._request_new_token(code, code_verifier)
        await self._retrieve_client_acc()
        
    async def refresh_token(self):
        _LOGGER.debug("Refreshing token")
        # do before, so that timestamp is older rather than newer        
        now = datetime.datetime.now()
        unix_time_token_received = time.mktime(now.timetuple())

        response = await self._client.post(
            f'{BASE_PATH_AUTH}/oauth/token',
            headers={
                "Auth0-Client": AUTH_0_CLIENT,
                "user-agent": AUTH_API_USER_AGENT,
            },
            json={
                "scope": self._settings.scope,
                "client_id": APP_CLIENT_ID,
                "refresh_token": self._settings.refresh_token,
                "grant_type": "refresh_token"
            },
            allow_redirects=False)
        await check_response(response, 'refresh_token', 200)
        token_response = json.loads(await response.text())
        self._set_token(token_response, unix_time_token_received)


    async def _authorize(self, challenge) -> aiohttp.ClientResponse:
        # --------------------------------------------------------------------
        # AUTHORIZE
        # --------------------------------------------------------------------
        state = generate_random_string(20)

        response = await self._client.get(
            f'{BASE_PATH_AUTH}/authorize',
            headers={
                "user-agent": AUTH_API_USER_AGENT,
            },
            params={
                "scope": "openid offline_access comfortcloud.control a2w.control",
                "audience": f"https://digital.panasonic.com/{APP_CLIENT_ID}/api/v1/",
                "protocol": "oauth2",
                "response_type": "code",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "auth0Client": AUTH_0_CLIENT,
                "client_id": APP_CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "state": state,
            },
            allow_redirects=False)
        await check_response(response, 'authorize', 302)
        return response
        
        
    async def _login(self, authorization_response: aiohttp.ClientResponse, username, password):
        _LOGGER.debug("Trying to log in")
        state = get_querystring_parameter_from_header_entry_url(
                authorization_response, 'Location', 'state')
        location = authorization_response.headers['Location']
        response = await self._client.get(
                f"{BASE_PATH_AUTH}/{location}",
                allow_redirects=False)
        await check_response(response, 'authorize_redirect', 200)

        # get the "_csrf" cookie
        csrf = response.cookies['_csrf']

        # -------------------------------------------------------------------
        # LOGIN
        # -------------------------------------------------------------------

        response = await self._client.post(
            f'{BASE_PATH_AUTH}/usernamepassword/login',
            headers={
                "Auth0-Client": AUTH_0_CLIENT,
                "user-agent": AUTH_API_USER_AGENT,
            },
            json={
                "client_id": APP_CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "tenant": "pdpauthglb-a1",
                "response_type": "code",
                "scope": "openid offline_access comfortcloud.control a2w.control",
                "audience": f"https://digital.panasonic.com/{APP_CLIENT_ID}/api/v1/",
                "_csrf": csrf,
                "state": state,
                "_intstate": "deprecated",
                "username": username,
                "password": password,
                "lang": "en",
                "connection": "PanasonicID-Authentication"
            },
            allow_redirects=False)
        await check_response(response, 'login', 200)

        # -------------------------------------------------------------------
        # CALLBACK
        # -------------------------------------------------------------------

        # get wa, wresult, wctx from body
        soup = BeautifulSoup(await response.text(), "html.parser")
        input_lines = soup.find_all("input", {"type": "hidden"})
        parameters = dict()
        for input_line in input_lines:
            parameters[input_line.get("name")] = input_line.get("value")


        response = await self._client.post(
            url=f"{BASE_PATH_AUTH}/login/callback",
            data=parameters,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": AUTH_BROWSER_USER_AGENT,
            },
            allow_redirects=False)
        await check_response(response, 'login_callback', 302)

        # ------------------------------------------------------------------
        # FOLLOW REDIRECT
        # ------------------------------------------------------------------

        location = response.headers['Location']

        response = await self._client.get(
            f"{BASE_PATH_AUTH}/{location}",
            allow_redirects=False)
        await check_response(response, 'login_redirect', 302)

        return get_querystring_parameter_from_header_entry_url(
                response, 'Location', 'code')
    
    async def _request_new_token(self, code, code_verifier):
        _LOGGER.debug("Requesting a new token")
        # do before, so that timestamp is older rather than newer
        now = datetime.datetime.now()
        unix_time_token_received = time.mktime(now.timetuple())

        response = await self._client.post(
            f'{BASE_PATH_AUTH}/oauth/token',
            headers={
                "Auth0-Client": AUTH_0_CLIENT,
                "user-agent": AUTH_API_USER_AGENT,
            },
            json={
                "scope": "openid",
                "client_id": APP_CLIENT_ID,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier
            },
            allow_redirects=False)
        await check_response(response, 'get_token', 200)

        token_response = json.loads(await response.text())
        self._set_token(token_response, unix_time_token_received)
        
    def _set_token(self, token_response, unix_time_token_received):
        self._settings.set_token(
            token_response["access_token"], 
            token_response["refresh_token"],
            unix_time_token_received + token_response["expires_in"],
            token_response["scope"])
        
    async def _retrieve_client_acc(self):
        # ------------------------------------------------------------------
        # RETRIEVE ACC_CLIENT_ID
        # ------------------------------------------------------------------
        response = await self._client.post(
            f'{BASE_PATH_ACC}/auth/v2/login',
            headers = await PanasonicRequestHeader.get(self._settings, self._app_version),
            json={
                "language": 0
            })
        await check_response(response, 'get_acc_client_id', 200)

        json_body = json.loads(await response.text())
        self._settings.clientId = json_body["clientId"]

