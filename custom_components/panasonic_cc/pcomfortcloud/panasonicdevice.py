import logging

from . import constants

_LOGGER = logging.getLogger(__name__)

class PanasonicDevice:
    def __init__(self, id: str, json = None) -> None:
        self.id = id
        self.features = PanasonicDeviceFeatures(json)
        json_parameters = None
        if (json is not None and 'parameters' in json):
            json_parameters = json['parameters']
        self.parameters = PanasonicDeviceParameters(json_parameters)

class PanasonicDeviceFeatures:
    def __init__(self, json = None) -> None:
        self.permission = 0
        self.summer_house = 0
        self.iAutoX = False
        self.nanoe = False
        self.nanoe_stand_alone = False
        self.auto_mode = False
        self.heat_mode = False
        self.fan_mode = False
        self.dry_mode = False
        self.cool_mode = False
        self.eco_navi = False
        self.powerful_mode = False
        self.quiet_mode = False
        self.air_swing_lr = False
        self.auto_swing_ud = False
        self.eco_eunction = 0
        self.load(json)

    def load(self, json):
        if not json:
            return
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
            self.eco_eunction = json['ecoFunction']
        
class PanasonicDeviceParameters:
    def __init__(self, json = None) -> None:
        self.power = constants.Power.Off
        self.mode = constants.OperationMode.Auto
        self.fan_speed = constants.FanSpeed.Auto
        self.horizontal_swing_mode = constants.AirSwingLR.Mid
        self.vertical_swing_mode = constants.AirSwingUD.Mid
        self.eco_mode = constants.EcoMode.Auto
        self.nanoe_mode = constants.NanoeMode.Unavailable
        self.eco_navi_mode = constants.EcoNaviMode.Off
        self.target_temperature: int = None
        self.inside_temperature: int = None
        self.outside_temperature: int = None
        self.load(json)
        

    def load(self, json):
        if not json:
            return
        if 'operate' in json:
            self.power = constants.Power(json['operate'])
        if 'operationMode' in json:
            self.mode = constants.OperationMode(json['operationMode'])
        if 'fanSpeed' in json:
            self.fan_speed = constants.FanSpeed(json['fanSpeed'])

        self._load_swing_mode(json)
        self._load_temperature(json)

        if 'ecoMode' in json:
            self.eco_mode = constants.EcoMode(json['ecoMode'])
        if 'nanoe' in json:
            self.nanoe_mode = constants.NanoeMode(json['nanoe'])
        if 'ecoNavi' in json:
            self.eco_navi_mode = constants.EcoNaviMode(json['ecoNavi'])

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

        

