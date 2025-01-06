import random

def inject_zone_data(json):
    if 'zoneParameters' not in json:
        json['zoneParameters']= []
    


    json['zoneParameters'].append({
        "zoneOnOff": 1 if random.random() >= 0.5 else 0,
        "zoneLevel": 100,
        "zoneTemperature": -255,
        "zoneSpill": 0,
        "zoneId": 1,
        "zoneName": "Zone 1"
      })
    json['zoneParameters'].append({
        "zoneOnOff": 1 if random.random() >= 0.5 else 0,
        "zoneLevel": 100,
        "zoneTemperature": 24,
        "zoneSpill": 0,
        "zoneId": 2,
        "zoneName": "Zone 2"
      })
    json['zoneParameters'].append({
        "zoneOnOff": 1 if random.random() >= 0.5 else 0,
        "zoneLevel": 50,
        "zoneTemperature": -255,
        "zoneSpill": 0,
        "zoneId": 3,
        "zoneName": "Zone 3"
      })
def get_dummy_aquarea_device_json():
    return {"deviceGuid": "000007340331", "deviceType": "2", "deviceName": "Demo", "connectionStatus": 0, "operationMode": 1, "zoneStatus": [{"zoneId": 1, "operationStatus": 0, "temperature": 0}, {"zoneId": 2}], "tankStatus": {"operationStatus": 1, "temperature": 50}}

def return_data():
    return {"timestamp":1727898629466,"permission":3,"summerHouse":2,"iAutoX":False,"nanoe":False,"nanoeStandAlone":False,"autoMode":True,"heatMode":True,"fanMode":True,"dryMode":True,"coolMode":True,"ecoNavi":False,"powerfulMode":True,"quietMode":True,"airSwingLR":True,"autoSwingUD":False,"ecoFunction":0,"temperatureUnit":0,"modeAvlList":{"autoMode":1},"nanoeList":{"visualizationShow":0},"clothesDrying":False,"insideCleaning":False,"fireplace":False,"pairedFlg":False,"parameters":{"ecoFunctionData":0,"insideCleaning":0,"fireplace":0,"lastSettingMode":0,"operate":1,"operationMode":0,"temperatureSet":22.5,"fanSpeed":0,"fanAutoMode":0,"airSwingLR":2,"airSwingUD":2,"ecoMode":2,"ecoNavi":0,"nanoe":0,"iAuto":0,"airDirection":1,"insideTemperature":21,"outTemperature":5,"airQuality":0}}