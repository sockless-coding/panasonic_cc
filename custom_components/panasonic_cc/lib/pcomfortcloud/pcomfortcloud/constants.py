from enum import Enum

class Power(Enum):
    Off = 0
    On = 1

class OperationMode(Enum):
    Auto = 0
    Dry = 1
    Cool = 2
    Heat = 3
    Fan = 4

class AirSwingUD(Enum):
    Auto = -1
    Up = 0
    UpMid = 3
    Mid = 2
    DownMid = 4
    Down = 1

class AirSwingLR(Enum):
    Auto = -1
    Left = 0
    LeftMid = 4
    Mid = 2
    RightMid = 3
    Right = 1

class EcoMode(Enum):
    Auto = 0
    Powerful = 1
    Quiet = 2

class AirSwingAutoMode(Enum):
    Disabled = 1
    Both = 0
    AirSwingLR = 3
    AirSwingUD = 2

class FanSpeed(Enum):
    Auto = 0
    Low = 1
    LowMid = 2
    Mid = 3
    HighMid = 4
    High = 5

class dataMode(Enum):
    Day = 0
    Week = 1
    Month = 2
    Year = 4

class NanoeMode(Enum):
    Unavailable = 0
    Off = 1
    On = 2
