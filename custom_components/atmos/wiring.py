"""Open the configured transports and bridge them into :class:`AtmosRuntime`."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pyatmos_wg1000 import AtmosClient, InfoFeed, LanguageCatalog

from .const import (
    CONF_FALLBACK_AFTER,
    CONF_LANGUAGE,
    CONF_SERIAL_BAUDRATE,
    CONF_SERIAL_PORT,
    CONF_WG1000_HOST,
    CONF_WG1000_PASSWORD,
    CONF_WG1000_PORT,
    CONF_WG1000_USERNAME,
    CONF_WG1000_VERIFY_TLS,
    DEFAULT_FALLBACK_AFTER,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_WG1000_PORT,
    DOMAIN,
    PLATFORMS,
)
from .info import gateway_language_for_hass, resolve_info_dump
from .runtime import AtmosRuntime
from .source import SourceConfig

if TYPE_CHECKING:
    from pyatmos_serial import AtmosSerialFeed

LOGGER = logging.getLogger(__name__)


def runtime_for(hass: HomeAssistant, entry: ConfigEntry) -> AtmosRuntime:
    """Return the runtime stored for ``entry``.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.

    Raises:
        RuntimeError: Setup did not store a runtime.
    """
    domain_data: Any = hass.data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        raise RuntimeError("ATMOS data is missing")
    runtime = domain_data.get(entry.entry_id)
    if not isinstance(runtime, AtmosRuntime):
        raise RuntimeError("ATMOS runtime is missing")
    return runtime


def config_from_entry(entry: ConfigEntry) -> SourceConfig:
    """Build the source policy from entry data and options.

    Args:
        entry: ATMOS config entry.
    """
    data: Mapping[str, Any] = entry.data
    options: Mapping[str, Any] = entry.options
    fallback = options.get(CONF_FALLBACK_AFTER, DEFAULT_FALLBACK_AFTER)
    window = float(fallback) if isinstance(fallback, int | float) else DEFAULT_FALLBACK_AFTER
    return SourceConfig(
        serial=CONF_SERIAL_PORT in data,
        wg1000=CONF_WG1000_HOST in data,
        fallback_after=window,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect the configured transports and forward platforms.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.

    Raises:
        ConfigEntryNotReady: Every configured transport failed to open.
    """
    runtime = AtmosRuntime(config_from_entry(entry))
    serial_open = await _start_serial(hass, entry, runtime)
    gateway_open = await _start_gateway(hass, entry, runtime)
    if not serial_open and not gateway_open:
        await runtime.aclose()
        raise ConfigEntryNotReady("Neither RS485 nor WG1000 is reachable")

    if runtime.config.serial and runtime.config.wg1000:
        stop = asyncio.Event()
        watch = hass.async_create_task(runtime.watch_fallback(stop), name="atmos-fallback")

        async def _stop_watch() -> None:
            stop.set()
            watch.cancel()
            try:
                await watch
            except asyncio.CancelledError:
                return

        runtime.add_closer(_stop_watch)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and close transports.

    Args:
        hass: Home Assistant instance.
        entry: ATMOS config entry.
    """
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    domain_data: Any = hass.data.get(DOMAIN)
    if isinstance(domain_data, dict):
        runtime = domain_data.pop(entry.entry_id, None)
        if isinstance(runtime, AtmosRuntime):
            await runtime.aclose()
    return True


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _start_serial(hass: HomeAssistant, entry: ConfigEntry, runtime: AtmosRuntime) -> bool:
    """Open the RS485 listen path when the entry still configures it.

    TODO(rs485): the config flow no longer creates serial entries. Keep this
    path for existing dual-source entries and for the future menu.
    """
    if not runtime.config.serial:
        return False
    # Lazy import: new installs are WG1000-only and should not need the serial
    # package at import time of this module.
    from pyatmos_serial import AtmosSerialFeed, SerialPortSource, SerialSettings

    port_name = entry.data.get(CONF_SERIAL_PORT)
    baud = entry.data.get(CONF_SERIAL_BAUDRATE)
    if not isinstance(port_name, str) or not isinstance(baud, int):
        LOGGER.error("RS485 config entry is missing the port or baud rate")
        return False
    try:
        settings = SerialSettings(port=port_name, baudrate=baud)
        port = SerialPortSource(settings)
        await port.open()
    except Exception:
        LOGGER.exception("RS485 port did not open")
        return False

    feed = AtmosSerialFeed(port, on_bytes=runtime.note_serial_bytes)
    listen = hass.async_create_task(_listen(feed, runtime), name="atmos-serial")

    async def _close_serial() -> None:
        listen.cancel()
        with suppress(asyncio.CancelledError):
            await listen
        await feed.stop()

    runtime.add_closer(_close_serial)
    runtime.set_serial_open(True)
    return True


async def _listen(feed: AtmosSerialFeed, runtime: AtmosRuntime) -> None:
    bridge = asyncio.create_task(_bridge_serial(feed, runtime), name="atmos-serial-bridge")
    try:
        while True:
            await feed.read_once()
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER.exception("RS485 listen stopped")
        runtime.set_serial_open(False)
        raise
    finally:
        bridge.cancel()
        with suppress(asyncio.CancelledError):
            await bridge


async def _bridge_serial(feed: AtmosSerialFeed, runtime: AtmosRuntime) -> None:
    """Forward decoded serial samples. The codec emits none today."""
    async for update in feed.bus.subscribe():
        runtime.note_serial_update(update.register_id, update.value, now=time.monotonic())


async def _start_gateway(hass: HomeAssistant, entry: ConfigEntry, runtime: AtmosRuntime) -> bool:
    if not runtime.config.wg1000:
        return False
    host = entry.data.get(CONF_WG1000_HOST)
    username = entry.data.get(CONF_WG1000_USERNAME)
    password = entry.data.get(CONF_WG1000_PASSWORD)
    port = entry.data.get(CONF_WG1000_PORT, DEFAULT_WG1000_PORT)
    verify = entry.data.get(CONF_WG1000_VERIFY_TLS, False)
    if not isinstance(host, str) or not isinstance(username, str) or not isinstance(password, str):
        LOGGER.error("WG1000 config entry is missing the host or credentials")
        return False
    if not isinstance(port, int) or not isinstance(verify, bool):
        LOGGER.error("WG1000 config entry has a bad port or TLS flag")
        return False
    client = AtmosClient(host, port=port, verify_tls=verify)
    try:
        await client.connect()
        await client.hello()
        result = await client.login(username, password)
    except Exception:
        LOGGER.exception("WG1000 connection failed")
        await client.aclose()
        return False
    if not result.logged_in:
        LOGGER.error(
            "WG1000 login was rejected (role=%s blocked=%s retry_after_s=%s)",
            result.role,
            result.blocked,
            result.retry_after_s,
        )
        await client.aclose()
        return False

    language = _entry_language(entry)
    try:
        catalog = await LanguageCatalog.fetch(client, language=language)
        if language is None:
            codes = tuple(lang.code for lang in catalog.languages())
            mapped = gateway_language_for_hass(hass.config.language, codes)
            catalog.select(mapped or catalog.language.code)
        own_text = await client.fetch_own_text()
        dump = await client.fetch_info()
    except Exception:
        LOGGER.exception("WG1000 Info bootstrap failed")
        with suppress(Exception):
            await client.logout()
        await client.aclose()
        return False

    runtime.language = catalog.language.code
    runtime.note_info_groups(resolve_info_dump(dump, catalog, own_text))

    pull = asyncio.create_task(
        _pull_info(client, runtime, catalog, own_text),
        name="atmos-wg1000-info",
    )

    async def _close_gateway() -> None:
        pull.cancel()
        with suppress(asyncio.CancelledError):
            await pull
        with suppress(Exception):
            await client.logout()
        await client.aclose()

    runtime.add_closer(_close_gateway)
    runtime.set_gateway_open(True)
    return True


async def _pull_info(
    client: AtmosClient,
    runtime: AtmosRuntime,
    catalog: LanguageCatalog,
    own_text: tuple[str, ...],
) -> None:
    """Poll Info dumps and bridge resolved groups into the runtime."""
    try:
        feed = InfoFeed(client, interval=DEFAULT_POLL_INTERVAL)

        async def _bridge() -> None:
            async for update in feed.bus.subscribe():
                runtime.note_info_groups(resolve_info_dump(update.dump, catalog, own_text))

        bridge = asyncio.create_task(_bridge(), name="atmos-wg1000-info-bridge")
        LOGGER.info("WG1000 Info poll started (language=%s)", catalog.language.code)
        try:
            await feed.run()
        finally:
            bridge.cancel()
            with suppress(asyncio.CancelledError):
                await bridge
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER.exception("WG1000 Info poll stopped")
        runtime.set_gateway_open(False)
        raise


def _entry_language(entry: ConfigEntry) -> str | None:
    raw = entry.data.get(CONF_LANGUAGE)
    return raw if isinstance(raw, str) and raw else None
