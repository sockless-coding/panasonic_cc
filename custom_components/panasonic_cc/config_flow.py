"""Config flow for the Panasonic Comfort Cloud platform."""
import asyncio
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN as PANASONIC_DOMAIN
from .const import (
    KEY_DOMAIN,
    CONF_FORCE_OUTSIDE_SENSOR,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_USE_PANASONIC_PRESET_NAMES,
    DEFAULT_USE_PANASONIC_PRESET_NAMES)

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
            CONF_ENABLE_DAILY_ENERGY_SENSOR: DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
            CONF_USE_PANASONIC_PRESET_NAMES: DEFAULT_USE_PANASONIC_PRESET_NAMES
        })

    async def _create_device(self, username, password):
        """Create device."""
        from . import pcomfortcloud
        try:
            client = async_get_clientsession(self.hass)
            api = pcomfortcloud.ApiClient(username, password, client)
            await api.start_session()
            devices = api.get_devices()

            if not devices:
                _LOGGER.debug("Not devices found")
                return self.async_abort(reason="No devices")

        except asyncio.TimeoutError as te:
            _LOGGER.exception("TimeoutError", te)
            return self.async_abort(reason="device_timeout")
        except ClientError as ce:
            _LOGGER.exception("ClientError", ce)
            return self.async_abort(reason="device_fail")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device", e)
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
                    vol.Optional(
                        CONF_USE_PANASONIC_PRESET_NAMES,
                        default=self.config_entry.options.get(
                            CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES
                        ),
                    ): bool,
                }
            ),
        )
