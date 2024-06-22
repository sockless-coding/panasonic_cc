import json
import os
import datetime
import time
import base64
import aiofiles
import asyncio
import logging
from datetime import date
from packaging import version

from .constants import (
    SETTING_VERSION,
    SETTING_VERSION_DATE,
    SETTING_ACCESS_TOKEN,
    SETTING_ACCESS_TOKEN_EXPIRES,
    SETTING_REFRESH_TOKEN,
    SETTING_SCOPE,
    SETTING_CLIENT_ID,

    DEFAULT_X_APP_VERSION,
    MAX_VERSION_AGE
)

_LOGGER = logging.getLogger(__name__)

class PanasonicSettings:

    def __init__(self, fileName):
        self._fileName = fileName
        self._version = None
        self._versionDate = None
        self._access_token = None
        self._access_token_expires = None
        self._refresh_token = None
        self._scope = None
        self._clientId = ""
        asyncio.ensure_future(self._load())
        

    async def _load(self):
        if not os.path.exists(self._fileName):
            _LOGGER.info("Settings file '%s' was not found", self._fileName)
            return
        try:
            async with aiofiles.open(self._fileName) as json_file:
                data = json.loads(await json_file.read())
                self._version = data[SETTING_VERSION]
                self._versionDate = date.fromisoformat(data[SETTING_VERSION_DATE])
                self._access_token = data[SETTING_ACCESS_TOKEN]
                self._access_token_expires = data[SETTING_ACCESS_TOKEN_EXPIRES]
                self._refresh_token = data[SETTING_REFRESH_TOKEN]
                self._clientId = data[SETTING_CLIENT_ID]
                self._scope = data[SETTING_SCOPE]
                _LOGGER.debug("Loaded settings from '%s'", self._fileName)
        except Exception as ex:
            _LOGGER.warning("Failed to loaded settings from '%s'", self._fileName, exc_info = ex)
            pass
    
    def _save(self):
        data = {}
        data[SETTING_VERSION] = self._version
        if self._versionDate:
            data[SETTING_VERSION_DATE] = self._versionDate.isoformat()
        data[SETTING_ACCESS_TOKEN] = self._access_token
        data[SETTING_ACCESS_TOKEN_EXPIRES] = self._access_token_expires
        data[SETTING_REFRESH_TOKEN] = self._refresh_token
        data[SETTING_CLIENT_ID] = self._clientId
        data[SETTING_SCOPE] = self._scope
        asyncio.ensure_future(self._do_save(data))
        

    async def _do_save(self, data):
        async with aiofiles.open(self._fileName, 'w') as outfile:
            await outfile.write(json.dumps(data))
            _LOGGER.debug("Saved settings to '%s'", self._fileName)

    @property
    def version(self):
        if self._version is None:
            return DEFAULT_X_APP_VERSION
        return self._version

    @version.setter
    def version(self,value):
        if value is None:
            return
        if (self._version is None
            or version.parse(self._version) < version.parse(value)):
            self._version = value
        self._versionDate = date.today()
        self._save()

    @property
    def is_version_expired(self):
        if self._version is None:
            return True
        if not self._version:
            return True
        if self._versionDate is None:
            return True
        delta = date.today() - self._versionDate
        if (delta.days < MAX_VERSION_AGE):
            return False
        return True
    
    @property
    def is_access_token_valid(self) -> bool:
        if not self._access_token:
            return False
        now = datetime.datetime.now()
        current_time = time.mktime(now.timetuple())
        part_of_token_b64 = str(self._access_token.split(".")[1])
        # as seen here: https://stackoverflow.com/questions/3302946/how-to-decode-base64-url-in-python
        part_of_token = base64.urlsafe_b64decode(part_of_token_b64 + '=' * (4 - len(part_of_token_b64) % 4))
        token_info_json = json.loads(part_of_token)
        expiry_in_token = token_info_json["exp"]

        
        return current_time < expiry_in_token or current_time < self._access_token_expires
    
    @property
    def has_refresh_token(self) -> bool:
        if self._refresh_token:
            return True
        return False
    
    @property
    def access_token(self):
        return self._access_token
    
    @property
    def refresh_token(self):
        return self._refresh_token
    
    @property
    def scope(self):
        return self._scope
    
    def set_token(self, access_token = None, refresh_token = None, access_token_expires = None, scope = None):
        if access_token:
            self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token
        if access_token_expires:
            self._access_token_expires = access_token_expires
        if scope:
            self._scope = scope
        self._save()

    @property
    def clientId(self):
        return self._clientId

    @clientId.setter
    def clientId(self, value):
        if self._clientId == value:
            return
        self._clientId = value
        self._save()

    def clear(self):
        self._clientId = None
        self._access_token = None
        self._refresh_token = None
        self._access_token_expires = None
        self._save()
    