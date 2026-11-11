"""Sensor platform for eedomus."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EedomusCoordinator
from .entity import EedomusEntity
from .mapping import coerce_number, resolve_mapping
from .values import extract_last_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EedomusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        EedomusSensor(coordinator, periph_id)
        for periph_id, data in coordinator.data.items()
        if resolve_mapping(data).get("platform") == "sensor"
    ]
    async_add_entities(entities)


class EedomusSensor(EedomusEntity, SensorEntity):
    """Read-only eedomus peripheral as a sensor."""

    def __init__(self, coordinator: EedomusCoordinator, periph_id: str) -> None:
        super().__init__(coordinator, periph_id)

    def _mapping(self) -> dict:
        return resolve_mapping(self.periph_data)

    @property
    def device_class(self):
        return self._mapping().get("device_class")

    @property
    def native_unit_of_measurement(self):
        return self._mapping().get("unit")

    @property
    def state_class(self):
        return self._mapping().get("state_class")

    @property
    def native_value(self):
        data = self.periph_data
        value = extract_last_value(data)
        if value is None and data.get("last_value_text") not in (None, ""):
            return data.get("last_value_text")
        number = coerce_number(value)
        # Keep 0 as a real state (fin de cycle / idle) — never collapse to None.
        return number
