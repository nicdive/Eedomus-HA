"""Light platform for eedomus."""

from __future__ import annotations

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EedomusCoordinator
from .entity import EedomusEntity
from .mapping import coerce_number, is_on_value, resolve_mapping


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EedomusCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        EedomusLight(coordinator, periph_id)
        for periph_id, data in coordinator.data.items()
        if resolve_mapping(data).get("platform") == "light"
    ]
    async_add_entities(entities)


class EedomusLight(EedomusEntity, LightEntity):
    """Dimmable / on-off light."""

    def __init__(self, coordinator: EedomusCoordinator, periph_id: str) -> None:
        super().__init__(coordinator, periph_id)
        mapping = resolve_mapping(self.periph_data)
        if mapping.get("dimmable"):
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        return is_on_value(self.periph_data.get("last_value"))

    @property
    def brightness(self) -> int | None:
        if ColorMode.BRIGHTNESS not in (self._attr_supported_color_modes or set()):
            return None
        value = coerce_number(self.periph_data.get("last_value"))
        if value is None or isinstance(value, str):
            return None
        # eedomus dimmers are typically 0–100.
        return max(0, min(255, int(round(float(value) * 2.55))))

    async def async_turn_on(self, **kwargs) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            percent = int(round(kwargs[ATTR_BRIGHTNESS] / 2.55))
            percent = max(1, min(100, percent))
            await self.coordinator.client.async_set_value(self.periph_id, percent)
        else:
            await self.coordinator.client.async_set_value(self.periph_id, 100)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.async_set_value(self.periph_id, 0)
        await self.coordinator.async_request_refresh()
