import datetime
import random
import string
import hashlib
import logging

from .panasonicsettings import PanasonicSettings
from .ccappversion import CCAppVersion
from .constants import AUTH_BROWSER_USER_AGENT

_LOGGER = logging.getLogger(__name__)

class PanasonicRequestHeader:

    @staticmethod
    async def get(settings: PanasonicSettings, app_version: CCAppVersion, include_client_id = True):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")    
        api_key = PanasonicRequestHeader._get_api_key(timestamp, settings.access_token)  
        _LOGGER.debug(f"Request Timestamp: {timestamp} key: {api_key}")
        headers={
                "content-type": "application/json;charset=utf-8",
                "user-agent": "G-RAC",
                "x-app-name": "Comfort Cloud",
                "x-app-timestamp": timestamp,
                "x-app-type": "1",
                "x-app-version": await app_version.get(),
                "x-cfc-api-key": api_key,
                "x-user-authorization-v2": "Bearer " + settings.access_token
            }
        if (include_client_id and settings.clientId):
            headers["x-client-id"] = settings.clientId
        return headers
    
    @staticmethod
    def get_aqua_headers(content_type: str = "application/x-www-form-urlencoded", referer:str = "https://aquarea-smart.panasonic.com/"):
        headers={
                "Cache-Control": "max-age=0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "deflate, br",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": AUTH_BROWSER_USER_AGENT,
                "content-type": content_type,
                "referer": referer
            }
        return headers
        
    @staticmethod
    def _get_api_key(timestamp, token):
        try:
            date = datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            timestamp_ms = str(int(date.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000))
            
            components = [
                'Comfort Cloud'.encode('utf-8'),
                '521325fb2dd486bf4831b47644317fca'.encode('utf-8'),
                timestamp_ms.encode('utf-8'),
                'Bearer '.encode('utf-8'),
                token.encode('utf-8')
            ]
                
            input_buffer = b''.join(components)
            hash_obj = hashlib.sha256()
            hash_obj.update(input_buffer)
            hash_str = hash_obj.hexdigest()
            
            result = hash_str[:9] + 'cfc' + hash_str[9:]
            return result
        except Exception as ex:
            _LOGGER.error("Failed to generate API key")