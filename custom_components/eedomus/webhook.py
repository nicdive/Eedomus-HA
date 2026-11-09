"""Push webhook receiver for instant eedomus → Home Assistant updates."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp.web import Request, Response
from homeassistant.components import webhook as ha_webhook
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import DOMAIN
from .coordinator import EedomusCoordinator

_LOGGER = logging.getLogger(__name__)

WEBHOOK_NAME = "eedomus push"


def webhook_url_for_entry(hass: HomeAssistant, webhook_id: str) -> str:
    """Build a LAN-friendly webhook URL for the eedomus HTTP actuator."""
    try:
        base = get_url(
            hass,
            prefer_external=False,
            allow_cloud=False,
            allow_external=False,
        )
    except Exception:  # noqa: BLE001 — network helpers raise several types
        base = "http://HOME_ASSISTANT_IP:8123"
    return f"{base.rstrip('/')}/api/webhook/{webhook_id}"


def async_register_webhook(
    hass: HomeAssistant,
    entry_id: str,
    webhook_id: str,
) -> None:
    """Register the Home Assistant webhook endpoint for one config entry."""
    ha_webhook.async_register(
        hass,
        DOMAIN,
        WEBHOOK_NAME,
        webhook_id,
        _make_handler(entry_id),
        local_only=True,
        allowed_methods=["GET", "POST", "PUT"],
    )


def async_unregister_webhook(hass: HomeAssistant, webhook_id: str) -> None:
    """Unregister a previously registered webhook."""
    ha_webhook.async_unregister(hass, webhook_id)


def interpret_push_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw webhook payload into a structured push intent.

    Returned keys:
      kind: "refresh" | "reload" | "state" | "empty"
      periph_id, value, extras (for state)
    """
    action = str(payload.get("action") or "").strip().lower()
    periph_id = _first_str(
        payload,
        ("periph_id", "periphid", "periphId", "id", "device_id"),
    )

    if action in {"refresh", "full_refresh", "partial_refresh"}:
        return {"kind": "refresh", "periph_id": periph_id}

    if action == "reload":
        return {"kind": "reload"}

    value = _first_present(
        payload,
        ("value", "last_value", "val", "state"),
    )
    if periph_id and value is not None:
        extras: dict[str, Any] = {}
        text = _first_present(
            payload,
            ("last_value_text", "value_text", "text", "description"),
        )
        if text is not None:
            extras["last_value_text"] = text
        battery = _first_present(payload, ("battery",))
        if battery is not None:
            extras["battery"] = battery
        return {
            "kind": "state",
            "periph_id": periph_id,
            "value": value,
            "extras": extras,
        }

    if not payload or action in {"", "ping"}:
        return {"kind": "empty"}

    return {"kind": "unknown", "payload": payload}


def _make_handler(entry_id: str):
    async def _handle_webhook(
        hass: HomeAssistant,
        webhook_id: str,
        request: Request,
    ) -> Response:
        coordinator = _coordinator_for_entry(hass, entry_id)
        if coordinator is None:
            _LOGGER.warning("Webhook %s: coordinator missing for %s", webhook_id, entry_id)
            return Response(text="Coordinator unavailable", status=503)

        payload = await _extract_payload(request)
        _LOGGER.debug("eedomus webhook payload: %s", payload)
        intent = interpret_push_payload(payload)
        kind = intent["kind"]

        if kind == "refresh":
            periph_id = intent.get("periph_id")
            if periph_id:
                await coordinator.async_refresh_periph(periph_id)
            else:
                await coordinator.async_request_refresh()
            return Response(text="OK")

        if kind == "reload":
            await hass.config_entries.async_reload(entry_id)
            return Response(text="OK")

        if kind == "state":
            applied = coordinator.apply_state_update(
                intent["periph_id"],
                intent["value"],
                **intent.get("extras", {}),
            )
            if not applied:
                _LOGGER.debug(
                    "Ignoring push for unselected / unknown periph %s",
                    intent["periph_id"],
                )
            return Response(text="OK")

        if kind == "empty":
            # Bare ping: wake a full refresh so a simple HTTP actuator still works.
            await coordinator.async_request_refresh()
            return Response(text="OK")

        _LOGGER.warning("Unrecognized eedomus webhook payload: %s", payload)
        return Response(text="Unrecognized payload", status=400)

    return _handle_webhook


def _coordinator_for_entry(
    hass: HomeAssistant, entry_id: str
) -> EedomusCoordinator | None:
    domain_data = hass.data.get(DOMAIN, {})
    coordinator = domain_data.get(entry_id)
    if isinstance(coordinator, EedomusCoordinator):
        return coordinator
    return None


async def _extract_payload(request: Request) -> dict[str, Any]:
    """Merge query string, JSON body and form fields into one dict."""
    payload: dict[str, Any] = dict(request.query)

    if request.method in ("POST", "PUT"):
        content_type = (request.content_type or "").lower()
        if "json" in content_type:
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001
                body = None
            if isinstance(body, dict):
                payload.update(body)
        else:
            try:
                form = await request.post()
            except Exception:  # noqa: BLE001
                form = None
            if form:
                payload.update({key: form.get(key) for key in form})

            # Some actionneurs POST raw JSON without a proper content-type.
            if len(payload) == len(request.query):
                try:
                    raw = await request.text()
                except Exception:  # noqa: BLE001
                    raw = ""
                raw = (raw or "").strip()
                if raw.startswith("{"):
                    try:
                        body = json.loads(raw)
                    except ValueError:
                        body = None
                    if isinstance(body, dict):
                        payload.update(body)

    return payload


def _first_str(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    value = _first_present(data, keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
        # Case-insensitive fallback for quirky HTTP actuators.
        lower = key.lower()
        for actual, value in data.items():
            if str(actual).lower() == lower and value not in (None, ""):
                return value
    return None
