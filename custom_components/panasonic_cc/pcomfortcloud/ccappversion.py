import logging
import json
import aiohttp
import re

from bs4 import BeautifulSoup
from .panasonicsettings import PanasonicSettings

_LOGGER = logging.getLogger(__name__)

class CCAppVersion:
    def __init__(self, client: aiohttp.ClientSession, settings: PanasonicSettings) -> None:
        self._client = client
        self._settings = settings
    
    async def get(self):
        if self._settings.is_version_expired:
            await self.refresh()
        return self._settings._version
    
    async def refresh(self):
        await self._update_playstore()

    async def _update_gist(self):        
        _LOGGER.debug("Fetching latest app version from gist")
        try:            
            response = await self._client.get("https://api.github.com/gists/e886d56531dbcde08aa11c096ab0a219")
            responseText = await response.text()
            data = json.loads(responseText)
            version = data['files']['comfort-cloud-version']['content']
            if version is not None:
                _LOGGER.debug(f"Found app version: {version}")
                self._settings.version = version
                return
        except Exception as e:
            _LOGGER.warning(f"Getting app version: {e}")
            pass
        _LOGGER.debug(f"Failed to retrive app version using version {self._settings.version}")

    async def _update_appbrain(self):        
        _LOGGER.debug("Fetching latest app version from app brain")
        try:            
            response = await self._client.get("https://www.appbrain.com/app/panasonic-comfort-cloud/com.panasonic.ACCsmart")
            responseText = await response.text()
            soup = BeautifulSoup(responseText, "html.parser")
            meta_tag = soup.find("meta", itemprop="softwareVersion")
            if meta_tag:
                version = meta_tag['content']
                _LOGGER.debug(f"Found app version: {version}")
                self._settings.version = version
                return
        except Exception as e:
            _LOGGER.warning(f"Getting app version: {e}")
            pass
        _LOGGER.debug(f"Failed to retrive app version using version {self._settings.version}")

    async def _update_playstore(self):
        _LOGGER.debug("Fetching latest app version from play store")
        try:            
            response = await self._client.get("https://play.google.com/store/apps/details?id=com.panasonic.ACCsmart")
            responseText = await response.text()
            version_match = re.search(r'\["(\d+\.\d+\.\d+)"\]', responseText)
            if version_match:
                version = version_match.group(1)
                _LOGGER.debug(f"Found app version: {version}")
                self._settings.version = version
                return
        except Exception as e:
            _LOGGER.warning(f"Getting app version: {e}")
            pass
        _LOGGER.debug(f"Failed to retrive app version using version {self._settings.version}")

    async def _update_appbrain(self):        
        _LOGGER.debug("Fetching latest app version from app brain")
        try:            
            response = await self._client.get("https://www.appbrain.com/app/panasonic-comfort-cloud/com.panasonic.ACCsmart")
            responseText = await response.text()
            soup = BeautifulSoup(responseText, "html.parser")
            meta_tag = soup.find("meta", itemprop="softwareVersion")
            if meta_tag:
                version = meta_tag['content']
                _LOGGER.debug(f"Found app version: {version}")
                self._settings.version = version
                return
        except Exception as e:
            _LOGGER.warning(f"Getting app version: {e}")
            pass
        _LOGGER.debug(f"Failed to retrive app version using version {self._settings.version}")

    async def _update_playstore(self):
        _LOGGER.debug("Fetching latest app version from play store")
        try:            
            response = await self._client.get("https://play.google.com/store/apps/details?id=com.panasonic.ACCsmart")
            responseText = await response.text()
            version_match = re.search(r'\["(\d+\.\d+\.\d+)"\]', responseText)
            if version_match:
                version = version_match.group(1)
                _LOGGER.debug(f"Found app version: {version}")
                self._settings.version = version
                return
        except Exception as e:
            _LOGGER.warning(f"Getting app version: {e}")
            pass
        _LOGGER.debug(f"Failed to retrive app version using version {self._settings.version}")