"""Constants for the ATMOS Home Assistant integration."""

from __future__ import annotations

from typing import Final

from pyatmos_wg1000.protocol import INFO_PAGE_POLL_INTERVAL

DOMAIN: Final = "atmos"
PLATFORMS: Final[list[str]] = ["sensor", "binary_sensor", "climate", "number"]

CONF_SERIAL_PORT: Final = "serial_port"
CONF_SERIAL_BAUDRATE: Final = "serial_baudrate"
CONF_WG1000_HOST: Final = "wg1000_host"
CONF_WG1000_PORT: Final = "wg1000_port"
CONF_WG1000_USERNAME: Final = "wg1000_username"
CONF_WG1000_PASSWORD: Final = "wg1000_password"  # noqa: S105
CONF_WG1000_VERIFY_TLS: Final = "wg1000_verify_tls"
CONF_LANGUAGE: Final = "language"
CONF_FALLBACK_AFTER: Final = "fallback_after"

DEFAULT_FALLBACK_AFTER: Final = 120.0
DEFAULT_WG1000_PORT: Final = 443
# Stock Informace page requests a new dump every 1 s (see Pages.js Timer).
DEFAULT_INFO_POLL_INTERVAL: Final = INFO_PAGE_POLL_INTERVAL

__all__ = [
    "CONF_FALLBACK_AFTER",
    "CONF_LANGUAGE",
    "CONF_SERIAL_BAUDRATE",
    "CONF_SERIAL_PORT",
    "CONF_WG1000_HOST",
    "CONF_WG1000_PASSWORD",
    "CONF_WG1000_PORT",
    "CONF_WG1000_USERNAME",
    "CONF_WG1000_VERIFY_TLS",
    "DEFAULT_FALLBACK_AFTER",
    "DEFAULT_INFO_POLL_INTERVAL",
    "DEFAULT_WG1000_PORT",
    "DOMAIN",
    "PLATFORMS",
]
