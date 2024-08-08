
from .panasonicdevice import PanasonicDevice
from . import constants

class ChangeRequestBuilder:

    def __init__(self, device: PanasonicDevice):
        self._request = {}
        self._device = device

    @property
    def has_changes(self) -> bool:
        """ Check if there are any changes to be made """
        return len(self._request)!= 0

    def build(self) -> dict:
        return self._request
    
    @property
    def eco_mode(self) -> constants.EcoMode | None:
        return constants.EcoMode(self._request["ecoMode"]) if "ecoMode" in self._request else None
    
    def set_eco_mode(self, new_value: str | constants.EcoMode):
        """ Set eco mode """
        if isinstance(new_value, str):
            new_value = constants.EcoMode[new_value]
        self._ensure_powered_on()
        self._request["ecoMode"] = new_value.value
        return self

    @property
    def target_temperature(self) -> int | None:
        return self._request["temperatureSet"] if "temperatureSet" in self._request else None
    
    def set_target_temperature(self, new_value: int):
        """ Set target temperature """
        self._ensure_powered_on()
        self._request["temperatureSet"] = new_value
        return self
    
    @property
    def fan_speed(self) -> constants.FanSpeed | None:
        return constants.FanSpeed(self._request["fanSpeed"]) if "fanSpeed" in self._request else None
    
    def set_fan_speed(self, new_value: str | constants.FanSpeed):
        """ Set fan speed """
        if isinstance(new_value, str):
            new_value = constants.FanSpeed[new_value]
        self._ensure_powered_on()
        self._request["fanSpeed"] = new_value.value
        return self

    @property
    def hvac_mode(self) -> constants.OperationMode | None:
        return constants.OperationMode(self._request["operationMode"]) if "operationMode" in self._request else None

    def set_hvac_mode(self, new_value: str | constants.OperationMode):
        """ Set hvac mode"""
        if isinstance(new_value, str):
            new_value = constants.OperationMode[new_value]
        self._ensure_powered_on()
        self._request["operationMode"] = new_value.value
        return self

    @property
    def horizontal_swing(self) -> constants.AirSwingLR | None:
        if "airSwingLR" not in self._request:
            return None
        if self._request["fanAutoMode"] in (constants.AirSwingAutoMode.Both.value, constants.AirSwingAutoMode.AirSwingLR.value):
            return constants.AirSwingLR.Auto
        return constants.AirSwingAutoMode(self._request["airSwingLR"])
    
    def set_horizontal_swing(self, new_value: str | constants.AirSwingLR):
        """ Set horizontal swing"""
        if isinstance(new_value, str):
            new_value = constants.AirSwingLR[new_value]
        fan_auto = (constants.AirSwingAutoMode.AirSwingLR 
                    if new_value == constants.AirSwingLR.Auto 
                    else constants.AirSwingAutoMode.Disabled)
        if self._device.parameters.vertical_swing_mode == constants.AirSwingUD.Auto:
            fan_auto = (constants.AirSwingAutoMode.Both 
                        if new_value == constants.AirSwingLR.Auto 
                        else constants.AirSwingAutoMode.AirSwingUD)
        self._ensure_powered_on()
        if new_value != constants.AirSwingLR.Auto:
            self._request["airSwingLR"] = new_value.value
        self._request["fanAutoMode"] = fan_auto.value
        return self
    
    @property
    def vertical_swing(self) -> constants.AirSwingUD | None:
        if "airSwingUD" not in self._request:
            return None
        if self._request["fanAutoMode"] in (constants.AirSwingAutoMode.Both.value, constants.AirSwingAutoMode.AirSwingUD.value):
            return constants.AirSwingUD.Auto
        return constants.AirSwingUD(self._request["airSwingUD"])
    
    def set_vertical_swing(self, new_value: str | constants.AirSwingUD):
        """ Set vertical swing"""
        if isinstance(new_value, str):
            new_value = constants.AirSwingUD[new_value]
        fan_auto = (constants.AirSwingAutoMode.AirSwingUD 
                    if new_value == constants.AirSwingUD.Auto 
                    else constants.AirSwingAutoMode.Disabled)
        if self._device.parameters.horizontal_swing_mode == constants.AirSwingLR.Auto:
            fan_auto = (constants.AirSwingAutoMode.Both 
                        if new_value == constants.AirSwingUD.Auto 
                        else constants.AirSwingAutoMode.AirSwingLR)
        self._ensure_powered_on()
        if new_value != constants.AirSwingUD.Auto:
            self._request["airSwingUD"] = new_value.value
        self._request["fanAutoMode"] = fan_auto.value
        return self
    
    @property
    def nanoe_mode(self) -> constants.NanoeMode | None:
        return constants.NanoeMode(self._request["nanoeMode"]) if "nanoe" in self._request else None
    
    def set_nanoe_mode(self, new_value: str | constants.NanoeMode):
        """ Set Nanoe mode"""
        if isinstance(new_value, str):
            new_value = constants.NanoeMode[new_value]
        self._request["nanoe"] = new_value.value
        return self
        
    @property
    def eco_navi_mode(self) -> constants.EcoNaviMode | None:
        return constants.EcoNaviMode(self._request["ecoNavi"]) if "ecoNavi" in self._request else None
    
    def set_eco_navi_mode(self, new_value: str | constants.EcoNaviMode):
        """ Set EcoNavi mode"""
        if isinstance(new_value, str):
            new_value = constants.EcoNaviMode[new_value]
        self._request["ecoNavi"] = new_value.value
        return self
        
    @property
    def eco_function_mode(self) -> constants.EcoFunctionMode | None:
        return constants.EcoFunctionMode(self._request["ecoFunctionData"]) if "ecoFunctionData" in self._request else None
    
    def set_eco_function_mode(self, new_value: str | constants.EcoFunctionMode):
        """ Set EcoFunction mode"""
        if isinstance(new_value, str):
            new_value = constants.EcoFunctionMode[new_value]
        self._request["ecoFunctionData"] = new_value.value
        return self
    
    @property
    def power_mode(self) -> constants.Power | None:
        return constants.Power(self._request["operate"]) if "operate" in self._request else None
    
    def set_power_mode(self, new_value: str | constants.Power):
        """ Set Power mode"""
        if isinstance(new_value, str):
            new_value = constants.Power[new_value]
        self._request["operate"] = new_value.value
        return self
    
    def set_zone_mode(self, zone_id: int, new_value: str | constants.ZoneMode):
        """ Set Zone mode"""
        if isinstance(new_value, str):
            new_value = constants.ZoneMode[new_value]
        zone_parameters = self._ensure_zone(new_value)
        zone_parameters["zoneOnOff"] = new_value.value
        return self
    
    def set_zone_damper(self, zone_id: int, new_value: int):
        """ Set Zone damper"""
        zone_parameters = self._ensure_zone(new_value)
        zone_parameters["zoneLevel"] = new_value
        return self

    def _ensure_zone(self, zone_id: int):
        if "zoneParameters" not in self._request:
            self._request["zoneParameters"] = []
        zone_parameters = None
        for zone in self._request["zoneParameters"]:
            if zone["zoneId"] == zone_id:
                zone_parameters = zone
                break
        if zone_parameters == None:
            zone_parameters = { "zoneId": zone_id }
            self._request["zoneParameters"].append(zone_parameters)
        return zone_parameters
    
    def _ensure_powered_on(self) -> None:
        """ Ensure that the device is powered on"""
        if self._device.parameters.power == constants.Power.On:
            return
        self._request["operate"] = constants.Power.On.value
        

    