"""WG1000 Info + circuit poll with automatic session reconnect.

Kept free of Home Assistant imports so pytest can exercise the reconnect
loop without ``homeassistant`` installed.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from pyatmos_wg1000 import AtmosClient, InfoFeed, LanguageCatalog
from pyatmos_wg1000.protocol.login import LoginResult

from .circuit import circuit_register_ids, circuits_from_records
from .const import DEFAULT_POLL_INTERVAL
from .info import resolve_info_dump
from .runtime import AtmosRuntime

LOGGER = logging.getLogger(__name__)

DEFAULT_RECONNECT_INITIAL = 5.0
DEFAULT_RECONNECT_MAX = 300.0


async def await_cancelled(task: asyncio.Task[Any]) -> None:
    """Wait for a cancelled task without swallowing other errors."""
    try:
        await task
    except asyncio.CancelledError:
        return


async def login_gateway(client: AtmosClient, username: str, password: str) -> LoginResult:
    """Connect, hello, and login. Return the gateway login result.

    Args:
        client: WG1000 client (socket may be closed).
        username: Gateway user name.
        password: Gateway password.
    """
    await client.connect()
    await client.hello()
    return await client.login(username, password, stay=True)


async def pull_gateway(
    client: AtmosClient,
    runtime: AtmosRuntime,
    catalog: LanguageCatalog,
    own_text: tuple[str, ...],
    *,
    username: str,
    password: str,
    interval: float = DEFAULT_POLL_INTERVAL,
    reconnect_initial: float = DEFAULT_RECONNECT_INITIAL,
    reconnect_max: float = DEFAULT_RECONNECT_MAX,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> None:
    """Poll Info dumps and circuit registers until cancelled.

    When the WebSocket dies, mark the gateway closed, back off, re-login, and
    resume polling. Entities flip to unavailable while the session is down.

    Args:
        client: Already connected and logged-in client for the first pass.
        runtime: Shared runtime updated by each successful dump.
        catalog: Language tables for caption expansion.
        own_text: OwnText slots from bootstrap.
        username: Gateway user name for reconnect.
        password: Gateway password for reconnect.
        interval: Seconds between Info dumps.
        reconnect_initial: First delay after a drop, in seconds.
        reconnect_max: Cap for exponential backoff, in seconds.
        sleep: Injected sleeper for tests. Defaults to ``asyncio.sleep``.
    """
    sleeper = sleep or asyncio.sleep
    delay = reconnect_initial
    while True:
        try:
            runtime.set_gateway_open(True)
            runtime.bind_write_registers(client.write_registers)
            feed = InfoFeed(client, interval=interval)

            async def _bridge(active: InfoFeed = feed) -> None:
                async for update in active.bus.subscribe():
                    runtime.note_info_groups(resolve_info_dump(update.dump, catalog, own_text))
                    try:
                        records = await client.read_registers(circuit_register_ids())
                        runtime.note_circuits(circuits_from_records(records, own_text=own_text, catalog=catalog))
                    except Exception:
                        LOGGER.exception("WG1000 circuit poll failed")

            bridge = asyncio.create_task(_bridge(), name="atmos-wg1000-bridge")
            LOGGER.info("WG1000 Info+circuit poll started (language=%s)", catalog.language.code)
            try:
                # Let the bridge reach ``subscribe()`` before the first dump.
                await asyncio.sleep(0)
                await feed.run()
            finally:
                bridge.cancel()
                await await_cancelled(bridge)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("WG1000 poll stopped; reconnecting in %.0fs", delay)
            runtime.set_gateway_open(False)
            runtime.bind_write_registers(None)
            with suppress(Exception):
                await client.aclose()

            while True:
                await sleeper(delay)
                try:
                    result = await login_gateway(client, username, password)
                    if result.logged_in:
                        LOGGER.info("WG1000 session reconnected")
                        delay = reconnect_initial
                        break
                    LOGGER.error(
                        "WG1000 reconnect login was rejected (role=%s blocked=%s retry_after_s=%s)",
                        result.role,
                        result.blocked,
                        result.retry_after_s,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOGGER.exception("WG1000 reconnect failed")
                delay = min(delay * 2, reconnect_max)
