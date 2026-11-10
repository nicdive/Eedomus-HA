"""Small helpers shared without pulling heavy HA components at import time."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


def webhook_url_for_entry(hass: HomeAssistant, webhook_id: str) -> str:
    """Build a LAN-friendly webhook URL for the eedomus HTTP actuator."""
    try:
        from homeassistant.helpers.network import get_url

        base = get_url(
            hass,
            prefer_external=False,
            allow_cloud=False,
            allow_external=False,
        )
    except Exception:  # noqa: BLE001 — network helpers raise several types
        base = "http://HOME_ASSISTANT_IP:8123"
    return f"{base.rstrip('/')}/api/webhook/{webhook_id}"
