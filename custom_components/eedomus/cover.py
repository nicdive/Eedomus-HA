"""Cover platform for eedomus (shutters / blinds)."""

from __future__ import annotations

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
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
        EedomusCover(coordinator, periph_id)
        for periph_id, data in coordinator.data.items()
        if resolve_mapping(data).get("platform") == "cover"
    ]
    async_add_entities(entities)


class EedomusCover(EedomusEntity, CoverEntity):
    """Shutter / blind controlled by percentage (0 closed → 100 open)."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )

    @property
    def current_cover_position(self) -> int | None:
        value = coerce_number(self.periph_data.get("last_value"))
        if value is None or isinstance(value, str):
            return None
        return max(0, min(100, int(round(float(value)))))

    @property
    def is_closed(self) -> bool | None:
        position = self.current_cover_position
        if position is None:
            return None
        return position == 0

    async def async_open_cover(self, **kwargs) -> None:
        await self.coordinator.client.async_set_value(self.periph_id, 100)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs) -> None:
        await self.coordinator.client.async_set_value(self.periph_id, 0)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs) -> None:
        position = int(kwargs.get("position", 0))
        await self.coordinator.client.async_set_value(self.periph_id, position)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs) -> None:
        # Many eedomus shutter modules accept an intermediate / stop value.
        await self.coordinator.client.async_set_value(self.periph_id, "STOP")
        await self.coordinator.async_request_refresh()
