"""Constants for the ATMOS Home Assistant integration."""

from __future__ import annotations

from typing import Final

from .registers import pull_register_ids

DOMAIN: Final = "atmos"
PLATFORMS: Final[list[str]] = ["sensor", "binary_sensor"]

CONF_SERIAL_PORT: Final = "serial_port"
CONF_SERIAL_BAUDRATE: Final = "serial_baudrate"
CONF_WG1000_HOST: Final = "wg1000_host"
CONF_WG1000_PORT: Final = "wg1000_port"
CONF_WG1000_USERNAME: Final = "wg1000_username"
CONF_WG1000_PASSWORD: Final = "wg1000_password"  # noqa: S105
CONF_WG1000_VERIFY_TLS: Final = "wg1000_verify_tls"
CONF_FALLBACK_AFTER: Final = "fallback_after"

DEFAULT_FALLBACK_AFTER: Final = 120.0
DEFAULT_WG1000_PORT: Final = 443
DEFAULT_POLL_INTERVAL: Final = 30.0

__all__ = [
    "CONF_FALLBACK_AFTER",
    "CONF_SERIAL_BAUDRATE",
    "CONF_SERIAL_PORT",
    "CONF_WG1000_HOST",
    "CONF_WG1000_PASSWORD",
    "CONF_WG1000_PORT",
    "CONF_WG1000_USERNAME",
    "CONF_WG1000_VERIFY_TLS",
    "DEFAULT_FALLBACK_AFTER",
    "DEFAULT_POLL_INTERVAL",
    "DEFAULT_WG1000_PORT",
    "DOMAIN",
    "PLATFORMS",
    "pull_register_ids",
]
