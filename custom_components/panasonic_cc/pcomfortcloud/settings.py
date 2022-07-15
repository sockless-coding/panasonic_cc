import json
import os
from datetime import date
from packaging import version

from .constants import (
    SETTING_TOKEN,
    SETTING_VERSION,
    SETTING_VERSION_DATE,
    SETTING_CLIENT_ID,

    DEFAULT_X_APP_VERSION,
    MAX_VERSION_AGE
)

class PanasonicSettings:

    def __init__(self, fileName):
        self._fileName = fileName
        self._token = None
        self._version = None
        self._versionDate = None
        self._clientId = ""
        self._load()

    def _load(self):
        if not os.path.exists(self._fileName):
            return
        try:
            with open(self._fileName) as json_file:
                data = json.load(json_file)
                self._token = data[SETTING_TOKEN]
                self._version = data[SETTING_VERSION]
                self._clientId = data[SETTING_CLIENT_ID]
                self._versionDate = date.fromisoformat(data[SETTING_VERSION_DATE])
        except:
            pass

    def _save(self):
        data = {}
        data[SETTING_TOKEN] = self._token
        data[SETTING_VERSION] = self._version
        data[SETTING_CLIENT_ID] = self._clientId
        data[SETTING_VERSION_DATE] = self._versionDate.isoformat()
        with open(self._fileName, 'w') as outfile:
            json.dump(data, outfile)

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, value):
        if self._token == value:
            return
        self._token = value
        self._save()

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
    def version_expired(self):
        if self._version is None:
            return True
        if self._versionDate is None:
            return True
        delta = date.today() - self._versionDate
        if (delta.days < MAX_VERSION_AGE):
            return False
        return True

    @property
    def clientId(self):
        return self._clientId

    @clientId.setter
    def clientId(self, value):
        if self._clientId == value:
            return
        self._clientId = value
        self._save()