"""Base entity for eedomus peripherals."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_LAST_VALUE_TEXT,
    ATTR_PERIPH_ID,
    ATTR_ROOM_NAME,
    ATTR_USAGE_ID,
    ATTR_USAGE_NAME,
    ATTR_VALUE_TYPE,
    DOMAIN,
)
from .coordinator import EedomusCoordinator


class EedomusEntity(CoordinatorEntity[EedomusCoordinator]):
    """Common bits for all eedomus entities."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: EedomusCoordinator, periph_id: str) -> None:
        super().__init__(coordinator)
        self.periph_id = str(periph_id)
        self._attr_unique_id = f"eedomus_{self.periph_id}"
        data = self.periph_data
        name = data.get("name") or f"eedomus {self.periph_id}"
        self._attr_name = str(name)
        room = str(data.get("room_name") or "").strip()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.periph_id)},
            name=str(name),
            manufacturer="eedomus",
            model=str(data.get("usage_name") or "Peripheral"),
            suggested_area=room or None,
            via_device=(DOMAIN, "bridge"),
        )

    @property
    def periph_data(self) -> dict[str, Any]:
        """Latest peripheral payload."""
        return self.coordinator.data.get(self.periph_id) or self.coordinator.peripherals.get(
            self.periph_id, {}
        )

    @property
    def available(self) -> bool:
        return super().available and self.periph_id in (self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.periph_data
        attrs: dict[str, Any] = {
            ATTR_PERIPH_ID: self.periph_id,
            ATTR_USAGE_ID: data.get("usage_id"),
            ATTR_USAGE_NAME: data.get("usage_name"),
            ATTR_ROOM_NAME: data.get("room_name"),
            ATTR_VALUE_TYPE: data.get("value_type"),
        }
        if data.get("last_value_text") not in (None, ""):
            attrs[ATTR_LAST_VALUE_TEXT] = data.get("last_value_text")
        if data.get("last_value_change"):
            attrs["last_value_change"] = data.get("last_value_change")
        if data.get("battery") not in (None, ""):
            attrs["battery"] = data.get("battery")
        return {k: v for k, v in attrs.items() if v is not None}
