"""Binary sensor platform for eedomus."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EedomusCoordinator
from .entity import EedomusEntity
from .mapping import is_on_value, resolve_mapping
from .values import extract_last_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EedomusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        EedomusBinarySensor(coordinator, periph_id)
        for periph_id, data in coordinator.data.items()
        if resolve_mapping(data).get("platform") == "binary_sensor"
    ]
    async_add_entities(entities)


class EedomusBinarySensor(EedomusEntity, BinarySensorEntity):
    """Binary eedomus peripheral (motion, smoke, contact…)."""

    def __init__(self, coordinator: EedomusCoordinator, periph_id: str) -> None:
        super().__init__(coordinator, periph_id)
        mapping = resolve_mapping(self.periph_data)
        self._attr_device_class = mapping.get("device_class")

    @property
    def is_on(self) -> bool:
        return is_on_value(extract_last_value(self.periph_data))
