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
        mapping = resolve_mapping(self.periph_data)
        self._attr_device_class = mapping.get("device_class")
        self._attr_native_unit_of_measurement = mapping.get("unit")
        self._attr_state_class = mapping.get("state_class")

    @property
    def native_value(self):
        data = self.periph_data
        value = data.get("last_value")
        if value in (None, "") and data.get("last_value_text") not in (None, ""):
            return data.get("last_value_text")
        return coerce_number(value)
