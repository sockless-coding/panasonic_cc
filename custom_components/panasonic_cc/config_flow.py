from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from aio_panasonic_comfort_cloud import ApiClient, MFARequiredError
from aio_panasonic_comfort_cloud.exceptions import AgreementNotAcceptedError

from .const import (
    CONF_AUTO_POWER_ON,
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_ENERGY_FETCH_INTERVAL,
    CONF_FORCE_ENABLE_NANOE,
    CONF_FORCE_OUTSIDE_SENSOR,
    CONF_USE_PANASONIC_PRESET_NAMES,
    DEFAULT_AUTO_POWER_ON,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    DEFAULT_FORCE_ENABLE_NANOE,
    DEFAULT_USE_PANASONIC_PRESET_NAMES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Transient form field for the one-time 2FA/MFA code — never persisted.
CONF_OTP_CODE = "otp_code"
# Transient form field for accepting updated Panasonic account agreements.
CONF_ACCEPT_AGREEMENTS = "accept_agreements"


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 3
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        # Credentials awaiting a 2FA/MFA code, stashed between the initial
        # step and the "otp" step — never persisted.
        self._pending_input: dict[str, Any] | None = None
        self._pending_origin: str | None = None
        # The authenticated (but not yet group-listed) client and the
        # agreement documents it's blocked on, stashed between the initial
        # step and the "agreements" step.
        self._pending_api: ApiClient | None = None
        self._pending_agreements: list[dict[str, Any]] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a user initiated config flow."""
        if user_input is None:
            return self._show_user_form()

        return await self._async_handle_login(user_input, "user")

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the 2FA/MFA one-time code step.

        Only reached when the account actually requires a code — a rare
        event that most users will never see.
        """
        if user_input is None:
            return self._show_otp_form()

        assert self._pending_input is not None
        assert self._pending_origin is not None
        merged_input = {**self._pending_input, CONF_OTP_CODE: user_input[CONF_OTP_CODE]}
        return await self._async_handle_login(merged_input, self._pending_origin)

    async def async_step_agreements(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show pending Panasonic account agreements and record acceptance.

        Only reached when Panasonic has updated its terms/privacy policy
        and the account needs to (re-)accept them before it can be used.
        """
        if user_input is None:
            return await self._show_agreements_form()

        if not user_input.get(CONF_ACCEPT_AGREEMENTS):
            return await self._show_agreements_form({"base": "agreements_not_accepted"})

        assert self._pending_api is not None
        assert self._pending_agreements is not None
        assert self._pending_input is not None
        assert self._pending_origin is not None

        try:
            await self._pending_api.accept_agreements([
                {"type": doc["type"], "version": doc["version"]}
                for doc in self._pending_agreements
            ])
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Failed to accept Panasonic account agreements")
            return await self._show_agreements_form({"base": "device_fail"})

        pending_input = self._pending_input
        origin = self._pending_origin
        self._pending_api = None
        self._pending_agreements = None
        return await self._async_handle_login(pending_input, origin)

    async def _async_handle_login(
        self, user_input: dict[str, Any], origin: str
    ) -> config_entries.ConfigFlowResult:
        """Validate credentials, transparently handling a 2FA challenge or
        pending account agreements.

        `origin` is the step ("user", "reconfigure" or "reauth_confirm") to
        fall back to if validation fails outright, so errors are shown on
        the form the user was actually filling in.
        """
        otp_code = user_input.get(CONF_OTP_CODE)
        try:
            errors = await self._async_try_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], otp_code
            )
        except MFARequiredError:
            _LOGGER.debug("Account requires a 2FA code, asking the user for one")
            self._pending_input = {
                key: value for key, value in user_input.items() if key != CONF_OTP_CODE
            }
            self._pending_origin = origin
            return self._show_otp_form()
        except AgreementNotAcceptedError:
            _LOGGER.debug("Account has updated agreements pending acceptance")
            self._pending_input = {
                key: value for key, value in user_input.items() if key != CONF_OTP_CODE
            }
            self._pending_origin = origin
            return await self._show_agreements_form()

        if errors:
            # If a code was part of this attempt, the credentials already
            # passed and it was the code itself that was rejected — keep the
            # user on the OTP form rather than sending them back to the start.
            if otp_code is not None:
                return self._show_otp_form(errors)
            if origin == "user":
                return self._show_user_form(errors)
            if origin == "reauth_confirm":
                return self._show_reauth_confirm_form(errors)
            return self._show_reconfigure_form(errors)

        self._pending_input = None
        self._pending_origin = None
        if origin == "reauth_confirm":
            reauth_entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                reauth_entry,
                data={
                    **reauth_entry.data,
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
            )
        return await self._async_create_entry(user_input)

    async def _async_try_login(
        self, username: str, password: str, otp_code: str | None = None
    ) -> dict[str, str]:
        """Attempt to authenticate and fetch the account's devices.

        Returns a dict of form errors (empty on success). Raises
        MFARequiredError if the account needs a 2FA code that wasn't
        supplied, or AgreementNotAcceptedError if Panasonic requires
        acceptance of updated agreements — the caller is expected to
        prompt for the missing input and retry.
        """
        client = async_get_clientsession(self.hass)
        api = ApiClient(username, password, client)
        errors: dict[str, str] = {}
        try:
            await api.start_session(otp_code)

            if not api.has_devices:
                errors["base"] = "no_devices"
        except MFARequiredError:
            raise
        except AgreementNotAcceptedError:
            # Login itself succeeded — only the group listing was blocked —
            # so this same authenticated client can accept the agreements
            # and be reused to retry without logging in again.
            self._pending_api = api
            raise
        except asyncio.TimeoutError:
            _LOGGER.exception("TimeoutError")
            errors["base"] = "device_timeout"
        except ClientError:
            _LOGGER.exception("ClientError")
            errors["base"] = "device_fail"
        except Exception as ex:  # pylint: disable=broad-except
            err_msg = str(ex)
            if "invalid_user_password" in err_msg:
                errors["base"] = "invalid_user_password"
            elif otp_code is not None and "otp" in err_msg.lower():
                errors["base"] = "invalid_otp"
            else:
                _LOGGER.exception("Unexpected error validating credentials")
                errors["base"] = "device_fail"
        return errors

    def _show_user_form(
        self, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
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
                    CONF_AUTO_POWER_ON,
                    default=DEFAULT_AUTO_POWER_ON,
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
            errors=errors,
        )

    def _show_reconfigure_form(
        self, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    def _show_otp_form(
        self, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required(CONF_OTP_CODE): str}),
            errors=errors,
        )

    def _show_reauth_confirm_form(
        self, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": self._get_reauth_entry().data[CONF_USERNAME]},
            errors=errors,
        )

    async def _show_agreements_form(
        self, errors: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        assert self._pending_api is not None
        if self._pending_agreements is None:
            try:
                self._pending_agreements = await self._async_fetch_pending_agreements(
                    self._pending_api
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Failed to fetch pending Panasonic account agreements")
                origin = self._pending_origin
                self._pending_api = None
                self._pending_agreements = None
                self._pending_input = None
                self._pending_origin = None
                if origin == "reauth_confirm":
                    return self._show_reauth_confirm_form({"base": "device_fail"})
                if origin == "reconfigure":
                    return self._show_reconfigure_form({"base": "device_fail"})
                return self._show_user_form({"base": "device_fail"})

        agreements_text = "\n\n---\n\n".join(
            doc.get("content") or f"Agreement type {doc['type']} (version {doc['version']})"
            for doc in self._pending_agreements
        )
        return self.async_show_form(
            step_id="agreements",
            data_schema=vol.Schema({vol.Required(CONF_ACCEPT_AGREEMENTS, default=False): bool}),
            description_placeholders={"agreements": agreements_text},
            errors=errors,
        )

    @staticmethod
    async def _async_fetch_pending_agreements(api: ApiClient) -> list[dict[str, Any]]:
        """Return the agreement documents the account hasn't accepted yet."""
        documents = await api.get_agreement_documents()
        accepted = await api.get_agreement_status()
        accepted_versions = {item.get("type"): item.get("version") for item in accepted}

        pending: list[dict[str, Any]] = []
        for document in documents:
            try:
                doc_type = int(document.get("type"))
            except (TypeError, ValueError):
                continue
            version = document.get("version")
            if accepted_versions.get(doc_type) == version:
                continue
            pending.append({**document, "type": doc_type})
        return pending

    async def _async_create_entry(self, user_input: dict[str, Any]) -> config_entries.ConfigFlowResult:
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
            },
            options={
                CONF_FORCE_OUTSIDE_SENSOR: False,
                CONF_FORCE_ENABLE_NANOE: user_input.get(CONF_FORCE_ENABLE_NANOE, DEFAULT_FORCE_ENABLE_NANOE),
                CONF_ENABLE_DAILY_ENERGY_SENSOR: user_input.get(CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR),
                CONF_USE_PANASONIC_PRESET_NAMES: user_input.get(CONF_USE_PANASONIC_PRESET_NAMES, DEFAULT_USE_PANASONIC_PRESET_NAMES),
                CONF_AUTO_POWER_ON: user_input.get(CONF_AUTO_POWER_ON, DEFAULT_AUTO_POWER_ON),
                CONF_DEVICE_FETCH_INTERVAL: user_input.get(CONF_DEVICE_FETCH_INTERVAL, DEFAULT_DEVICE_FETCH_INTERVAL),
                CONF_ENERGY_FETCH_INTERVAL: user_input.get(CONF_ENERGY_FETCH_INTERVAL, DEFAULT_ENERGY_FETCH_INTERVAL),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a reconfiguration flow."""
        if user_input is None:
            return self._show_reconfigure_form()

        return await self._async_handle_login(user_input, "reconfigure")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication, e.g. triggered by pending agreements
        discovered while the integration was running."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm re-authentication with the account's current password."""
        if user_input is None:
            return self._show_reauth_confirm_form()

        reauth_entry = self._get_reauth_entry()
        merged_input = {
            CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }
        return await self._async_handle_login(merged_input, "reauth_confirm")


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an option changes."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
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
                    CONF_AUTO_POWER_ON,
                    default=self._config_entry.options.get(
                        CONF_AUTO_POWER_ON, DEFAULT_AUTO_POWER_ON
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
