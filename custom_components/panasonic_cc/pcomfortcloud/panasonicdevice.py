import logging
import hashlib
from datetime import datetime, timedelta, timezone

from . import constants

_LOGGER = logging.getLogger(__name__)

def read_enum(json, key, type, default_value):
    if key not in json:
        return default_value
    try:
        return type(json[key])
    except Exception as es:
        _LOGGER.warn("Error reading property '%s' with value '%s'", key, json[key], exc_info= es)
    return default_value

def read_value(json, key, default_value):
    return json[key] if key in json else default_value

class PanasonicDeviceInfo:
    def __init__(self, json = None) -> None:
        self.id: str = None
        self.guid = None
        self.name = "Unknown Device"
        self.group = 'My House'
        self.model = ''
        self.load(json)


    def load(self, json):
        if not json:
            return
        if 'deviceHashGuid' in json:
            self.id = json['deviceHashGuid']
        else:
            self.id = hashlib.md5(json['deviceGuid'].encode('utf-8')).hexdigest()
        self.guid = json['deviceGuid']
        self.name = read_value(json, 'deviceName', self.name)
        self.group = read_value(json, 'groupName', self.group)
        self.model = read_value(json, 'deviceModuleNumber', self.model)

    @property
    def is_valid(self):
        return self.id is not None and self.guid is not None
        

class PanasonicDevice:
    def __init__(self, info: PanasonicDeviceInfo, json = None) -> None:
        self._info = info
        self._features: PanasonicDeviceFeatures = None
        self._parameters: PanasonicDeviceParameters = None
        self._last_update = datetime.now(timezone.utc)
        self.load(json)

    @property
    def id(self)->str:
        return self.info.id

    @property
    def info(self) -> PanasonicDeviceInfo:
        return self._info
    
    @property
    def features(self):
        return self._features
    
    @property
    def parameters(self):
        return self._parameters

    @property
    def last_update(self) -> datetime:
        return self._last_update

    @property
    def has_eco_navi(self):
        return self._features.eco_navi and self._parameters.eco_navi_mode != constants.EcoNaviMode.Unavailable
    
    @property
    def has_eco_function(self):
        return self._features.eco_function > 0 and self._parameters.eco_function_mode != constants.EcoFunctionMode.Unavailable
    
    @property
    def has_nanoe(self):
        return self._features.nanoe and self._parameters.nanoe_mode!= constants.NanoeMode.Unavailable
    
    @property
    def has_zones(self):
        return len(self._parameters.zones) > 0
    
    @property
    def has_horizontal_swing(self):
        return self._features.air_swing_lr and self._parameters.horizontal_swing_mode != constants.AirSwingLR.Unavailable
    
    @property
    def has_inside_temperature(self):
        return self._parameters.inside_temperature is not None
    
    @property
    def has_outside_temperature(self):
        return self._parameters.outside_temperature is not None
    
    @property
    def in_summer_house_mode(self):        
        temp = self._parameters.target_temperature
        i = 1 if temp - 8 > 0 else (0 if temp -8 else -1)
        match self._features.summer_house:
            case 1:
                return i == 0 or temp == 10
            case 2:
                return i >= 0 and temp <= 15
            case 3:
                return i == 0 or temp == 10
        return False

    def load(self, json) -> bool:
        has_changed = False
        if not self._features:
            self._features = PanasonicDeviceFeatures(json)
            has_changed = True
        else:
            has_changed = True if self._features.load(json) else has_changed
        json_parameters = None
        if (json is not None and 'parameters' in json):
            json_parameters = json['parameters']
        if not self._parameters:
            self._parameters = PanasonicDeviceParameters(json_parameters)
            has_changed = True
        else:
            has_changed = True if self._parameters.load(json_parameters) else has_changed
        if has_changed:
            self._last_update = datetime.now(timezone.utc)
        return has_changed


class PanasonicDeviceFeatures:
    def __init__(self, json = None) -> None:
        self._permission = 0
        self._summer_house = 0
        self._iAutoX = False
        self._nanoe = False
        self._nanoe_stand_alone = False
        self._auto_mode = False
        self._heat_mode = False
        self._fan_mode = False
        self._dry_mode = False
        self._cool_mode = False
        self._eco_navi = False
        self._powerful_mode = False
        self._quiet_mode = False
        self._air_swing_lr = False
        self._auto_swing_ud = False
        self._eco_function = 0

        self._has_changed = False
        self.load(json)

    @property
    def has_changed(self):
        return self._has_changed
    
    @property
    def permission(self):
        return self._permission
    @permission.setter
    def permission(self, value):
        if self._permission == value:
            return
        self._permission = value
        self._has_changed = True

    @property
    def summer_house(self):
        return self._summer_house
    @summer_house.setter
    def summer_house(self, value):
        if self._summer_house == value:
            return
        self._summer_house = value
        self._has_changed = True

    @property
    def iAutoX(self):
        return self._iAutoX
    @iAutoX.setter
    def iAutoX(self, value):
        if self._iAutoX == value:
            return
        self._iAutoX = value
        self._has_changed = True

    @property
    def nanoe(self):
        return self._nanoe
    @nanoe.setter
    def nanoe(self, value):
        if self._nanoe == value:
            return
        self._nanoe = value
        self._has_changed = True

    @property
    def nanoe_stand_alone(self):
        return self._nanoe_stand_alone
    @nanoe_stand_alone.setter
    def nanoe_stand_alone(self, value):
        if self._nanoe_stand_alone == value:
            return
        self._nanoe_stand_alone = value
        self._has_changed = True

    @property
    def auto_mode(self):
        return self._auto_mode
    @auto_mode.setter
    def auto_mode(self, value):
        if self._auto_mode == value:
            return
        self._auto_mode = value
        self._has_changed = True

    @property
    def heat_mode(self):
        return self._heat_mode
    @heat_mode.setter
    def heat_mode(self, value):
        if self._heat_mode == value:
            return
        self._heat_mode = value
        self._has_changed = True

    @property
    def fan_mode(self):
        return self._fan_mode
    @fan_mode.setter
    def fan_mode(self, value):
        if self._fan_mode == value:
            return
        self._fan_mode = value
        self._has_changed = True

    @property
    def dry_mode(self):
        return self._dry_mode
    @dry_mode.setter
    def dry_mode(self, value):
        if self._dry_mode == value:
            return
        self._dry_mode = value
        self._has_changed = True

    @property
    def cool_mode(self):
        return self._cool_mode
    @cool_mode.setter
    def cool_mode(self, value):
        if self._cool_mode == value:
            return
        self._cool_mode = value
        self._has_changed = True

    @property
    def eco_navi(self):
        return self._eco_navi
    @eco_navi.setter
    def eco_navi(self, value):
        if self._eco_navi == value:
            return
        self._eco_navi = value
        self._has_changed = True

    @property
    def powerful_mode(self):
        return self._powerful_mode
    @powerful_mode.setter
    def powerful_mode(self, value):
        if self._powerful_mode == value:
            return
        self._powerful_mode = value
        self._has_changed = True

    @property
    def quiet_mode(self):
        return self._quiet_mode
    @quiet_mode.setter
    def quiet_mode(self, value):
        if self._quiet_mode == value:
            return
        self._quiet_mode = value
        self._has_changed = True

    @property
    def air_swing_lr(self):
        return self._air_swing_lr
    @air_swing_lr.setter
    def air_swing_lr(self, value):
        if self._air_swing_lr == value:
            return
        self._air_swing_lr = value
        self._has_changed = True

    @property
    def auto_swing_ud(self):
        return self._auto_swing_ud
    @auto_swing_ud.setter
    def auto_swing_ud(self, value):
        if self._auto_swing_ud == value:
            return
        self._auto_swing_ud = value
        self._has_changed = True

    @property
    def eco_function(self):
        return self._eco_function
    @eco_function.setter
    def eco_function(self, value):
        if self._eco_function == value:
            return
        self._eco_function = value
        self._has_changed = True

    def load(self, json) -> bool:        
        if not json:
            return False
        self._has_changed = False
        if 'permission' in json:
            self.permission = json['permission']
        if 'summerHouse' in json:
            self.summer_house = json['summerHouse']
        if 'iAutoX' in json:
            self.iAutoX = json['iAutoX']
        if 'nanoe' in json:
            self.nanoe = json['nanoe']
        if 'nanoeStandAlone' in json:
            self.nanoe_stand_alone = json['nanoeStandAlone']
        if 'autoMode' in json:
            self.auto_mode = json['autoMode']
        if 'heatMode' in json:
            self.heat_mode = json['heatMode']
        if 'fanMode' in json:
            self.fan_mode = json['fanMode']
        if 'dryMode' in json:
            self.dry_mode = json['dryMode']
        if 'coolMode' in json:
            self.cool_mode = json['coolMode']
        if 'ecoNavi' in json:
            self.eco_navi = json['ecoNavi']
        if 'powerfulMode' in json:
            self.powerful_mode = json['powerfulMode']
        if 'quietMode' in json:
            self.quiet_mode = json['quietMode']
        if 'airSwingLR' in json:
            self.air_swing_lr = json['airSwingLR']
        if 'autoSwingUD' in json:
            self.auto_swing_ud = json['autoSwingUD']
        if 'ecoFunction' in json:
            self.eco_function = json['ecoFunction']
        has_changed = self._has_changed
        self._has_changed = False
        return has_changed
        
class PanasonicDeviceParameters:
    def __init__(self, json = None) -> None:
        self._power = constants.Power.Off
        self._mode = constants.OperationMode.Auto
        self._fan_speed = constants.FanSpeed.Auto
        self._horizontal_swing_mode = constants.AirSwingLR.Mid
        self._vertical_swing_mode = constants.AirSwingUD.Mid
        self._eco_mode = constants.EcoMode.Auto
        self._nanoe_mode = constants.NanoeMode.Unavailable
        self._eco_navi_mode = constants.EcoNaviMode.Unavailable
        self._eco_function_mode = constants.EcoFunctionMode.Unavailable
        self._target_temperature: float = None
        self._inside_temperature: float = None
        self._outside_temperature: float = None
        self._zones: list[PanasonicDeviceZone] = []
        self._zone_index: dict[int, PanasonicDeviceZone] = {}
        self._has_changed = False
        self.load(json)
        
    @property
    def has_changed(self):
        return self._has_changed
    
    @property
    def power(self):
        return self._power
    @power.setter
    def power(self, value):
        if self._power == value:
            return
        self._power = value
        self._has_changed = True

    @property
    def mode(self):
        return self._mode
    @mode.setter
    def mode(self, value):
        if self._mode == value:
            return
        self._mode = value
        self._has_changed = True

    @property
    def fan_speed(self):
        return self._fan_speed
    @fan_speed.setter
    def fan_speed(self, value):
        if self._fan_speed == value:
            return
        self._fan_speed = value
        self._has_changed = True

    @property
    def horizontal_swing_mode(self):
        return self._horizontal_swing_mode
    @horizontal_swing_mode.setter
    def horizontal_swing_mode(self, value):
        if self._horizontal_swing_mode == value:
            return
        self._horizontal_swing_mode = value
        self._has_changed = True

    @property
    def vertical_swing_mode(self):
        return self._vertical_swing_mode
    @vertical_swing_mode.setter
    def vertical_swing_mode(self, value):
        if self._vertical_swing_mode == value:
            return
        self._vertical_swing_mode = value
        self._has_changed = True

    @property
    def eco_mode(self):
        return self._eco_mode
    @eco_mode.setter
    def eco_mode(self, value):
        if self._eco_mode == value:
            return
        self._eco_mode = value
        self._has_changed = True

    @property
    def nanoe_mode(self):
        return self._nanoe_mode
    @nanoe_mode.setter
    def nanoe_mode(self, value):
        if self._nanoe_mode == value:
            return
        self._nanoe_mode = value
        self._has_changed = True

    @property
    def eco_navi_mode(self):
        return self._eco_navi_mode
    @eco_navi_mode.setter
    def eco_navi_mode(self, value):
        if self._eco_navi_mode == value:
            return
        self._eco_navi_mode = value
        self._has_changed = True

    @property
    def eco_function_mode(self):
        return self._eco_function_mode
    @eco_function_mode.setter
    def eco_function_mode(self, value):
        if self._eco_function_mode == value:
            return
        self._eco_function_mode = value
        self._has_changed = True

    @property
    def target_temperature(self):
        return self._target_temperature
    @target_temperature.setter
    def target_temperature(self, value):
        if self._target_temperature == value:
            return
        self._target_temperature = value
        self._has_changed = True

    @property
    def inside_temperature(self):
        return self._inside_temperature
    @inside_temperature.setter
    def inside_temperature(self, value):
        if self._inside_temperature == value:
            return
        self._inside_temperature = value
        self._has_changed = True

    @property
    def outside_temperature(self):
        return self._outside_temperature
    @outside_temperature.setter
    def outside_temperature(self, value):
        if self._outside_temperature == value:
            return
        self._outside_temperature = value
        self._has_changed = True

    @property
    def zones(self):
        return self._zones

    def load(self, json) -> bool:
        _LOGGER.debug('Loading device parameters, has data: %s', json is not None)
        if not json:
            return False
        self._has_changed = False

        self.power = read_enum(json, 'operate', constants.Power, self.power)
        self.mode = read_enum(json, 'operationMode', constants.OperationMode, self.mode)
        self.fan_speed = read_enum(json, 'fanSpeed', constants.FanSpeed, self.fan_speed)
        
        self._load_swing_mode(json)
        self._load_temperature(json)        

        self.eco_mode = read_enum(json, 'ecoMode', constants.EcoMode, self.eco_mode)
        self.nanoe_mode = read_enum(json, 'nanoe', constants.NanoeMode, self.nanoe_mode)
        self.eco_navi_mode = read_enum(json, 'ecoNavi', constants.EcoNaviMode, self.eco_navi_mode)
        self.eco_function_mode = read_enum(json, 'ecoFunctionData', constants.EcoFunctionMode, self.eco_function_mode)
        
        has_changed = self._has_changed or self._load_zones(json)
        self._has_changed = False
        return has_changed

    def _load_zones(self, json) -> bool:
        if 'zoneParameters' not in json:
            return False
        has_changed = False

        for zone in json['zoneParameters']:
            if 'zoneId' not in zone:
                continue
            id = zone['zoneId']
            if id in self._zone_index:
                has_changed = has_changed or self._zone_index[id].load(zone)
                continue
            self._zone_index[id] = PanasonicDeviceZone(zone)
            self._zones.append(self._zone_index[id])
            has_changed = True
        return has_changed
        

    def _load_temperature(self, json):
        if 'temperatureSet' in json and json['temperatureSet'] != constants.INVALID_TEMPERATURE:
            self.target_temperature = json['temperatureSet']
        if 'insideTemperature' in json and json['insideTemperature'] != constants.INVALID_TEMPERATURE:
            self.inside_temperature = json['insideTemperature']
        if 'outTemperature' in json and json['outTemperature'] != constants.INVALID_TEMPERATURE:
            self.outside_temperature = json['outTemperature']


    def _load_swing_mode(self, json):
        if 'airSwingLR' in json:
            try:
                self.horizontal_swing_mode = constants.AirSwingLR(json['airSwingLR'])
            except:
                _LOGGER.warning("Invalid horizontal swing mode '%s'", json['airSwingLR'])
        if 'airSwingUD' in json:
            try:
                self.vertical_swing_mode = constants.AirSwingUD(json['airSwingUD'])
            except:
                _LOGGER.warning("Invalid vertical swing mode '%s'", json['airSwingUD'])
        if 'fanAutoMode' in json:
            if json['fanAutoMode'] == constants.AirSwingAutoMode.Both.value:
                self.horizontal_swing_mode = constants.AirSwingLR.Auto
                self.vertical_swing_mode = constants.AirSwingUD.Auto
            elif json['fanAutoMode'] == constants.AirSwingAutoMode.AirSwingLR.value:
                self.horizontal_swing_mode = constants.AirSwingLR.Auto
            elif json['fanAutoMode'] == constants.AirSwingAutoMode.AirSwingUD.value:
                self.vertical_swing_mode = constants.AirSwingUD.Auto

        

class PanasonicDeviceZone:
    def __init__(self, json) -> None:
        if 'zoneId' not in json:
            raise ValueError('Invalid zone json')            

        self._id:int = json['zoneId']
        self._name:str = None
        self._mode = constants.ZoneMode.Off
        self._level = 100
        self._spill = 0
        self._temperature: int = None
        self._has_changed = False
        self.load(json)

    @property
    def id(self):
        return self._id
    
    @property
    def has_changed(self) -> bool:
        return self._has_changed
    
    @property
    def name(self):
        return self._name
    @name.setter
    def name(self, value):
        if self._name == value:
            return
        self._name = value
        self._has_changed = True

    @property
    def mode(self):
        return self._mode
    @mode.setter
    def mode(self, value):
        if self._mode == value:
            return
        self._has_changed = True
        self._mode = value

    @property
    def level(self):
        return self._level
    @level.setter
    def level(self, value):
        if self._level == value:
            return
        self._has_changed = True
        self._level = value

    @property
    def spill(self):
        return self._spill
    @spill.setter
    def spill(self, value):
        if self._spill == value:
            return
        self._has_changed = True
        self._spill = value

    @property
    def temperature(self):
        return self._temperature
    @temperature.setter
    def temperature(self, value):
        if self._temperature == value:
            return
        self._has_changed = True
        self._temperature = value

    def load(self, json) -> bool:
        if not json:
            return False
        self._has_changed = False
        if 'zoneName' in json:
            self.name = json['zoneName']
        self.mode = read_enum(json, 'zoneOnOff', constants.ZoneMode, self.mode)
        if 'zoneLevel' in json:
            self.level = json['zoneLevel']
        if 'zoneSpill' in json:
            self.spill = json['zoneSpill']
        if 'zoneTemperature' in json:
            self.temperature = json['zoneTemperature']
            if self.temperature == -255:
                self.temperature = None
        has_changed = self._has_changed
        self._has_changed = False
        return has_changed

class PanasonicDeviceEnergy:

    def __init__(self, info: PanasonicDeviceInfo, json = None) -> None:
        self._info = info
        self._consumption: float = 0.0
        self._heating_rate: float = 0.0
        self._cooling_rate: float = 0.0
        self._heating_consumption: float = 0.0
        self._cooling_consumption: float = 0.0
        self._last_consumption: float = None
        self._last_consumption_changed: datetime = None
        self._current_power: float = None
        self._has_changed = False
        self.load(json)

    @property
    def id(self)->str:
        return self.info.id
    
    @property
    def info(self) -> PanasonicDeviceInfo:
        return self._info

    @property
    def consumption(self) -> float:
        return self._consumption
    @consumption.setter
    def consumption(self, value):
        now = datetime.now()
        if self._consumption == value:
            if now - self._last_consumption_changed >= timedelta(minutes= 15):
                self._current_power = 0
            return
        self._has_changed = True
        self._last_consumption = self._consumption
        self._consumption = value
        if self._last_consumption_changed is None:
            self._last_consumption_changed = now
        else:
            delta = (now - self._last_consumption_changed).total_seconds() / 3600
            self._last_consumption_changed = now
            energy_diff = value if value < self._last_consumption else value - self._last_consumption
            self._current_power = round((energy_diff*1000)/delta)
            


    @property
    def heating_rate(self) -> float:
        return self._heating_rate
    @heating_rate.setter
    def heating_rate(self, value):
        if self._heating_rate == value:
            return
        self._has_changed = True
        self._heating_rate = value

    @property
    def heating_consumption(self) -> float:
        return self._heating_consumption

    @property
    def cooling_rate(self) -> float:
        return self._cooling_rate
    @cooling_rate.setter
    def cooling_rate(self, value):
        if self._cooling_rate == value:
            return
        self._has_changed = True
        self._cooling_rate = value

    @property
    def cooling_consumption(self) -> float:
        return self._cooling_consumption
    
    @property
    def current_power(self)->float|None:
        return self._current_power

    def load(self, json) -> bool:
        if not json:
            return False
        self._has_changed = False
        if 'consumption' in json and json['consumption'] >= 0:
            self.consumption = json['consumption']
        if 'heatConsumptionRate' in json and json['heatConsumptionRate'] >= 0:
            self.heating_rate = json['heatConsumptionRate']
        if 'coolConsumptionRate' in json and json['coolConsumptionRate'] >= 0:
            self.cooling_rate = json['coolConsumptionRate']

        has_changed = self._has_changed
        if has_changed:
            self._cooling_consumption = self.cooling_rate * self.consumption
            self._heating_consumption = self.heating_rate * self.consumption
        self._has_changed = False
        return has_changed
