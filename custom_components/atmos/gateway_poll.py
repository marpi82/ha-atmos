"""WG1000 Info + circuit poll with automatic session reconnect.

Kept free of Home Assistant imports so pytest can exercise the reconnect
loop without ``homeassistant`` installed.

Info dumps follow the stock Informace-page cadence (1 s). Homepage circuit
registers follow ``PrmID*`` buckets parsed from ``Pages.js``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from typing import Any

from pyatmos_wg1000 import AtmosClient, InfoFeed, LanguageCatalog
from pyatmos_wg1000.protocol.login import LoginResult

from .circuit import (
    circuit_register_ids,
    circuits_from_words,
    merge_register_words,
)
from .const import DEFAULT_INFO_POLL_INTERVAL
from .info import resolve_info_dump
from .runtime import AtmosRuntime
from .ui_schedule import circuit_schedule_from_pages

LOGGER = logging.getLogger(__name__)

DEFAULT_RECONNECT_INITIAL = 5.0
DEFAULT_RECONNECT_MAX = 300.0
_PAGES_JS = "Pages.js"


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


async def _load_circuit_schedule(
    client: AtmosClient,
    override: Mapping[float, Sequence[int]] | None,
) -> dict[float, tuple[int, ...]]:
    """Return interval → wire ids from ``override``, ``Pages.js``, or fallback."""
    if override is not None:
        return {float(seconds): tuple(ids) for seconds, ids in override.items() if ids}

    source: str | None = None
    try:
        blob = await client.download_file(_PAGES_JS)
        source = blob.decode("utf-8")
    except Exception:
        LOGGER.exception("WG1000 Pages.js download failed; using fallback circuit schedule")
    return circuit_schedule_from_pages(source)


async def pull_gateway(
    client: AtmosClient,
    runtime: AtmosRuntime,
    catalog: LanguageCatalog,
    own_text: tuple[str, ...],
    *,
    username: str,
    password: str,
    info_interval: float = DEFAULT_INFO_POLL_INTERVAL,
    circuit_schedule: Mapping[float, Sequence[int]] | None = None,
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
        info_interval: Seconds between Info dumps (stock Informace page: 1 s).
        circuit_schedule: Optional interval → wire ids (tests / overrides).
            When omitted, ``Pages.js`` is downloaded and parsed.
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
            schedule = await _load_circuit_schedule(client, circuit_schedule)
            await _run_session(
                client,
                runtime,
                catalog,
                own_text,
                info_interval=info_interval,
                circuit_schedule=schedule,
            )
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
                    with suppress(Exception):
                        await client.aclose()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOGGER.exception("WG1000 reconnect failed")
                    with suppress(Exception):
                        await client.aclose()
                delay = min(delay * 2, reconnect_max)


async def _run_session(
    client: AtmosClient,
    runtime: AtmosRuntime,
    catalog: LanguageCatalog,
    own_text: tuple[str, ...],
    *,
    info_interval: float,
    circuit_schedule: Mapping[float, Sequence[int]],
) -> None:
    """Run Info + per-bucket circuit polls until one task fails or is cancelled."""
    words: dict[int, int] = {}
    words_lock = asyncio.Lock()

    try:
        seed = await client.read_registers(circuit_register_ids())
        merge_register_words(words, seed)
        runtime.note_circuits(circuits_from_words(words, own_text=own_text, catalog=catalog))
    except Exception:
        LOGGER.exception("WG1000 circuit seed poll failed")

    feed = InfoFeed(client, interval=info_interval)

    async def _info_bridge(active: InfoFeed = feed) -> None:
        async for update in active.bus.subscribe():
            runtime.note_info_groups(resolve_info_dump(update.dump, catalog, own_text))

    async def _circuit_bucket(interval: float, register_ids: Sequence[int]) -> None:
        while True:
            try:
                records = await client.read_registers(register_ids)
                async with words_lock:
                    if merge_register_words(words, records) or not runtime.circuits:
                        runtime.note_circuits(circuits_from_words(words, own_text=own_text, catalog=catalog))
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("WG1000 circuit poll failed (every %.0fs)", interval)
            await asyncio.sleep(interval)

    bridge = asyncio.create_task(_info_bridge(), name="atmos-wg1000-info-bridge")
    feed_task = asyncio.create_task(feed.run(), name="atmos-wg1000-info-feed")
    circuit_tasks = [
        asyncio.create_task(
            _circuit_bucket(interval, ids),
            name=f"atmos-wg1000-circuit-{interval:g}s",
        )
        for interval, ids in circuit_schedule.items()
    ]
    buckets = ", ".join(f"{interval:g}s x {len(ids)}" for interval, ids in circuit_schedule.items()) or "none"
    LOGGER.info(
        "WG1000 poll started (language=%s info=%.0fs circuits=%s)",
        catalog.language.code,
        info_interval,
        buckets,
    )
    workers = (bridge, feed_task, *circuit_tasks)
    try:
        # Let the info bridge reach ``subscribe()`` before the first dump.
        await asyncio.sleep(0)
        done, _pending = await asyncio.wait(workers, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc
    finally:
        for task in workers:
            task.cancel()
        for task in workers:
            await await_cancelled(task)
