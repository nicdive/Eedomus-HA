"""The eedomus integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .api import EedomusClient
from .const import (
    CONF_API_HOST,
    CONF_API_SECRET,
    CONF_API_USER,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_DEVICES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import EedomusCoordinator

_LOGGER = logging.getLogger(__name__)


def _cleanup_deselected_entities(
    hass: HomeAssistant, entry: ConfigEntry, selected_ids: set[str]
) -> None:
    """Remove entities that are no longer in the user selection."""
    entity_registry = async_get_entity_registry(hass)
    keep_unique_ids = {f"eedomus_{pid}" for pid in selected_ids}
    for entity in list(entity_registry.entities.values()):
        if entity.config_entry_id != entry.entry_id:
            continue
        if entity.unique_id not in keep_unique_ids:
            _LOGGER.info("Removing deselected eedomus entity %s", entity.entity_id)
            entity_registry.async_remove(entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up eedomus from a config entry."""
    host = entry.data.get(CONF_API_HOST) or entry.data.get(CONF_HOST)
    client = EedomusClient(
        session=async_get_clientsession(hass),
        host=host,
        api_user=entry.data[CONF_API_USER],
        api_secret=entry.data[CONF_API_SECRET],
    )

    selected = entry.options.get(CONF_SELECTED_DEVICES) or entry.data.get(
        CONF_SELECTED_DEVICES, []
    )
    selected_ids = {str(i) for i in selected}
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    coordinator = EedomusCoordinator(
        hass=hass,
        client=client,
        selected_ids=list(selected_ids),
        scan_interval=int(scan_interval),
    )
    await coordinator.async_config_entry_first_refresh()
    _cleanup_deselected_entities(hass, entry, selected_ids)

    # Register a bridge device so peripherals can link via_device.
    registry = async_get_device_registry(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "bridge")},
        manufacturer="Connected Object",
        name=f"eedomus ({host})",
        model="eedomus box",
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
