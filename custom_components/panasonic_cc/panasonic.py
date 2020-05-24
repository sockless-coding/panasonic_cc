
from datetime import timedelta
import logging

from typing import Any, Dict, Optional, List
from homeassistant.util import Throttle
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.helpers.typing import HomeAssistantType

from .const import PRESET_LIST, OPERATION_LIST

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

def api_call_login(func):
    def wrapper_call(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            args[0]._api.login()
            func(*args, **kwargs)
    return wrapper_call

class PanasonicApiDevice:

    def __init__(self, hass: HomeAssistantType, api, device):
        from pcomfortcloud import constants
        self.hass = hass
        self._api = api
        self.device = device
        self.id = device['id']
        self.name = device['name']
        self.group = device['group']
        self.data = None
        self._available = True
        self.constants = constants
        

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, **kwargs):
        await self.do_update()

    async def do_update(self):
        try:
            data= await self.hass.async_add_executor_job(self._api.get_device,self.id)
        except:
            _LOGGER.debug("Error trying to get device {id} state, probably expired token, trying to update it...".format(**self.device))
            self._api.login()
            data = self._api.get_device(self.id)

        if data is None:
            self._available = False
            _LOGGER.debug("Received no data for device {id}".format(**self.device))
            return
        self._available = True
        self.data = data

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": { ("panasonic_cc", self.id) },
            "manufacturer": "Panasonic",
            "model": self.device['model'],
            "name": self.name,
        }

    @property
    def is_on(self):
        return bool( self.data['parameters']['power'].value )

    @property
    def inside_temperature(self):
        if self.data['parameters']['temperatureInside'] != 126:
            return self.data['parameters']['temperatureInside']
        return None

    @property
    def support_inside_temperature(self):
        return self.inside_temperature != None

    @property
    def outside_temperature(self):
        return self.data['parameters']['temperatureOutside']

    @property
    def support_outside_temperature(self):
        return self.outside_temperature != 126

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self.data['parameters']['temperature'] != 126:
            return self.data['parameters']['temperature']
        return None

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.data['parameters']['fanSpeed'].name

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self.data['parameters']['airSwingVertical'].name

    @property
    def hvac_mode(self):
        """Return the current operation."""
        return self.data['parameters']['mode'].name

    @property
    def eco_mode(self) -> Optional[str]:
        return self.data['parameters']['eco'].name

    @property
    def nanoe_mode(self):
        p = self.data['parameters']
        if 'nanoe' in p:
            return p['nanoe']
        return None

    
    async def turn_off(self):
        await self.hass.async_add_executor_job(
            self.set_device,
            { "power": self.constants.Power.Off }
        )
        await self.do_update()

    async def turn_on(self):
        await self.hass.async_add_executor_job(
            self.set_device,
            { "power": self.constants.Power.On }
        )
        await self.do_update()
        
    async def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Set %s ecomode %s", self.name, preset_mode)
        await self.hass.async_add_executor_job(
            self.set_device,
            { 
                "power": self.constants.Power.On,
                "eco": self.constants.EcoMode[ PRESET_LIST[preset_mode] ]
            })
        await self.do_update()

    async def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)

        await self.hass.async_add_executor_job(
            self.set_device,
            { "temperature": target_temp }
        )
        await self.do_update()
        

    async def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { "fanSpeed": self.constants.FanSpeed[fan_mode] }
        )
        await self.do_update()
    
    async def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        _LOGGER.debug("Set %s mode %s", self.name, hvac_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { 
                "power": self.constants.Power.On,
                "mode": self.constants.OperationMode[OPERATION_LIST[hvac_mode]] 
            })

        await self.do_update()

    async def set_swing_mode(self, swing_mode):
        """Set swing mode."""
        _LOGGER.debug("Set %s swing mode %s", self.name, swing_mode)
        if swing_mode == 'Auto':
            automode = self.constants.AirSwingAutoMode["AirSwingUD"]
        else:
            automode = self.constants.AirSwingAutoMode["Disabled"]

        _LOGGER.debug("Set %s swing mode %s", self.name, swing_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { 
                "power": self.constants.Power.On,
                "airSwingVertical": self.constants.AirSwingUD[swing_mode],
                "fanAutoMode": automode
            })
        await self.do_update()

    async def set_nanoe_mode(self, nanoe_mode):
        """Set new nanoe mode."""
        _LOGGER.debug("Set %s nanoe mode %s", self.name, nanoe_mode)

        await self.hass.async_add_executor_job(
            self.set_device,
            { "nanoe": self.constants.NanoeMode[nanoe_mode] }
        )
        await self.do_update()

    @api_call_login
    def set_device(self, args):
        self._api.set_device(
            self.id,
            **args
        )
