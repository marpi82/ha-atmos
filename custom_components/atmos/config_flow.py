"""Config flow for the WG1000 poll path.

TODO(rs485): re-offer ``serial_only`` / ``both`` in the user menu when the
serial codec is ready. The serial form steps below stay for that path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant
from pyatmos_wg1000 import AtmosClient

from .const import (
    CONF_FALLBACK_AFTER,
    CONF_SERIAL_BAUDRATE,
    CONF_SERIAL_PORT,
    CONF_WG1000_HOST,
    CONF_WG1000_PASSWORD,
    CONF_WG1000_USERNAME,
    CONF_WG1000_VERIFY_TLS,
    DEFAULT_FALLBACK_AFTER,
    DOMAIN,
)

_SERIAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_PORT): str,
        vol.Required(CONF_SERIAL_BAUDRATE): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)


@dataclass
class _Draft:
    include_serial: bool = False
    include_gateway: bool = False
    port: str | None = None
    baudrate: int | None = None
    host: str | None = None
    username: str | None = None
    password: str | None = None
    verify_tls: bool = False


class AtmosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up and reconfigure the local WG1000 poll path.

    Serial listen remains in the codebase for a later release; the user menu
    does not offer it yet.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Start with an empty draft."""
        self._draft = _Draft()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Start WG1000 setup. Serial modes are hidden until the codec exists.

        Args:
            user_input: Unused. The gateway form is the next step.
        """
        del user_input
        self._draft.include_serial = False
        self._draft.include_gateway = True
        return await self.async_step_gateway()

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change WG1000 host, credentials, or TLS verification.

        Args:
            user_input: Submitted gateway fields, when the form was posted.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _host(user_input.get(CONF_WG1000_HOST))
            username = _text(user_input.get(CONF_WG1000_USERNAME))
            password = user_input.get(CONF_WG1000_PASSWORD)
            verify = user_input.get(CONF_WG1000_VERIFY_TLS, False)
            if not isinstance(password, str):
                password = ""
            if password == "":
                existing = entry.data.get(CONF_WG1000_PASSWORD)
                password = existing if isinstance(existing, str) else ""
            if host is None or username is None or password == "" or not isinstance(verify, bool):
                errors["base"] = "invalid_gateway"
            else:
                auth_error = await _probe_gateway(self.hass, host, username, password, verify)
                if auth_error is not None:
                    errors["base"] = auth_error
                else:
                    data = dict(entry.data)
                    data[CONF_WG1000_HOST] = host
                    data[CONF_WG1000_USERNAME] = username
                    data[CONF_WG1000_PASSWORD] = password
                    data[CONF_WG1000_VERIFY_TLS] = verify
                    await self.async_set_unique_id(_unique_id(data))
                    self._abort_if_unique_id_mismatch(reason="already_configured")
                    return self.async_update_reload_and_abort(
                        entry,
                        data=data,
                        title=_title_from_data(data),
                    )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_gateway_schema(entry.data, password_optional=True),
            errors=errors,
        )

    async def async_step_serial_only(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect an RS485 port and ignore the gateway.

        TODO(rs485): wire this back into ``async_step_user`` when serial is ready.

        Args:
            user_input: Unused. The serial form is the next step.
        """
        del user_input
        self._draft.include_serial = True
        self._draft.include_gateway = False
        return await self.async_step_serial()

    async def async_step_gateway_only(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect WG1000 credentials and ignore RS485.

        Args:
            user_input: Unused. The gateway form is the next step.
        """
        del user_input
        self._draft.include_serial = False
        self._draft.include_gateway = True
        return await self.async_step_gateway()

    async def async_step_both(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect RS485 first, then WG1000.

        TODO(rs485): wire this back into ``async_step_user`` when serial is ready.

        Args:
            user_input: Unused. The serial form is the next step.
        """
        del user_input
        self._draft.include_serial = True
        self._draft.include_gateway = True
        return await self.async_step_serial()

    async def async_step_serial(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the serial device and baud rate.

        Args:
            user_input: Submitted port and baud, when the form was posted.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            port = _text(user_input.get(CONF_SERIAL_PORT))
            baud = _positive_int(user_input.get(CONF_SERIAL_BAUDRATE))
            if port is None or baud is None:
                errors["base"] = "invalid_serial"
            else:
                self._draft.port = port
                self._draft.baudrate = baud
                if self._draft.include_gateway:
                    return await self.async_step_gateway()
                return await self._create()
        return self.async_show_form(step_id="serial", data_schema=_SERIAL_SCHEMA, errors=errors)

    async def async_step_gateway(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the local WG1000 host and credentials.

        Args:
            user_input: Submitted host and credentials, when the form was posted.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _host(user_input.get(CONF_WG1000_HOST))
            username = _text(user_input.get(CONF_WG1000_USERNAME))
            password = user_input.get(CONF_WG1000_PASSWORD)
            verify = user_input.get(CONF_WG1000_VERIFY_TLS, False)
            if (
                host is None
                or username is None
                or not isinstance(password, str)
                or password == ""
                or not isinstance(verify, bool)
            ):
                errors["base"] = "invalid_gateway"
            else:
                auth_error = await _probe_gateway(self.hass, host, username, password, verify)
                if auth_error is not None:
                    errors["base"] = auth_error
                else:
                    self._draft.host = host
                    self._draft.username = username
                    self._draft.password = password
                    self._draft.verify_tls = verify
                    return await self._create()
        return self.async_show_form(step_id="gateway", data_schema=_gateway_schema(), errors=errors)

    async def _create(self) -> ConfigFlowResult:
        data = _entry_data(self._draft)
        await self.async_set_unique_id(_unique_id(data))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=_title(self._draft), data=data)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> AtmosOptionsFlow:
        """Return the fallback-window editor.

        Args:
            config_entry: Existing ATMOS entry. Home Assistant binds it on the flow.
        """
        del config_entry
        return AtmosOptionsFlow()


class AtmosOptionsFlow(OptionsFlow):
    """Edit how long serial may stay quiet before WG1000 takes over."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the fallback window when both transports are configured.

        Args:
            user_input: Submitted window, when the form was posted.
        """
        entry = self.config_entry
        if CONF_SERIAL_PORT not in entry.data or CONF_WG1000_HOST not in entry.data:
            return self.async_abort(reason="single_source")
        if user_input is not None:
            window = _positive_float(user_input.get(CONF_FALLBACK_AFTER))
            if window is None:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_fallback_schema(entry),
                    errors={"base": "invalid_fallback"},
                )
            return self.async_create_entry(title="", data={CONF_FALLBACK_AFTER: window})
        return self.async_show_form(step_id="init", data_schema=_fallback_schema(entry))


async def _probe_gateway(
    hass: HomeAssistant,
    host: str,
    username: str,
    password: str,
    verify_tls: bool,
) -> str | None:
    """Return a config-flow error key, or ``None`` when login succeeds."""
    del hass  # reserved for future executor helpers
    client = AtmosClient(host, verify_tls=verify_tls)
    try:
        await client.connect()
        await client.hello()
        result = await client.login(username, password)
    except Exception:
        await client.aclose()
        return "cannot_connect"
    await client.aclose()
    if result.logged_in:
        return None
    if result.blocked:
        return "login_blocked"
    return "invalid_auth"


def _gateway_schema(
    defaults: dict[str, Any] | None = None,
    *,
    password_optional: bool = False,
) -> vol.Schema:
    data = defaults or {}
    host = data.get(CONF_WG1000_HOST, "")
    username = data.get(CONF_WG1000_USERNAME, "")
    verify = data.get(CONF_WG1000_VERIFY_TLS, False)
    password_key = vol.Optional(CONF_WG1000_PASSWORD, default="") if password_optional else vol.Required(CONF_WG1000_PASSWORD)
    return vol.Schema(
        {
            vol.Required(CONF_WG1000_HOST, default=host if isinstance(host, str) else ""): str,
            vol.Required(CONF_WG1000_USERNAME, default=username if isinstance(username, str) else ""): str,
            password_key: str,
            vol.Required(CONF_WG1000_VERIFY_TLS, default=bool(verify)): bool,
        }
    )


def _fallback_schema(entry: ConfigEntry) -> vol.Schema:
    current = entry.options.get(CONF_FALLBACK_AFTER, DEFAULT_FALLBACK_AFTER)
    default = float(current) if isinstance(current, int | float) else DEFAULT_FALLBACK_AFTER
    return vol.Schema(
        {
            vol.Required(CONF_FALLBACK_AFTER, default=default): vol.All(vol.Coerce(float), vol.Range(min=1, max=3600)),
        }
    )


def _entry_data(draft: _Draft) -> dict[str, object]:
    data: dict[str, object] = {}
    if draft.include_serial:
        data[CONF_SERIAL_PORT] = draft.port
        data[CONF_SERIAL_BAUDRATE] = draft.baudrate
    if draft.include_gateway:
        data[CONF_WG1000_HOST] = draft.host
        data[CONF_WG1000_USERNAME] = draft.username
        data[CONF_WG1000_PASSWORD] = draft.password
        data[CONF_WG1000_VERIFY_TLS] = draft.verify_tls
    return data


def _unique_id(data: dict[str, object]) -> str:
    parts: list[str] = []
    port = data.get(CONF_SERIAL_PORT)
    host = data.get(CONF_WG1000_HOST)
    if isinstance(port, str):
        parts.append(f"serial:{port}")
    if isinstance(host, str):
        parts.append(f"wg1000:{host}")
    return "|".join(parts)


def _title(draft: _Draft) -> str:
    return _title_from_data(_entry_data(draft))


def _title_from_data(data: dict[str, object]) -> str:
    port = data.get(CONF_SERIAL_PORT)
    host = data.get(CONF_WG1000_HOST)
    if isinstance(port, str) and isinstance(host, str):
        return f"ATMOS ({port} / {host})"
    if isinstance(port, str):
        return f"ATMOS ({port})"
    if isinstance(host, str):
        return f"ATMOS ({host})"
    return "ATMOS"


def _host(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    lowered = text.lower()
    for prefix in ("https://", "http://", "wss://", "ws://"):
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.split("/")[0].strip()
    return text or None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return value


def _positive_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value <= 0:
        return None
    return float(value)
