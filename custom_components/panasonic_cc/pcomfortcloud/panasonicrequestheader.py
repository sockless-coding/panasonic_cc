import datetime
import random
import string

from .panasonicsettings import PanasonicSettings
from .ccappversion import CCAppVersion

class PanasonicRequestHeader:

    @staticmethod
    async def get(settings: PanasonicSettings, app_version: CCAppVersion, include_client_id = True):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")        
        headers={
                "content-type": "application/json;charset=utf-8",
                "user-agent": "G-RAC",
                "x-app-name": "Comfort Cloud",
                "x-app-timestamp": timestamp,
                "x-app-type": "1",
                "x-app-version": await app_version.get(),
                "x-cfc-api-key": PanasonicRequestHeader._get_api_key(),
                "x-user-authorization-v2": "Bearer " + settings.access_token
            }
        if (include_client_id and settings.clientId):
            headers["x-client-id"] = settings.clientId
        return headers
        
    @staticmethod
    def _get_api_key():
        return ''.join(random.choice(string.hexdigits) for _ in range(128))
