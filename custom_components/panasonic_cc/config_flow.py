"""Config flow for the Panasonic Comfort Cloud platform."""
import asyncio
from typing import Any, Dict, Optional
import logging

from aiohttp import ClientError
from async_timeout import timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback

from . import DOMAIN as PANASONIC_DOMAIN

from .panasonic import PanasonicApiDevice

from .const import (
    KEY_DOMAIN, 
    TIMEOUT, 
    CONF_FORCE_OUTSIDE_SENSOR, 
    CONF_ENABLE_DAILY_ENERGY_SENSOR, 
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR)

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register("panasonic_cc")
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PanasonicOptionsFlowHandler(config_entry)

    async def _create_entry(self, username, password):
        """Register new entry."""
        # Check if ip already is registered
        for entry in self._async_current_entries():
            if entry.data[KEY_DOMAIN] == PANASONIC_DOMAIN:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="", data={
            CONF_USERNAME: username, 
            CONF_PASSWORD: password, 
            CONF_FORCE_OUTSIDE_SENSOR: False,
            CONF_ENABLE_DAILY_ENERGY_SENSOR: DEFAULT_ENABLE_DAILY_ENERGY_SENSOR
            })

    async def _create_device(self, username, password):
        """Create device."""
        import pcomfortcloud
        try:

            api = pcomfortcloud.Session(username, password, verifySsl=False)
            devices = await self.hass.async_add_executor_job(api.get_devices)
            if not devices:
                _LOGGER.warning("No device returned from Panasonic Cloud")
                return self.async_abort(reason="No devices")
        except asyncio.TimeoutError:
            _LOGGER.warning("Unable to connect to Panasonic Cloud: timed out")
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

class PanasonicOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Panasonic options."""

    def __init__(self, config_entry):
        """Initialize Panasonic options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Manage Panasonic options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FORCE_OUTSIDE_SENSOR,
                        default=self.config_entry.options.get(
                            CONF_FORCE_OUTSIDE_SENSOR, False
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_DAILY_ENERGY_SENSOR,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR
                        ),
                    ): bool,
                }
            ),
        )