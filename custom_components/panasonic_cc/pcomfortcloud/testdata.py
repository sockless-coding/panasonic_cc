
def inject_zone_data(json):
    if 'zoneParameters' not in json:
        json['zoneParameters']= []
    json['zoneParameters'].append({
        "zoneOnOff": 0,
        "zoneLevel": 100,
        "zoneTemperature": -255,
        "zoneSpill": 0,
        "zoneId": 1,
        "zoneName": "Zone 1"
      })
    json['zoneParameters'].append({
        "zoneOnOff": 1,
        "zoneLevel": 100,
        "zoneTemperature": 24,
        "zoneSpill": 0,
        "zoneId": 2,
        "zoneName": "Zone 2"
      })
    json['zoneParameters'].append({
        "zoneOnOff": 1,
        "zoneLevel": 50,
        "zoneTemperature": -255,
        "zoneSpill": 0,
        "zoneId": 3,
        "zoneName": "Zone 3"
      })