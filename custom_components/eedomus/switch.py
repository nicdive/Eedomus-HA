"""Switch platform for eedomus."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EedomusCoordinator
from .entity import EedomusEntity
from .mapping import is_on_value, resolve_mapping


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EedomusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        EedomusSwitch(coordinator, periph_id)
        for periph_id, data in coordinator.data.items()
        if resolve_mapping(data).get("platform") == "switch"
    ]
    async_add_entities(entities)


class EedomusSwitch(EedomusEntity, SwitchEntity):
    """On/off actuator."""

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.async_set_value(self.periph_id, 100)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.async_set_value(self.periph_id, 0)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        return is_on_value(self.periph_data.get("last_value"))
