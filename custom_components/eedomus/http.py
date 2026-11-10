"""HTTP session helpers for talking to eedomus (LAN vs cloud)."""

from __future__ import annotations

import logging
import socket
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)

from .api import EedomusClient

_LOGGER = logging.getLogger(__name__)


def async_eedomus_clientsession(hass: HomeAssistant, host: str):
    """Return an aiohttp session suited to the target host.

    For LAN boxes we force IPv4 and disable SSL verify / env proxy, which are
    common reasons HA reaches api.eedomus.com but not a raw 192.168.x.x IP.
    """
    local = EedomusClient.is_local_host(host)
    kwargs: dict[str, Any] = {"verify_ssl": not local}
    if local:
        kwargs["family"] = socket.AF_INET
        # Avoid HTTP(S)_PROXY from the HA environment hijacking LAN calls.
        kwargs["trust_env"] = False

    try:
        if local:
            session = async_create_clientsession(hass, **kwargs)
        else:
            session = async_get_clientsession(hass, verify_ssl=True)
    except TypeError:
        # Older HA builds may not accept family/trust_env.
        _LOGGER.debug("Falling back to default clientsession for host %s", host)
        try:
            session = async_get_clientsession(hass, verify_ssl=not local)
        except TypeError:
            session = async_get_clientsession(hass)

    _LOGGER.debug(
        "eedomus HTTP session host=%s local=%s verify_ssl=%s",
        host,
        local,
        not local,
    )
    return session
