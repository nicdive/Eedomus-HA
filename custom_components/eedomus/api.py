"""Async client for the eedomus HTTP API."""

from __future__ import annotations

import json
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

    @property
    def base_url(self) -> str:
        """Normalized API root (…/api for local box)."""
        return self._base

    @staticmethod
    def is_local_host(host: str) -> bool:
        """Return True when the host targets a LAN box rather than the cloud API."""
        normalized = host.strip().lower()
        if "://" in normalized:
            normalized = urlparse(normalized).netloc or normalized
        normalized = normalized.split("/")[0].split(":")[0]
        if normalized in {"api.eedomus.com"} or normalized.endswith(".eedomus.com"):
            # eedomus.local is the box mDNS name, not cloud.
            return normalized == "eedomus.local"
        return True

    @staticmethod
    def _normalize_base(host: str) -> str:
        host = host.strip()
        if not host:
            raise EedomusApiError("Host is empty")
        if "://" not in host:
            # Local box IPs use plain HTTP; public API uses HTTPS.
            if host.startswith("api.eedomus.com") or (
                host.endswith(".eedomus.com") and not host.startswith("eedomus.")
            ):
                host = f"https://{host}"
            else:
                host = f"http://{host}"
        parsed = urlparse(host)
        # Accept either https://api.eedomus.com or http://192.168.x.x
        # Local API lives under /api ; cloud under /
        netloc = parsed.netloc or parsed.path
        scheme = parsed.scheme or "http"
        path = parsed.path.rstrip("/")
        host_only = netloc.split("@")[-1].split(":")[0].lower()
        local = host_only == "eedomus.local" or not host_only.endswith(".eedomus.com")
        if path in ("", "/") and local:
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
        *,
        timeout: float = 30,
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
        safe_params = {**params, "api_secret": "***"}
        _LOGGER.info("eedomus GET %s params=%s", url, safe_params)

        try:
            async with self._session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True,
                headers={"Accept": "application/json, text/plain, */*"},
            ) as resp:
                raw = await resp.read()
                # Local box firmware may not advertise UTF-8 correctly.
                text = raw.decode("utf-8", errors="replace")
                if resp.status >= 400:
                    raise EedomusApiError(
                        f"HTTP {resp.status} from {url}: {text[:200]}"
                    )
                try:
                    data = json.loads(text) if text else None
                except json.JSONDecodeError as err:
                    raise EedomusApiError(
                        f"Invalid JSON from eedomus ({url}): {text[:200]}"
                    ) from err
        except TimeoutError as err:
            raise EedomusApiError(
                f"Timeout contacting eedomus at {self._base} (action={action})"
            ) from err
        except aiohttp.ClientError as err:
            raise EedomusApiError(
                f"HTTP error contacting {self._base}: {err}"
            ) from err
        except UnicodeError as err:
            raise EedomusApiError(
                f"Encoding error from {self._base}: {err}"
            ) from err

        if not isinstance(data, dict):
            raise EedomusApiError(f"Unexpected eedomus response shape: {data!r}"[:200])

        success = data.get("success")
        if success in (0, "0", False):
            body = data.get("body")
            if isinstance(body, dict):
                message = str(
                    body.get("error_msg")
                    or body.get("error")
                    or body.get("message")
                    or body
                )
            else:
                message = body if isinstance(body, str) else str(body)
            lowered = message.lower()
            if (
                "auth" in lowered
                or "identif" in lowered
                or "password" in lowered
                or "secret" in lowered
            ):
                raise EedomusAuthError(message)
            raise EedomusApiError(message or "eedomus API failure")

        return data.get("body")

    async def async_test_auth(self) -> bool:
        """Validate API credentials."""
        body = await self._request("get", "auth.test", timeout=15)
        _LOGGER.debug("auth.test => %s", body)
        return True

    async def async_get_peripherals(self) -> list[dict[str, Any]]:
        """Return the full peripheral list."""
        body = await self._request("get", "periph.list", timeout=60)
        if body is None:
            return []
        if isinstance(body, dict):
            # Some firmwares wrap the list
            for key in ("peripherals", "list", "items"):
                if isinstance(body.get(key), list):
                    return body[key]
            return [body]
        if not isinstance(body, list):
            raise EedomusApiError(
                f"periph.list did not return a list (got {type(body).__name__})"
            )
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
