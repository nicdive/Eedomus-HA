"""DataUpdateCoordinator for eedomus."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EedomusApiError, EedomusClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EedomusCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll selected eedomus peripherals and accept instant push updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EedomusClient,
        selected_ids: list[str],
        scan_interval: int,
    ) -> None:
        interval = timedelta(seconds=scan_interval) if scan_interval > 0 else None
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )
        self.client = client
        self.selected_ids = {str(i) for i in selected_ids}
        self.peripherals: dict[str, dict[str, Any]] = {}
        self.webhook_id: str | None = None

    def set_selected_ids(self, selected_ids: list[str]) -> None:
        """Update the selection used by the next refresh."""
        self.selected_ids = {str(i) for i in selected_ids}

    def apply_state_update(
        self,
        periph_id: str | int,
        value: Any,
        **extras: Any,
    ) -> bool:
        """Apply an instant state change from webhook / optimistic command.

        Returns False if the peripheral is not in the user selection.
        """
        pid = str(periph_id)
        if pid not in self.selected_ids:
            return False

        current = dict(
            (self.data or {}).get(pid)
            or self.peripherals.get(pid)
            or {"periph_id": pid}
        )
        current["last_value"] = value
        current["last_value_change"] = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
        for key, extra_value in extras.items():
            if extra_value is not None:
                current[key] = extra_value

        merged = dict(self.data or self.peripherals)
        merged[pid] = current
        self.peripherals = merged
        self.async_set_updated_data(merged)
        return True

    async def async_set_value(
        self,
        periph_id: str | int,
        value: str | int | float,
        *,
        optimistic: bool = True,
    ) -> None:
        """Send a command to eedomus and optionally update HA state immediately."""
        pid = str(periph_id)
        await self.client.async_set_value(pid, value)
        if optimistic:
            self.apply_state_update(pid, value)
        # Verify against the box shortly after (RF / Z-Wave ack latency).
        self.hass.async_create_task(self.async_refresh_periph(pid))

    async def async_refresh_periph(self, periph_id: str | int) -> None:
        """Refresh a single selected peripheral from the eedomus API."""
        pid = str(periph_id)
        if pid not in self.selected_ids:
            return
        try:
            caract = await self.client.async_get_caract(pid)
        except EedomusApiError as err:
            _LOGGER.warning("Could not refresh periph %s: %s", pid, err)
            return

        current = dict(
            (self.data or {}).get(pid)
            or self.peripherals.get(pid)
            or {"periph_id": pid}
        )
        current.update(caract)
        current["periph_id"] = pid
        merged = dict(self.data or self.peripherals)
        merged[pid] = current
        self.peripherals = merged
        self.async_set_updated_data(merged)

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            peripherals = await self.client.async_get_peripherals()
        except EedomusApiError as err:
            raise UpdateFailed(str(err)) from err

        by_id: dict[str, dict[str, Any]] = {}
        for periph in peripherals:
            periph_id = str(periph.get("periph_id") or "")
            if not periph_id or periph_id not in self.selected_ids:
                continue
            by_id[periph_id] = dict(periph)

        # Enrich devices missing last_value (typical for cloud periph.list).
        missing = [
            pid
            for pid, data in by_id.items()
            if "last_value" not in data or data.get("last_value") in (None, "")
        ]
        if missing:
            results = await asyncio.gather(
                *(self.client.async_get_caract(pid) for pid in missing),
                return_exceptions=True,
            )
            for pid, result in zip(missing, results):
                if isinstance(result, Exception):
                    _LOGGER.warning("Could not refresh periph %s: %s", pid, result)
                    continue
                by_id[pid] = {**by_id[pid], **result}

        self.peripherals = by_id
        return by_id
