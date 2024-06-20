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
    Swing = 5


class AirSwingLR(Enum):
    Auto = -1
    Left = 1
    LeftMid = 5
    Mid = 2
    RightMid = 4
    Right = 0


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


class DataMode(Enum):
    Day = 0
    Week = 1
    Month = 2
    Year = 4


class NanoeMode(Enum):
    Unavailable = 0
    Off = 1
    On = 2
    ModeG = 3
    All = 4

DEFAULT_X_APP_VERSION = "1.20.0"

MAX_VERSION_AGE = 5

SETTING_ACCESS_TOKEN = "access_token"
SETTING_ACCESS_TOKEN_EXPIRES = "access_token_expires"
SETTING_REFRESH_TOKEN = "refresh_token"
SETTING_SCOPE = "scope"
SETTING_VERSION = "android_version"
SETTING_VERSION_DATE = "android_version_date"
SETTING_CLIENT_ID = "clientId"