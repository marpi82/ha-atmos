"""Open the configured transports and bridge them into :class:`AtmosRuntime`."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pyatmos_serial import AtmosSerialFeed, SerialPortSource, SerialSettings
from pyatmos_wg1000 import AtmosClient

from .const import (
    CONF_FALLBACK_AFTER,
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
    pull_register_ids,
)
from .runtime import AtmosRuntime
from .source import SourceConfig

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
    gateway_open = await _start_gateway(entry, runtime)
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
    if not runtime.config.serial:
        return False
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


async def _start_gateway(entry: ConfigEntry, runtime: AtmosRuntime) -> bool:
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
        result = await client.login(username, password)
    except Exception:
        LOGGER.exception("WG1000 connection failed")
        await client.aclose()
        return False
    if not result.logged_in:
        LOGGER.error("WG1000 login was rejected")
        await client.aclose()
        return False

    stop = asyncio.Event()
    pull = asyncio.create_task(_pull_gateway(client, runtime, stop), name="atmos-wg1000")

    async def _close_gateway() -> None:
        stop.set()
        pull.cancel()
        with suppress(asyncio.CancelledError):
            await pull
        with suppress(Exception):
            await client.logout()
        await client.aclose()

    runtime.add_closer(_close_gateway)
    runtime.set_gateway_open(True)
    return True


async def _pull_gateway(client: AtmosClient, runtime: AtmosRuntime, stop: asyncio.Event) -> None:
    """Poll WG1000 registers once a map exists. Until then, stay logged in."""
    try:
        register_ids = pull_register_ids()
        if not register_ids:
            LOGGER.info("WG1000 pull is idle because the register map is empty")
            await stop.wait()
            return
        from pyatmos_wg1000 import AtmosFeed

        feed = AtmosFeed(client, register_ids, interval=DEFAULT_POLL_INTERVAL)

        async def _bridge() -> None:
            async for update in feed.bus.subscribe():
                runtime.note_gateway_update(update.register_id, update.value)

        bridge = asyncio.create_task(_bridge(), name="atmos-wg1000-bridge")
        try:
            await feed.run()
        finally:
            bridge.cancel()
            try:
                await bridge
            except asyncio.CancelledError:
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER.exception("WG1000 pull stopped")
        runtime.set_gateway_open(False)
        raise
