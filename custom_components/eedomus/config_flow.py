"""Config flow for eedomus — credentials then multi-select like a remote HA."""

from __future__ import annotations

import logging
import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EedomusApiError, EedomusAuthError, EedomusClient
from .const import (
    CONF_API_HOST,
    CONF_API_SECRET,
    CONF_API_USER,
    CONF_SCAN_INTERVAL,
    CONF_SELECTED_DEVICES,
    CONF_WEBHOOK_ID,
    DEFAULT_API_HOST,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .helpers import webhook_url_for_entry
from .mapping import peripheral_label

_LOGGER = logging.getLogger(__name__)


def _build_device_options(peripherals: list[dict[str, Any]]) -> list[selector.SelectOptionDict]:
    """Build sorted multi-select options from the eedomus peripheral list."""
    options: list[selector.SelectOptionDict] = []
    for periph in sorted(
        peripherals,
        key=lambda item: (
            str(item.get("room_name") or ""),
            str(item.get("name") or ""),
        ),
    ):
        periph_id = str(periph.get("periph_id") or "")
        if not periph_id:
            continue
        options.append(
            selector.SelectOptionDict(
                value=periph_id,
                label=peripheral_label(periph),
            )
        )
    return options


class EedomusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the eedomus config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._api_user: str | None = None
        self._api_secret: str | None = None
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._peripherals: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Ask for API connection details."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_API_HOST].strip()
            api_user = user_input[CONF_API_USER].strip()
            api_secret = user_input[CONF_API_SECRET].strip()
            scan_interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

            client = EedomusClient(
                session=async_get_clientsession(self.hass),
                host=host,
                api_user=api_user,
                api_secret=api_secret,
            )
            try:
                await client.async_test_auth()
                peripherals = await client.async_get_peripherals()
            except EedomusAuthError:
                errors["base"] = "invalid_auth"
            except EedomusApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during eedomus setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"eedomus_{api_user}")
                self._abort_if_unique_id_configured()

                self._host = host
                self._api_user = api_user
                self._api_secret = api_secret
                self._scan_interval = scan_interval
                self._peripherals = peripherals
                return await self.async_step_devices()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_HOST, default=DEFAULT_API_HOST): str,
                    vol.Required(CONF_API_USER): str,
                    vol.Required(CONF_API_SECRET): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=5,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "scan_hint": "0 = push webhook uniquement (recommandé pour Z-Wave/RFX)",
            },
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ):
        """Let the user pick which peripherals to import."""
        options = _build_device_options(self._peripherals)

        if user_input is not None:
            selected = [str(i) for i in user_input.get(CONF_SELECTED_DEVICES, [])]
            if not selected:
                return self.async_show_form(
                    step_id="devices",
                    data_schema=_devices_schema(options, selected),
                    errors={"base": "no_devices"},
                )

            return self.async_create_entry(
                title=f"eedomus ({self._host})",
                data={
                    CONF_API_HOST: self._host,
                    CONF_API_USER: self._api_user,
                    CONF_API_SECRET: self._api_secret,
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_SELECTED_DEVICES: selected,
                    CONF_WEBHOOK_ID: secrets.token_hex(16),
                },
            )

        return self.async_show_form(
            step_id="devices",
            data_schema=_devices_schema(options, []),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return EedomusOptionsFlowHandler()


def _devices_schema(
    options: list[selector.SelectOptionDict],
    defaults: list[str],
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SELECTED_DEVICES, default=defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


class EedomusOptionsFlowHandler(config_entries.OptionsFlow):
    """Options: re-select devices and tweak poll interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        entry = self.config_entry
        data = entry.data
        current_selected = [str(i) for i in (
            entry.options.get(CONF_SELECTED_DEVICES)
            or data.get(CONF_SELECTED_DEVICES, [])
        )]
        current_interval = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )
        webhook_id = str(data.get(CONF_WEBHOOK_ID) or "")
        webhook_url = (
            webhook_url_for_entry(self.hass, webhook_id)
            if webhook_id
            else "(webhook non encore initialisé — rechargez l'intégration)"
        )

        client = EedomusClient(
            session=async_get_clientsession(self.hass),
            host=data[CONF_API_HOST],
            api_user=data[CONF_API_USER],
            api_secret=data[CONF_API_SECRET],
        )

        peripherals: list[dict[str, Any]] = []
        try:
            peripherals = await client.async_get_peripherals()
        except EedomusApiError:
            errors["base"] = "cannot_connect"

        if user_input is not None and "base" not in errors:
            selected = [str(i) for i in user_input.get(CONF_SELECTED_DEVICES, [])]
            if not selected:
                errors["base"] = "no_devices"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SELECTED_DEVICES: selected,
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )

        options = _build_device_options(peripherals)
        known_ids = {opt["value"] for opt in options}
        for orphan in current_selected:
            if orphan not in known_ids:
                options.append(
                    selector.SelectOptionDict(
                        value=orphan,
                        label=f"[indisponible] #{orphan}",
                    )
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SELECTED_DEVICES, default=current_selected
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=5,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"webhook_url": webhook_url},
        )
