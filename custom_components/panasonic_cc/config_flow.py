"""Config flow for the Panasonic Comfort Cloud platform."""
import asyncio
import logging

from aiohttp import ClientError
from async_timeout import timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from . import DOMAIN as PANASONIC_DOMAIN

from .panasonic import PanasonicApiDevice

from .const import KEY_DOMAIN, TIMEOUT

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register("panasonic_cc")
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _create_entry(self, username, password):
        """Register new entry."""
        # Check if ip already is registered
        for entry in self._async_current_entries():
            if entry.data[KEY_DOMAIN] == PANASONIC_DOMAIN:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="", data={CONF_USERNAME: username, CONF_PASSWORD: password})

    async def _create_device(self, username, password):
        """Create device."""
        import pcomfortcloud
        try:

            api = pcomfortcloud.Session(username, password, verifySsl=False)
            devices = await self.hass.async_add_executor_job(api.get_devices)
            if not devices:
                return self.async_abort(reason="No devices")
        except asyncio.TimeoutError:
            return self.async_abort(reason="device_timeout")
        except ClientError:
            _LOGGER.exception("ClientError")
            return self.async_abort(reason="device_fail")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device")
            return self.async_abort(reason="device_fail")

        return await self._create_entry(username, password)

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str
                    })
            )
        return await self._create_device(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

    async def async_step_import(self, user_input):
        """Import a config entry."""
        username = user_input.get(CONF_USERNAME)
        if not username:
            return await self.async_step_user()
        return await self._create_device(username, user_input[CONF_PASSWORD])

    