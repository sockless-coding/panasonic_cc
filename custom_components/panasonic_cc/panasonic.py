import json
from datetime import timedelta
import logging
from datetime import datetime

from typing import Optional
from homeassistant.util import Throttle
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.components.climate.const import ATTR_HVAC_MODE

from .const import PRESET_LIST, OPERATION_LIST

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)



class PanasonicApiDevice:

    def __init__(self, hass: HomeAssistant, api, device, force_outside_sensor, enable_energy_sensor): # noqa: E501
        from .pcomfortcloud import constants
        self.hass = hass
        self._api = api
        self.device = device
        self.force_outside_sensor = force_outside_sensor
        self.enable_energy_sensor = enable_energy_sensor
        self.id = device['id']
        self.name = device['name']
        self.group = device['group']
        #self.data = None
        #self.energy_data = None
        self.last_energy_reading = 0
        self.last_energy_reading_time = None
        self.current_power_value = 0
        self.current_power_counter = 0
        self._available = True
        self.constants = constants

        self._is_on = False
        self._inside_temperature = None
        self._outside_temperature = None
        self._target_temperature = None
        self._fan_mode = None
        self._swing_mode = None
        self._swing_lr_mode = None
        self._hvac_mode = None
        self._eco_mode = None
        self._nanoe_mode = None
        self._daily_energy = None

        self.features = None

        

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self, **kwargs):
        await self.do_update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update_energy(self, **kwargs):
        await self.do_update_energy()

    async def update_app_version(self):
        await self._api.update_app_version()

    async def do_update(self):
        #_LOGGER.debug("Requesting data for device {id}".format(**self.device))
        try:
            data = await self._api.get_device(self.id)
        except:
            _LOGGER.debug("Error trying to get device {id} state, probably expired token, trying to update it...".format(**self.device)) # noqa: E501
            try:
                await self.hass.async_add_executor_job(self._api.login)
                data = await self._api.get_device(self.id)
            except:
                _LOGGER.debug("Failed to renew token for device {id}, giving up for now".format(**self.device))  # noqa: E501
                return

        if data is None:
            self._available = False
            _LOGGER.debug("Received no data for device {id}".format(**self.device))
            return
        try:
            _LOGGER.debug("Data: {}".format(data))

            if self.features is None:
                self.features = data.get('features', None)

            plst = data.get('parameters')
            self._is_on = bool(plst.get('power').value)
            if plst.get('temperatureInside') != 126:
                self._inside_temperature = plst.get('temperatureInside')
            if plst.get('temperatureOutside') != 126:
                self._outside_temperature = plst.get('temperatureOutside')
                if self._inside_temperature is None and self._outside_temperature is not None:
                    self._inside_temperature = self._outside_temperature
            if plst.get('temperature') != 126:
                self._target_temperature = plst.get('temperature')
            self._fan_mode = plst.get('fanSpeed').name
            self._swing_mode = plst.get('airSwingVertical').name
            self._swing_lr_mode = plst.get('airSwingHorizontal').name
            self._hvac_mode = plst.get('mode').name
            self._eco_mode = plst.get('eco').name
            self._nanoe_mode = plst.get('nanoe', None)

        except Exception as e:
            _LOGGER.debug("Failed to set data for device {id}".format(**self.device))
            _LOGGER.debug("Set data Error: {0}".format(e))
        self._available = True
        #self.data = data

    async def do_update_energy(self):
        #_LOGGER.debug("Requesting energy for device {id}".format(**self.device))
        try:
            data= await self._api.history(self.id,"Day",datetime.now().strftime("%Y%m%d")) # noqa: E501
            
        except:
            _LOGGER.debug("Error trying to get device {id} state, probably expired token, trying to update it...".format(**self.device)) # noqa: E501
            try:
                await self.hass.async_add_executor_job(self._api.login)
                data= await self._api.get_device(self.id) # noqa: E501
            except:
                _LOGGER.debug("Failed to renew token for device {id}, giving up for now".format(**self.device)) # noqa: E501
                return

        if data is None:
            _LOGGER.debug("Received no energy data for device {id}".format(**self.device)) # noqa: E501
            return
        t1 = datetime.now()
        if 'energyConsumption' in data['parameters']:
            c_energy = data['parameters']['energyConsumption']
            if c_energy:
                if self.last_energy_reading_time is not None:
                    if c_energy != self.last_energy_reading:                
                        d = (t1 - self.last_energy_reading_time).total_seconds() / 60 / 60  # noqa: E501
                        p = round((c_energy - self.last_energy_reading)*1000 / d)
                        self.last_energy_reading = c_energy
                        self.last_energy_reading_time = t1
                        if p >= 0:
                            self.current_power_value = p
                        self.current_power_counter = 0
                    else:
                        self.current_power_counter += 1
                        if self.current_power_counter > 30:
                            self.current_power_value = 0
                else:
                    self.last_energy_reading = c_energy
                    self.last_energy_reading_time = t1
                self._daily_energy = data['parameters']['energyConsumption']

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
            "sw_version": self._api.app_version
        }

    @property
    def is_on(self):
        return self._is_on

    @property
    def inside_temperature(self):
        return self._inside_temperature

    @property
    def support_inside_temperature(self):
        return self._inside_temperature is not None

    @property
    def outside_temperature(self):
        return self._outside_temperature

    @property
    def support_outside_temperature(self):
        if self.force_outside_sensor:
            return True
        return self._outside_temperature is not None

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def fan_mode(self):
        return self._fan_mode

    @property
    def swing_mode(self):
        return self._swing_mode

    @property
    def swing_lr_mode(self):
        return self._swing_lr_mode

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def eco_mode(self) -> Optional[str]:
        return self._eco_mode

    @property
    def nanoe_mode(self):
        return self._nanoe_mode

    @property
    def energy_sensor_enabled(self):
        return self.enable_energy_sensor

    @property
    def daily_energy(self):
        return self._daily_energy

    @property
    def current_power(self):
        if not self.enable_energy_sensor:
            return None
        return self.current_power_value

    async def turn_off(self):
        await self.set_device(
            { "power": self.constants.Power.Off }
        )
        await self.do_update()

    async def turn_on(self):
        await self.set_device(
            { "power": self.constants.Power.On }
        )
        await self.do_update()
        
    async def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Set %s ecomode %s", self.name, preset_mode)
        await self.set_device(
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

        new_values = { "temperature": target_temp }

        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            new_values['power'] = self.constants.Power.On
            new_values['mode'] = self.constants.OperationMode[OPERATION_LIST[hvac_mode]]

        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)

        await self.set_device(
            new_values
        )
        await self.do_update()
        

    async def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)

        await self.set_device(
            { "fanSpeed": self.constants.FanSpeed[fan_mode] }
        )
        await self.do_update()
    
    async def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        _LOGGER.debug("Set %s mode %s", self.name, hvac_mode)

        await self.set_device(
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

        await self.set_device(
            { 
                "power": self.constants.Power.On,
                "airSwingVertical": self.constants.AirSwingUD[swing_mode],
                "fanAutoMode": automode
            })
        await self.do_update()

    async def set_swing_lr_mode(self, swing_mode):
        """Set swing mode."""
        _LOGGER.debug("Set %s horizontal swing mode %s", self.name, swing_mode)
        if swing_mode == 'Auto':
            automode = self.constants.AirSwingAutoMode["AirSwingLR"]
        else:
            automode = self.constants.AirSwingAutoMode["Disabled"]

        _LOGGER.debug("Set %s horizontal swing mode %s", self.name, swing_mode)

        await self.set_device(
            { 
                "power": self.constants.Power.On,
                "airSwingHorizontal": self.constants.AirSwingLR[swing_mode],
                "fanAutoMode": automode
            })
        await self.do_update()

    async def set_nanoe_mode(self, nanoe_mode):
        """Set new nanoe mode."""
        _LOGGER.debug("Set %s nanoe mode %s", self.name, nanoe_mode)

        await self.set_device(
            { "nanoe": self.constants.NanoeMode[nanoe_mode] }
        )
        await self.do_update()


    async def set_device(self, args):
        try:
            await self._api.set_device(
                self.id,
                **args
            )
        except:
            await self._api.start_session()
            await self._api.set_device(
                self.id,
                **args
            )
