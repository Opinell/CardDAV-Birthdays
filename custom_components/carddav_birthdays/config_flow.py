"""Config flow for CardDAV Birthdays."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import (
    CONF_PASSWORD,
    CONF_SERVER_URL,
    CONF_UPCOMING_DAYS,
    CONF_USERNAME,
    DEFAULT_UPCOMING_DAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVER_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_UPCOMING_DAYS, default=DEFAULT_UPCOMING_DAYS): vol.All(
            int, vol.Range(min=1, max=365)
        ),
    }
)


async def _validate_connection(hass: HomeAssistant, server_url: str, username: str, password: str) -> str | None:
    """Try a PROPFIND against the server URL. Returns error key or None on success."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    auth = aiohttp.BasicAuth(username, password)
    headers = {"Depth": "0", "Content-Type": "application/xml"}
    timeout = aiohttp.ClientTimeout(total=15)
    session = async_get_clientsession(hass)
    try:
        async with session.request(
            "PROPFIND", server_url, headers=headers, auth=auth, timeout=timeout
        ) as resp:
            if resp.status in (401, 403):
                return "invalid_auth"
            if resp.status >= 400:
                return "cannot_connect"
    except aiohttp.InvalidURL:
        return "invalid_url"
    except aiohttp.ClientError:
        return "cannot_connect"
    return None


class CardDAVBirthdaysConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CardDAV Birthdays."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            server_url = user_input[CONF_SERVER_URL].rstrip("/")
            error = await _validate_connection(
                self.hass, server_url, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_USERNAME]}@{server_url}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"CardDAV ({user_input[CONF_USERNAME]})",
                    data={**user_input, CONF_SERVER_URL: server_url},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
