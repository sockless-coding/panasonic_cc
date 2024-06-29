import json
from datetime import timedelta
import logging
from datetime import datetime
from functools import cached_property 

from typing import Optional
from homeassistant.util import Throttle
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.components.climate.const import ATTR_HVAC_MODE
from homeassistant.helpers.storage import Store
from .pcomfortcloud.apiclient import ApiClient
from .pcomfortcloud.panasonicdevice import PanasonicDevice, PanasonicDeviceZone
from .pcomfortcloud import constants

from .const import OPERATION_LIST, PRESET_8_15, PRESET_NONE, PRESET_ECO, PRESET_BOOST, PRESET_QUIET, PRESET_POWERFUL

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)



class PanasonicApiDevice:

    def __init__(
            self, 
            hass: HomeAssistant, 
            api: ApiClient, 
            device, 
            force_outside_sensor, 
            enable_energy_sensor,
            use_panasonic_preset_names: bool): # noqa: E501
        from .pcomfortcloud import constants
        self.hass = hass
        self._api = api
        self.device = device
        self._details: PanasonicDevice = None
        self.force_outside_sensor = force_outside_sensor
        self.enable_energy_sensor = enable_energy_sensor
        self._use_panasonic_preset_names = use_panasonic_preset_names
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
        self._store = Store(hass, version=1, key=f"panasonic_cc_{self.id}")
        

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
                await self._api.refresh_token()
                data = await self._api.get_device(self.id)
            except:
                _LOGGER.warning("Failed to renew token for device {id}, giving up for now".format(**self.device))  # noqa: E501
                return

        if data is None:
            self._available = False
            _LOGGER.debug("Received no data for device {id}".format(**self.device))
            return
        self._details = data
        try:
            _LOGGER.debug("Data: {}".format(data))

            self._is_on = bool(data.parameters.power.value)
            if data.parameters.inside_temperature is not None:
                self._inside_temperature = data.parameters.inside_temperature
            if data.parameters.outside_temperature is not None:
                self._outside_temperature = data.parameters.outside_temperature
            if data.parameters.target_temperature is not None:
                self._target_temperature = data.parameters.target_temperature
            self._fan_mode = data.parameters.fan_speed.name
            self._swing_mode = data.parameters.vertical_swing_mode.name
            self._swing_lr_mode = data.parameters.horizontal_swing_mode.name
            self._hvac_mode = data.parameters.mode.name
            self._eco_mode = data.parameters.eco_mode.name
            self._nanoe_mode = data.parameters.nanoe_mode

        except Exception as e:
            _LOGGER.debug("Failed to set data for device {id}".format(**self.device))
            _LOGGER.debug("Set data Error: {0}".format(e))
        self._available = True
        #self.data = data

    async def do_update_energy(self):
        #_LOGGER.debug("Requesting energy for device {id}".format(**self.device))
        today = datetime.now().strftime("%Y%m%d")
        try:
            data= await self._api.history(self.id,"Month",today) # noqa: E501
            
        except:
            _LOGGER.debug("Error trying to get device {id} state, probably expired token, trying to update it...".format(**self.device)) # noqa: E501
            try:
                await self._api.refresh_token()
                data= await self._api.history(self.id,"Month",today) # noqa: E501
            except:
                _LOGGER.debug("Failed to renew token for device {id}, giving up for now".format(**self.device)) # noqa: E501
                return

        if data is None:
            _LOGGER.debug("Received no energy data for device {id}".format(**self.device)) # noqa: E501
            return
        
        if 'historyDataList' not in data['parameters']:
            return
        t1 = datetime.now()
        history = data['parameters']['historyDataList']
        c_energy = None
        for item in history:
            if 'dataTime' not in item:
                continue
            if item['dataTime'] != today:
                continue
            if 'consumption' not in item:
                break
            c_energy = item['consumption']
            break

        if (c_energy is None) or (c_energy < 0):
            return
        t1 = datetime.now()
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
        self._daily_energy = c_energy

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
    
    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self.in_summer_house_mode:
            return 8
        return 16

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self.in_summer_house_mode:
            return 15 if self._details.features.summer_house == 2 else 10
        return 30

    @cached_property
    def support_eco_navi(self) -> bool:
        return self._details.features.eco_navi
    
    @property
    def eco_navi(self):
        return self._details.parameters.eco_navi_mode
    
    @cached_property
    def support_zones(self) -> bool:
        if not self._details:
            return False
        return self._details.parameters.zones.count() > 0
    
    @property
    def zones(self):
        if not self._details:
            return [PanasonicDeviceZone]
        return self._details.parameters.zones

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

    def _get_quiet_preset(self):
        return PRESET_QUIET if self._use_panasonic_preset_names else PRESET_ECO
    def _get_powerful_preset(self):
        return PRESET_POWERFUL if self._use_panasonic_preset_names else PRESET_BOOST

    @cached_property
    def available_presets(self):
        presets = [PRESET_NONE]
        if self._details.features.quiet_mode:
            presets.append(self._get_quiet_preset())
        if self._details.features.powerful_mode:
            presets.append(self._get_powerful_preset())
        if self._details.features.summer_house > 0:
            presets.append(PRESET_8_15)
        return presets

    @property  
    def preset_mode(self):
        if not self._details:
            return PRESET_NONE
        match self._details.parameters.eco_mode:
            case constants.EcoMode.Quiet:
                return self._get_quiet_preset()
            case constants.EcoMode.Powerful:
                return self._get_powerful_preset()
        if self.in_summer_house_mode:
            return PRESET_8_15        

        return PRESET_NONE

    @property
    def in_summer_house_mode(self):
        if not self._details:
            return False
        temp = self._details.parameters.target_temperature
        i = 1 if temp - 8 > 0 else (0 if temp -8 else -1)
        match self._details.features.summer_house:
            case 1:
                return i == 0 or temp == 10
            case 2:
                return i >= 0 and temp <= 15
            case 3:
                return i == 0 or temp == 10
        return False

    async def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Set %s ecomode %s", self.name, preset_mode)
        data = {
            "power": constants.Power.On,
            "eco": constants.EcoMode.Auto
        }
        if self.in_summer_house_mode and preset_mode != PRESET_8_15:
            await self._exit_summer_house_mode(data)

        if preset_mode == self._get_quiet_preset():
            data["eco"] = constants.EcoMode.Quiet
        elif preset_mode == self._get_powerful_preset():
            data["eco"] = constants.EcoMode.Powerful
        elif preset_mode == PRESET_8_15:
            await self._enter_summer_house_mode()
            data["mode"] = constants.OperationMode.Heat
            data["eco"] = constants.EcoMode.Auto
            data["temperature"] = 8
            data["fanSpeed"] = constants.FanSpeed.High
        
        await self.set_device(data)
        await self.do_update()

    async def _enter_summer_house_mode(self):
        data = await self._store.async_load()
        if data is None:
            data = {}
        data['mode'] = self._details.parameters.mode
        data['ecoMode'] = self._details.parameters.eco_mode
        data['targetTemperature'] = self._details.parameters.target_temperature
        data['fanSpeed'] = self._details.parameters.fan_speed
        await self._store.async_save(data)

    async def _exit_summer_house_mode(self, device_data):
        stored_data = await self._store.async_load()
        if stored_data is None:
            return
        if 'mode' in stored_data:
            device_data['mode'] = stored_data['mode']
        if 'ecoMode' in stored_data:
            device_data["eco"] = stored_data['ecoMode']
        if 'targetTemperature' in stored_data:
            device_data['temperature'] = stored_data['targetTemperature']
        if 'fanSpeed' in stored_data:
            device_data['fanSpeed'] = stored_data['fanSpeed']


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
        data = {
            'power': self.constants.Power.On
        }
        if self.in_summer_house_mode:
            await self._exit_summer_house_mode(data)
        data['mode'] = self.constants.OperationMode[OPERATION_LIST[hvac_mode]] 

        await self.set_device(data)

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

    async def set_eco_navi_mode(self, eco_navi: constants.EcoNaviMode):
        """Set new eco navi mode."""
        _LOGGER.debug("Set %s eco navi mode %s", self.name, eco_navi.name)

        await self.set_device(
            { "ecoNavi": eco_navi }
        )
        await self.do_update()

    async def set_zone(
            self, 
            zone_id: int, 
            mode: constants.ZoneMode = None, 
            level: int = None,
            temperature: int = None,
            spill: int = None):
        """Set new zone."""
        _LOGGER.debug("Set %s zone id: %s", self.name, zone_id)
        data = {
            "zoneId": zone_id
        }
        if mode is not None:
            data["zoneOnOff"] = mode.value
        if level is not None:
            data["zoneLevel"] = level
        if temperature is not None:
            data["zoneTemperature"] = temperature
        if spill is not None:
            data["zoneSpill"] = spill
        await self.set_device(
            { "zoneParameters": data }
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
