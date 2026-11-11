"""Config flow for eedomus — credentials then multi-select like a remote HA."""

from __future__ import annotations

import logging
import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector

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
from .http import async_eedomus_clientsession
from .mapping import peripheral_label, sort_peripherals

_LOGGER = logging.getLogger(__name__)

CONF_SORT_BY = "sort_by"
SORT_ROOM = "room"
SORT_TYPE = "type"


def _build_device_options(
    peripherals: list[dict[str, Any]],
    *,
    sort_by: str = SORT_ROOM,
) -> list[selector.SelectOptionDict]:
    """Build multi-select options grouped/sorted for readability."""
    options: list[selector.SelectOptionDict] = []
    for periph in sort_peripherals(peripherals, sort_by=sort_by):
        periph_id = str(periph.get("periph_id") or "")
        if not periph_id:
            continue
        options.append(
            selector.SelectOptionDict(
                value=periph_id,
                label=peripheral_label(periph, sort_by=sort_by),
            )
        )
    return options


def _devices_schema(
    options: list[selector.SelectOptionDict],
    defaults: list[str],
) -> vol.Schema:
    # DROPDOWN + multiple → HA mobile picker (search + larger taps).
    # LIST checkboxes stay too cramped on a phone with long labels.
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


class EedomusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the eedomus config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._api_user: str | None = None
        self._api_secret: str | None = None
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._peripherals: list[dict[str, Any]] = []
        self._sort_by: str = SORT_ROOM

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Ask for API connection details."""
        errors: dict[str, str] = {}
        last_error = ""
        defaults = {
            CONF_API_HOST: DEFAULT_API_HOST,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        }

        if user_input is not None:
            try:
                host = str(user_input[CONF_API_HOST]).strip()
                api_user = str(user_input[CONF_API_USER]).strip()
                api_secret = str(user_input[CONF_API_SECRET]).strip()
                scan_interval = int(
                    user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                )
                defaults[CONF_API_HOST] = host
                defaults[CONF_SCAN_INTERVAL] = scan_interval

                if not api_user or not api_secret:
                    errors["base"] = (
                        "api_user/api_secret vides — ressaisir les identifiants API"
                    )
                    last_error = errors["base"]
                else:
                    client = EedomusClient(
                        session=async_eedomus_clientsession(self.hass, host),
                        host=host,
                        api_user=api_user,
                        api_secret=api_secret,
                    )
                    _LOGGER.info(
                        "eedomus config_flow trying host=%s base_url=%s",
                        host,
                        client.base_url,
                    )
                    await client.async_test_auth()
                    peripherals = await client.async_get_peripherals()

                    await self.async_set_unique_id(f"eedomus_{api_user}")
                    self._abort_if_unique_id_configured(
                        updates={
                            CONF_API_HOST: host,
                            CONF_API_SECRET: api_secret,
                            CONF_SCAN_INTERVAL: scan_interval,
                        }
                    )

                    self._host = host
                    self._api_user = api_user
                    self._api_secret = api_secret
                    self._scan_interval = scan_interval
                    self._peripherals = peripherals
                    return await self.async_step_organize()
            except AbortFlow:
                raise
            except EedomusAuthError as err:
                _LOGGER.warning("eedomus auth failed: %s", err)
                errors["base"] = f"Auth: {err}"[:220]
                last_error = errors["base"]
            except EedomusApiError as err:
                _LOGGER.warning("eedomus API failed: %s", err)
                errors["base"] = f"API {host}: {err}"[:220]
                last_error = errors["base"]
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during eedomus setup")
                errors["base"] = f"{type(err).__name__}: {err}"[:220]
                last_error = errors["base"]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_HOST, default=defaults[CONF_API_HOST]
                    ): str,
                    vol.Required(CONF_API_USER): str,
                    vol.Required(CONF_API_SECRET): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=defaults[CONF_SCAN_INTERVAL],
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
                "scan_hint": "60 s par défaut (automations puissance). 0 = webhook seul (PIR/RFX + règle eedomus)",
                "last_error": last_error or "—",
            },
        )

    async def async_step_organize(
        self, user_input: dict[str, Any] | None = None
    ):
        """Choose how to present the peripheral list."""
        if user_input is not None:
            self._sort_by = str(user_input.get(CONF_SORT_BY, SORT_ROOM))
            return await self.async_step_devices()

        return self.async_show_form(
            step_id="organize",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SORT_BY, default=SORT_ROOM): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=SORT_ROOM,
                                    label="Par pièce (recommandé)",
                                ),
                                selector.SelectOptionDict(
                                    value=SORT_TYPE,
                                    label="Par type (capteur, interrupteur…)",
                                ),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ):
        """Let the user pick which peripherals to import."""
        options = _build_device_options(self._peripherals, sort_by=self._sort_by)

        if user_input is not None:
            selected = [str(i) for i in user_input.get(CONF_SELECTED_DEVICES, [])]
            if not selected:
                return self.async_show_form(
                    step_id="devices",
                    data_schema=_devices_schema(options, selected),
                    errors={"base": "no_devices"},
                    description_placeholders={
                        "sort_by": (
                            "pièce" if self._sort_by == SORT_ROOM else "type"
                        ),
                        "count": str(len(options)),
                    },
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
            description_placeholders={
                "sort_by": "pièce" if self._sort_by == SORT_ROOM else "type",
                "count": str(len(options)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return EedomusOptionsFlowHandler()


class EedomusOptionsFlowHandler(config_entries.OptionsFlow):
    """Options: host, sort, devices, poll interval."""

    def __init__(self) -> None:
        self._sort_by = SORT_ROOM
        self._peripherals: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        last_error = ""
        entry = self.config_entry
        data = entry.data
        current_host = str(
            entry.options.get(CONF_API_HOST) or data.get(CONF_API_HOST) or ""
        )
        current_selected = [
            str(i)
            for i in (
                entry.options.get(CONF_SELECTED_DEVICES)
                or data.get(CONF_SELECTED_DEVICES, [])
            )
        ]
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

        probe_host = current_host
        sort_by = self._sort_by
        if user_input is not None:
            probe_host = str(user_input.get(CONF_API_HOST, current_host)).strip()
            sort_by = str(user_input.get(CONF_SORT_BY, SORT_ROOM))

        client = EedomusClient(
            session=async_eedomus_clientsession(self.hass, probe_host or current_host),
            host=probe_host or current_host,
            api_user=data[CONF_API_USER],
            api_secret=data[CONF_API_SECRET],
        )
        try:
            await client.async_test_auth()
            self._peripherals = await client.async_get_peripherals()
        except EedomusApiError as err:
            errors["base"] = f"API: {err}"[:220]
            last_error = errors["base"]
            _LOGGER.warning("eedomus options connect failed: %s", last_error)

        if user_input is not None and "base" not in errors:
            selected = [str(i) for i in user_input.get(CONF_SELECTED_DEVICES, [])]
            # Changing sort order → refresh labels once, then Valider again to save.
            if sort_by != self._sort_by:
                self._sort_by = sort_by
            elif not selected:
                errors["base"] = "no_devices"
            else:
                new_host = str(user_input[CONF_API_HOST]).strip()
                if new_host and new_host != data.get(CONF_API_HOST):
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**data, CONF_API_HOST: new_host},
                        title=f"eedomus ({new_host})",
                    )
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SELECTED_DEVICES: selected,
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )

        options = _build_device_options(self._peripherals, sort_by=sort_by)
        known_ids = {opt["value"] for opt in options}
        for orphan in current_selected:
            if orphan not in known_ids:
                options.append(
                    selector.SelectOptionDict(
                        value=orphan,
                        label=f"Indisponible  ·  #{orphan}",
                    )
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_HOST, default=current_host): str,
                    vol.Required(CONF_SORT_BY, default=sort_by): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=SORT_ROOM, label="Classer par pièce"
                                ),
                                selector.SelectOptionDict(
                                    value=SORT_TYPE, label="Classer par type"
                                ),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
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
            description_placeholders={
                "webhook_url": webhook_url,
                "last_error": last_error or "—",
                "base_url": client.base_url if current_host else "—",
            },
        )
