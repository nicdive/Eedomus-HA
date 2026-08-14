"""Constants for the eedomus integration."""

from __future__ import annotations

from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfIlluminance,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

DOMAIN = "eedomus"
PLATFORMS = ["sensor", "binary_sensor", "switch", "light", "cover"]

CONF_API_HOST = "api_host"
CONF_API_USER = "api_user"
CONF_API_SECRET = "api_secret"
CONF_SELECTED_DEVICES = "selected_devices"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_API_HOST = "api.eedomus.com"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 900

ATTR_PERIPH_ID = "periph_id"
ATTR_USAGE_ID = "usage_id"
ATTR_USAGE_NAME = "usage_name"
ATTR_ROOM_NAME = "room_name"
ATTR_LAST_VALUE_TEXT = "last_value_text"
ATTR_VALUE_TYPE = "value_type"

# usage_id -> Home Assistant platform + metadata
# Based on eedomus API usage identifiers and common mappings.
USAGE_MAPPING: dict[str, dict] = {
    "1": {"platform": "light", "dimmable": True},
    "2": {"platform": "switch"},
    "4": {"platform": "switch"},
    "7": {
        "platform": "sensor",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "22": {
        "platform": "sensor",
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "24": {
        "platform": "sensor",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "unit": UnitOfIlluminance.LUX,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "26": {
        "platform": "sensor",
        "device_class": SensorDeviceClass.ENERGY,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "27": {"platform": "binary_sensor", "device_class": "smoke"},
    "28": {
        "platform": "sensor",
        "device_class": SensorDeviceClass.POWER,
        "unit": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "29": {
        "platform": "sensor",
        "device_class": SensorDeviceClass.ENERGY,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "36": {"platform": "binary_sensor", "device_class": "moisture"},
    "37": {"platform": "binary_sensor", "device_class": "motion"},
    "48": {"platform": "cover"},
    "50": {"platform": "switch"},
    "52": {"platform": "switch"},
}

# Keyword fallbacks when usage_id is unknown (matched against usage_name / name).
NAME_HINTS: list[tuple[tuple[str, ...], dict]] = [
    (("temp", "thermom"), USAGE_MAPPING["7"]),
    (("humid", "hygro"), USAGE_MAPPING["22"]),
    (("lumin", "lux", "éclair", "eclair"), USAGE_MAPPING["24"]),
    (("mouvement", "motion", "présence", "presence", "pir"), USAGE_MAPPING["37"]),
    (("fumée", "fumee", "smoke"), USAGE_MAPPING["27"]),
    (("inond", "fuite", "flood", "leak"), USAGE_MAPPING["36"]),
    (("volet", "store", "shutter", "blind", "rideau"), USAGE_MAPPING["48"]),
    (("lampe", "light", "éclairage", "eclairage", "dimmer"), USAGE_MAPPING["1"]),
    (("prise", "switch", "relais", "on/off", "onoff"), USAGE_MAPPING["2"]),
    (("puissance", "watt", "power"), USAGE_MAPPING["28"]),
    (("conso", "énergie", "energie", "kwh", "energy"), USAGE_MAPPING["29"]),
    (("ouverture", "porte", "fenêtre", "fenetre", "contact", "door", "window"), {
        "platform": "binary_sensor",
        "device_class": "opening",
    }),
]
