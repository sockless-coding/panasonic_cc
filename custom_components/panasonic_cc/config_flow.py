from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import ActionResponse
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from aio_panasonic_comfort_cloud import ApiClient

from .const import (
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_ENERGY_FETCH_INTERVAL,
    CONF_FORCE_ENABLE_NANOE,
    CONF_FORCE_OUTSIDE_SENSOR,
    CONF_USE_PANASONIC_PRESET_NAMES,
    DATA_COORDINATORS,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    DEFAULT_FORCE_ENABLE_NANOE,
    DEFAULT_USE_PANASONIC_PRESET_NAMES,
    DOMAIN,
    ENERGY_COORDINATORS,
)

_LOGGER = logging.getLogger(__name__)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle a user initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_ENABLE_DAILY_ENERGY_SENSOR,
                        default=DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
                    ): bool,
                    vol.Optional(
                        CONF_FORCE_ENABLE_NANOE,
                        default=DEFAULT_FORCE_ENABLE_NANOE,
                    ): bool,
                    vol.Optional(
                        CONF_USE_PANASONIC_PRESET_NAMES,
                        default=DEFAULT_USE_PANASONIC_PRESET_NAMES,
                    ): bool,
                    vol.Optional(
                        CONF_DEVICE_FETCH_INTERVAL,
                        default=DEFAULT_DEVICE_FETCH_INTERVAL,
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                    vol.Optional(
                        CONF_ENERGY_FETCH_INTERVAL,
                        default=DEFAULT_ENERGY_FETCH_INTERVAL,
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
                }),
            )

        return await self._async_create_entry(user_input)

    async def _async_create_entry(self, user_input: dict[str, Any]) -> config_entries.FlowResult:
        """Create a config entry."""
        # Validate no duplicate entries
        self._async_abort_entries_match({
            CONF_USERNAME: user_input[CONF_USERNAME],
        })

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_FORCE_OUTSIDE_SENSOR: False,
                CONF_FORCE_ENABLE_NANOE: user_input.get(CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE),
                CONF_ENABLE_DAILY_ENERGY_SENSOR: user_input.get(CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR),
                CONF_USE_PANASONIC_PRESET_NAMES: user_input.get(CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES),
                CONF_DEVICE_FETCH_INTERVAL: user_input.get(CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL),
                CONF_ENERGY_FETCH_INTERVAL: user_input.get(CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL),
            },
        )

    async def _async_validate_user_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Validate the user input."""
        errors: dict[str, str] = {}

        client = async_get_clientsession(self.hass)
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        api = ApiClient(username, password, client)

        try:
            await api.reauthenticate()
            devices = api.get_devices()

            if not devices and not api.has_unknown_devices:
                errors["base"] = "no_devices"
        except asyncio.TimeoutError:
            _LOGGER.exception("TimeoutError")
            errors["base"] = "device_timeout"
        except ClientError:
            _LOGGER.exception("ClientError")
            errors["base"] = "device_fail"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error")
            errors["base"] = "device_fail"

        if errors:
            raise ActionResponse("show_form", errors=errors)

        return {}

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle a reconfiguration flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_confirm",
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }),
            )

        return await self._async_create_entry(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an option changes."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self._config_entry.options,
                    **user_input,
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_FORCE_OUTSIDE_SENSOR,
                    default=self._config_entry.options.get(
                        CONF_FORCE_OUTSIDE_SENSOR, False
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_DAILY_ENERGY_SENSOR,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR
                    ),
                ): bool,
                vol.Optional(
                    CONF_FORCE_ENABLE_NANOE,
                    default=self._config_entry.options.get(
                        CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE
                    ),
                ): bool,
                vol.Optional(
                    CONF_USE_PANASONIC_PRESET_NAMES,
                    default=self._config_entry.options.get(
                        CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES
                    ),
                ): bool,
                vol.Optional(
                    CONF_DEVICE_FETCH_INTERVAL,
                    default=self._config_entry.options.get(
                        CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Optional(
                    CONF_ENERGY_FETCH_INTERVAL,
                    default=self._config_entry.options.get(
                        CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
            }),
        )
