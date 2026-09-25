"""Constants for the ATMOS Home Assistant integration."""

from __future__ import annotations

from typing import Final

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


def pull_register_ids() -> tuple[int, ...]:
    """Return WG1000 register ids to poll.

    The tuple stays empty until the register map is known. The pull loop then
    stays logged in and does not invent ids.
    """
    return ()
