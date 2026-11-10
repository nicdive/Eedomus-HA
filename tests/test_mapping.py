"""Unit tests for mapping helpers and webhook payload parsing."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "eedomus"


def _stub_homeassistant() -> None:
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []  # mark as package
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.PERCENTAGE = "%"
    ha_const.UnitOfEnergy = types.SimpleNamespace(KILO_WATT_HOUR="kWh")
    ha_const.UnitOfIlluminance = types.SimpleNamespace(LUX="lx")
    ha_const.UnitOfPower = types.SimpleNamespace(WATT="W")
    ha_const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.HomeAssistant = object

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
    ha_components.__path__ = []
    ha_webhook = types.ModuleType("homeassistant.components.webhook")
    ha_webhook.async_register = lambda *args, **kwargs: None
    ha_webhook.async_unregister = lambda *args, **kwargs: None

    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers.__path__ = []
    ha_helpers_network = types.ModuleType("homeassistant.helpers.network")

    def _get_url(*args, **kwargs):
        return "http://192.168.1.10:8123"

    ha_helpers_network.get_url = _get_url

    ha_helpers_update = types.ModuleType("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, hass, logger, *, name, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = {}

        def async_set_updated_data(self, data):
            self.data = data

    class UpdateFailed(Exception):
        pass

    ha_helpers_update.DataUpdateCoordinator = DataUpdateCoordinator
    ha_helpers_update.UpdateFailed = UpdateFailed

    ha_util = types.ModuleType("homeassistant.util")
    ha_util.__path__ = []
    ha_util_dt = types.ModuleType("homeassistant.util.dt")

    class _FakeDateTime:
        def strftime(self, fmt):
            return "2026-03-26 12:00:00"

    ha_util_dt.now = lambda: _FakeDateTime()

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.components"] = ha_components
    sys.modules["homeassistant.components.sensor"] = ha_sensor
    sys.modules["homeassistant.components.webhook"] = ha_webhook
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.network"] = ha_helpers_network
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_helpers_update
    sys.modules["homeassistant.util"] = ha_util
    sys.modules["homeassistant.util.dt"] = ha_util_dt


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

    aiohttp_web = types.ModuleType("aiohttp.web")

    class Request:
        pass

    class Response:
        def __init__(self, text="", status=200):
            self.text = text
            self.status = status

    aiohttp_web.Request = Request
    aiohttp_web.Response = Response
    sys.modules["aiohttp"] = aiohttp
    sys.modules["aiohttp.web"] = aiohttp_web


def _load_module(module_name: str, filename: str):
    path = PKG_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
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
coordinator_mod = _load_module("eedomus.coordinator", "coordinator.py")
helpers = _load_module("eedomus.helpers", "helpers.py")
webhook = _load_module("eedomus.webhook", "webhook.py")

resolve_mapping = mapping.resolve_mapping
peripheral_label = mapping.peripheral_label
coerce_number = mapping.coerce_number
is_on_value = mapping.is_on_value
EedomusClient = api.EedomusClient
EedomusCoordinator = coordinator_mod.EedomusCoordinator
interpret_push_payload = webhook.interpret_push_payload
webhook_url_for_entry = helpers.webhook_url_for_entry


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


class WebhookPayloadTests(unittest.TestCase):
    def test_state_from_query_style(self):
        intent = interpret_push_payload({"periph_id": "42", "value": "100"})
        self.assertEqual(intent["kind"], "state")
        self.assertEqual(intent["periph_id"], "42")
        self.assertEqual(intent["value"], "100")

    def test_state_accepts_periphId_alias(self):
        intent = interpret_push_payload({"periphId": "7", "last_value": 0})
        self.assertEqual(intent["kind"], "state")
        self.assertEqual(intent["periph_id"], "7")
        self.assertEqual(intent["value"], 0)

    def test_refresh_action(self):
        intent = interpret_push_payload({"action": "refresh"})
        self.assertEqual(intent["kind"], "refresh")
        self.assertIsNone(intent["periph_id"])

    def test_refresh_single_periph(self):
        intent = interpret_push_payload({"action": "partial_refresh", "periph_id": "9"})
        self.assertEqual(intent["kind"], "refresh")
        self.assertEqual(intent["periph_id"], "9")

    def test_empty_payload_is_ping(self):
        intent = interpret_push_payload({})
        self.assertEqual(intent["kind"], "empty")

    def test_webhook_url(self):
        url = webhook_url_for_entry(MagicMock(), "abc123")
        self.assertEqual(url, "http://192.168.1.10:8123/api/webhook/abc123")


class CoordinatorPushTests(unittest.TestCase):
    def test_apply_state_update_selected(self):
        hass = MagicMock()
        client = MagicMock()
        coord = EedomusCoordinator(hass, client, ["42"], scan_interval=0)
        coord.data = {
            "42": {"periph_id": "42", "name": "PIR", "last_value": "0"},
        }
        coord.peripherals = dict(coord.data)

        ok = coord.apply_state_update("42", "100", last_value_text="Mouvement")
        self.assertTrue(ok)
        self.assertEqual(coord.data["42"]["last_value"], "100")
        self.assertEqual(coord.data["42"]["last_value_text"], "Mouvement")

    def test_apply_state_update_ignores_unselected(self):
        hass = MagicMock()
        client = MagicMock()
        coord = EedomusCoordinator(hass, client, ["42"], scan_interval=0)
        coord.data = {}
        ok = coord.apply_state_update("99", "1")
        self.assertFalse(ok)

    def test_webhook_only_disables_interval(self):
        hass = MagicMock()
        client = MagicMock()
        coord = EedomusCoordinator(hass, client, ["1"], scan_interval=0)
        self.assertIsNone(coord.update_interval)


if __name__ == "__main__":
    unittest.main()
