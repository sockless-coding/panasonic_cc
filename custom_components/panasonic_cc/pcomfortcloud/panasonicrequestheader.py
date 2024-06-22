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
                "Content-Type": "application/json;charset=utf-8",
                "User-Agent": "G-RAC",
                "X-APP-NAME": "Comfort Cloud",
                "X-APP-TIMESTAMP": timestamp,
                "X-APP-TYPE": "1",
                "X-APP-VERSION": await app_version.get(),
                "X-CFC-API-KEY": PanasonicRequestHeader._get_api_key(),
                "X-User-Authorization-V2": "Bearer " + settings.access_token
            }
        if (include_client_id and settings.clientId):
            headers["X-Client-Id"] = settings.clientId
        return headers
        
    @staticmethod
    def _get_api_key():
        return ''.join(random.choice(string.hexdigits) for _ in range(128))