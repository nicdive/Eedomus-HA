"""Async client for the eedomus HTTP API."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp

_LOGGER = logging.getLogger(__name__)


class EedomusApiError(Exception):
    """Raised when the eedomus API returns an error."""


class EedomusAuthError(EedomusApiError):
    """Raised when authentication fails."""


class EedomusClient:
    """Thin wrapper around the eedomus get/set API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        api_user: str,
        api_secret: str,
    ) -> None:
        self._session = session
        self._api_user = api_user
        self._api_secret = api_secret
        self._base = self._normalize_base(host)

    @staticmethod
    def _normalize_base(host: str) -> str:
        host = host.strip()
        if not host:
            raise EedomusApiError("Host is empty")
        if "://" not in host:
            # Local box IPs use plain HTTP; public API uses HTTPS.
            if host.startswith("api.eedomus.com") or host.endswith(".eedomus.com"):
                host = f"https://{host}"
            else:
                host = f"http://{host}"
        parsed = urlparse(host)
        # Accept either https://api.eedomus.com or http://192.168.x.x
        # Local API lives under /api ; cloud under /
        netloc = parsed.netloc or parsed.path
        scheme = parsed.scheme or "http"
        path = parsed.path.rstrip("/")
        if path in ("", "/") and not netloc.startswith("api."):
            # Local box root → /api
            return f"{scheme}://{netloc}/api"
        if path.endswith("/api"):
            return f"{scheme}://{netloc}{path}"
        # Cloud API: https://api.eedomus.com
        return f"{scheme}://{netloc}"

    async def _request(
        self,
        kind: str,
        action: str,
        extra: dict[str, Any] | None = None,
    ) -> Any:
        params: dict[str, Any] = {
            "action": action,
            "api_user": self._api_user,
            "api_secret": self._api_secret,
            "format": "json",
        }
        if extra:
            params.update(extra)

        url = f"{self._base}/{kind}"
        try:
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise EedomusApiError(f"HTTP error talking to eedomus: {err}") from err
        except ValueError as err:
            raise EedomusApiError(f"Invalid JSON from eedomus: {err}") from err

        if not isinstance(data, dict):
            raise EedomusApiError("Unexpected eedomus response shape")

        success = data.get("success")
        if success in (0, "0", False):
            body = data.get("body")
            message = body if isinstance(body, str) else str(body)
            if "auth" in message.lower() or "identif" in message.lower():
                raise EedomusAuthError(message)
            raise EedomusApiError(message or "eedomus API failure")

        return data.get("body")

    async def async_test_auth(self) -> bool:
        """Validate API credentials."""
        body = await self._request("get", "auth.test")
        _LOGGER.debug("auth.test => %s", body)
        return True

    async def async_get_peripherals(self) -> list[dict[str, Any]]:
        """Return the full peripheral list."""
        body = await self._request("get", "periph.list")
        if body is None:
            return []
        if isinstance(body, dict):
            # Some firmwares wrap the list
            for key in ("peripherals", "list", "items"):
                if isinstance(body.get(key), list):
                    return body[key]
            return [body]
        if not isinstance(body, list):
            raise EedomusApiError("periph.list did not return a list")
        return body

    async def async_get_caract(self, periph_id: str | int) -> dict[str, Any]:
        """Return characteristics / current value for one peripheral."""
        body = await self._request(
            "get",
            "periph.caract",
            {"periph_id": str(periph_id)},
        )
        if not isinstance(body, dict):
            raise EedomusApiError(f"Invalid caract for {periph_id}")
        return body

    async def async_set_value(self, periph_id: str | int, value: str | int | float) -> None:
        """Set a peripheral value (actuator command or sensor history write)."""
        await self._request(
            "set",
            "periph.value",
            {"periph_id": str(periph_id), "value": str(value)},
        )
