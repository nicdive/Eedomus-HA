"""Unit tests for mapping helpers (no Home Assistant runtime required)."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "eedomus"


def _stub_homeassistant() -> None:
    ha = types.ModuleType("homeassistant")
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.PERCENTAGE = "%"
    ha_const.UnitOfEnergy = types.SimpleNamespace(KILO_WATT_HOUR="kWh")
    ha_const.UnitOfIlluminance = types.SimpleNamespace(LUX="lx")
    ha_const.UnitOfPower = types.SimpleNamespace(WATT="W")
    ha_const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")

    ha_sensor = types.ModuleType("homeassistant.components.sensor")
    ha_sensor.SensorDeviceClass = types.SimpleNamespace(
        TEMPERATURE="temperature",
        HUMIDITY="humidity",
        ILLUMINANCE="illuminance",
        ENERGY="energy",
        POWER="power",
    )
    ha_sensor.SensorStateClass = types.SimpleNamespace(
        MEASUREMENT="measurement",
        TOTAL_INCREASING="total_increasing",
    )

    ha_components = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.components"] = ha_components
    sys.modules["homeassistant.components.sensor"] = ha_sensor


def _stub_aiohttp() -> None:
    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class ClientTimeout:
        def __init__(self, total=None):
            self.total = total

    class ClientSession:
        pass

    aiohttp.ClientError = ClientError
    aiohttp.ClientTimeout = ClientTimeout
    aiohttp.ClientSession = ClientSession
    sys.modules["aiohttp"] = aiohttp


def _load_module(fullname_name: str, filename: str):
    path = PKG_DIR / filename
    spec = importlib.util.spec_from_file_location(fullname_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_stub_homeassistant()
_stub_aiohttp()

# Minimal package shell so relative imports in mapping/api work.
eedomus_pkg = types.ModuleType("eedomus")
eedomus_pkg.__path__ = [str(PKG_DIR)]
sys.modules["eedomus"] = eedomus_pkg

_load_module("eedomus.const", "const.py")
mapping = _load_module("eedomus.mapping", "mapping.py")
api = _load_module("eedomus.api", "api.py")

resolve_mapping = mapping.resolve_mapping
peripheral_label = mapping.peripheral_label
coerce_number = mapping.coerce_number
is_on_value = mapping.is_on_value
EedomusClient = api.EedomusClient


class MappingTests(unittest.TestCase):
    def test_usage_temperature(self):
        result = resolve_mapping({"usage_id": "7", "name": "Salon"})
        self.assertEqual(result["platform"], "sensor")
        self.assertEqual(result["device_class"], "temperature")

    def test_usage_light(self):
        result = resolve_mapping({"usage_id": "1"})
        self.assertEqual(result["platform"], "light")
        self.assertTrue(result.get("dimmable"))

    def test_name_hint_humidity(self):
        result = resolve_mapping(
            {"usage_id": "9999", "usage_name": "Humidité", "name": "SDB"}
        )
        self.assertEqual(result["platform"], "sensor")
        self.assertEqual(result["device_class"], "humidity")

    def test_name_hint_shutter(self):
        result = resolve_mapping(
            {"usage_id": "9999", "name": "Volet salon", "usage_name": "Autre"}
        )
        self.assertEqual(result["platform"], "cover")

    def test_label_contains_id(self):
        label = peripheral_label(
            {
                "periph_id": "123",
                "name": "Temp Cuisine",
                "room_name": "Cuisine",
                "usage_id": "7",
                "usage_name": "Température",
            }
        )
        self.assertIn("#123", label)
        self.assertIn("Cuisine", label)
        self.assertIn("[sensor]", label)

    def test_coerce_number(self):
        self.assertEqual(coerce_number("21,5"), 21.5)
        self.assertEqual(coerce_number("10"), 10)
        self.assertEqual(coerce_number("abc"), "abc")
        self.assertIsNone(coerce_number(""))

    def test_is_on_value(self):
        self.assertTrue(is_on_value(100))
        self.assertTrue(is_on_value("on"))
        self.assertFalse(is_on_value(0))
        self.assertFalse(is_on_value("off"))


class ApiHostTests(unittest.TestCase):
    def test_cloud_host(self):
        base = EedomusClient._normalize_base("api.eedomus.com")
        self.assertEqual(base, "https://api.eedomus.com")

    def test_local_ip(self):
        base = EedomusClient._normalize_base("192.168.1.50")
        self.assertEqual(base, "http://192.168.1.50/api")

    def test_local_with_scheme(self):
        base = EedomusClient._normalize_base("http://192.168.1.50")
        self.assertEqual(base, "http://192.168.1.50/api")


if __name__ == "__main__":
    unittest.main()
