import logging
import json
import aiohttp

from .panasonicsettings import PanasonicSettings

_LOGGER = logging.getLogger(__name__)

class CCAppVersion:
    def __init__(self, client: aiohttp.ClientSession, settings: PanasonicSettings) -> None:
        self._client = client
        self._settings = settings
        self._appVersion = settings._version
    
    async def get(self):
        if self._settings.is_version_expired:
            await self._update()
        return self._appVersion

    async def _update(self):        
        _LOGGER.debug("Fetching latest app version")
        try:            
            response = await self._client.get("https://api.github.com/gists/e886d56531dbcde08aa11c096ab0a219")
            responseText = await response.text()
            data = json.loads(responseText)
            version = data['files']['comfort-cloud-version']['content']
            if version is not None:
                _LOGGER.debug(f"Found app version: {version}")
                self._appVersion = version
                self._settings.version = version
                return
        except Exception as e:
            _LOGGER.warning(f"Getting app version: {e}")
            pass
        _LOGGER.debug(f"Failed to retrive app version using version {self._appVersion}")