"""HTTP session helpers for talking to eedomus (LAN vs cloud)."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EedomusClient

_LOGGER = logging.getLogger(__name__)


def async_eedomus_clientsession(hass: HomeAssistant, host: str):
    """Return the shared HA aiohttp session (SSL verify off for LAN).

    Keep this minimal: exotic ClientSession kwargs have caused opaque
    "Erreur inattendue" failures on some HA builds when targeting a LAN IP.
    """
    local = EedomusClient.is_local_host(host)
    try:
        session = async_get_clientsession(hass, verify_ssl=not local)
    except TypeError:
        session = async_get_clientsession(hass)

    _LOGGER.info(
        "eedomus session host=%s local=%s verify_ssl=%s",
        host,
        local,
        not local,
    )
    return session
