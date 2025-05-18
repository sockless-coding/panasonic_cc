"""Platform for the Panasonic Comfort Cloud."""
import logging
from typing import Dict

import asyncio

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration
from aio_panasonic_comfort_cloud import ApiClient
from aioaquarea import Client as AquareaApiClient, AquareaEnvironment

from .const import (
    CONF_UPDATE_INTERVAL_VERSION,
    CONF_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_DEVICE_FETCH_INTERVAL,
    CONF_ENERGY_FETCH_INTERVAL,
    DEFAULT_DEVICE_FETCH_INTERVAL,
    DEFAULT_ENERGY_FETCH_INTERVAL,
    DEFAULT_ENABLE_DAILY_ENERGY_SENSOR,
    CONF_USE_PANASONIC_PRESET_NAMES,
    PANASONIC_DEVICES,
    COMPONENT_TYPES,
    STARTUP,
    DATA_COORDINATORS,
    ENERGY_COORDINATORS,
    AQUAREA_COORDINATORS)

from .coordinator import PanasonicDeviceCoordinator, PanasonicDeviceEnergyCoordinator, AquareaDeviceCoordinator


_LOGGER = logging.getLogger(__name__)

DOMAIN = "panasonic_cc"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_ENABLE_DAILY_ENERGY_SENSOR, default=DEFAULT_ENABLE_DAILY_ENERGY_SENSOR): cv.boolean,
                # noqa: E501
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

AQUAREA_DEMO = False

def setup(hass, config):
    pass


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the Garo Wallbox component."""

    hass.data.setdefault(DOMAIN, {})
    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info(STARTUP, integration.version)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Establish connection with Comfort Cloud."""
    

    conf = entry.data
    if PANASONIC_DEVICES not in hass.data:
        hass.data[PANASONIC_DEVICES] = []

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    enable_daily_energy_sensor = entry.options.get(CONF_ENABLE_DAILY_ENERGY_SENSOR, DEFAULT_ENABLE_DAILY_ENERGY_SENSOR)
    
    client = async_get_clientsession(hass)
    api = ApiClient(username, password, client)
    await api.start_session()
    devices = api.get_devices()
    
    if CONF_UPDATE_INTERVAL_VERSION not in conf or conf[CONF_UPDATE_INTERVAL_VERSION] < 2:
        _LOGGER.info("Updating configuration")
        updated_config = dict(entry.data)
        updated_config[CONF_UPDATE_INTERVAL_VERSION] = 2
        if conf[CONF_DEVICE_FETCH_INTERVAL] <= 31:
            updated_config[CONF_DEVICE_FETCH_INTERVAL] = DEFAULT_DEVICE_FETCH_INTERVAL
            _LOGGER.info(f"Setting default fetch interval to {DEFAULT_DEVICE_FETCH_INTERVAL}")        
        if conf[CONF_ENERGY_FETCH_INTERVAL] <= 61:
            updated_config[CONF_ENERGY_FETCH_INTERVAL] = DEFAULT_ENERGY_FETCH_INTERVAL
            _LOGGER.info(f"Setting default energy fetch interval to {DEFAULT_ENERGY_FETCH_INTERVAL}")
        hass.config_entries.async_update_entry(entry, data=updated_config)

   
    if len(devices) == 0 and not api.has_unknown_devices:
        _LOGGER.error("Could not find any Panasonic Comfort Cloud Heat Pumps")
        return False

    _LOGGER.info("Got %s devices", len(devices))
    data_coordinators: list[PanasonicDeviceCoordinator] = []
    energy_coordinators: list[PanasonicDeviceEnergyCoordinator] = []
    aquarea_coordinators: list[AquareaDeviceCoordinator] = []


    for device in devices:
        try:
            device_coordinator = PanasonicDeviceCoordinator(hass, conf, api, device)
            await device_coordinator.async_config_entry_first_refresh()
            data_coordinators.append(device_coordinator)
            if enable_daily_energy_sensor:
                energy_coordinators.append(PanasonicDeviceEnergyCoordinator(hass, conf, api, device))
        except Exception as e:
            _LOGGER.warning(f"Failed to setup device: {device.name} ({e})", exc_info=e)

    if api.has_unknown_devices or AQUAREA_DEMO:
        try:
            
            if not AQUAREA_DEMO:
                aquarea_api_client = AquareaApiClient(client, username, password)
                await aquarea_api_client.login()
            else:
                aquarea_api_client = AquareaApiClient(client, environment=AquareaEnvironment.DEMO)
                aquarea_api_client._access_token = 'dummy'
                aquarea_api_client._token_expiration = None
            aquarea_devices = await aquarea_api_client.get_devices(include_long_id=True)
            for aquarea_device in aquarea_devices:
                try:
                    aquarea_device_coordinator = AquareaDeviceCoordinator(hass, conf, aquarea_api_client, aquarea_device)
                    await aquarea_device_coordinator.async_config_entry_first_refresh()
                    aquarea_coordinators.append(aquarea_device_coordinator)
                except Exception as e:
                    _LOGGER.warning(f"Failed to setup Aquarea device: {aquarea_device.name} ({e})", exc_info=e)
        except Exception as e:
            _LOGGER.warning(f"Failed to setup Aquarea: {e}", exc_info=e)


    hass.data[DOMAIN][DATA_COORDINATORS] = data_coordinators
    hass.data[DOMAIN][ENERGY_COORDINATORS] = energy_coordinators
    hass.data[DOMAIN][AQUAREA_COORDINATORS] = aquarea_coordinators
    await asyncio.gather(
        *(
            data.async_config_entry_first_refresh()
            for data in energy_coordinators
        ),
        return_exceptions=True
    )

    await hass.config_entries.async_forward_entry_setups(entry, COMPONENT_TYPES)
    return True


async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, COMPONENT_TYPES)
