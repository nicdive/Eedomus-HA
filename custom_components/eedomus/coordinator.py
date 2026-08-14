"""DataUpdateCoordinator for eedomus."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EedomusApiError, EedomusClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class EedomusCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll selected eedomus peripherals."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EedomusClient,
        selected_ids: list[str],
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.selected_ids = {str(i) for i in selected_ids}
        self.peripherals: dict[str, dict[str, Any]] = {}

    def set_selected_ids(self, selected_ids: list[str]) -> None:
        """Update the selection used by the next refresh."""
        self.selected_ids = {str(i) for i in selected_ids}

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
