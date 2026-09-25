"""In-memory arbitration between the RS485 listen and the WG1000 poll."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from .source import ActiveSource, SourceConfig, choose_source

logger = logging.getLogger(__name__)


class AtmosRuntime:
    """Holds both value maps and tells entities which one is active.

    Listeners run on the event loop. They must not block.
    """

    def __init__(self, config: SourceConfig) -> None:
        """Start with both transports closed and no samples."""
        self.config = config
        self.serial_bytes_seen = 0
        self._serial_open = False
        self._gateway_open = False
        self._last_serial: float | None = None
        self._serial_values: dict[int, int] = {}
        self._gateway_values: dict[int, int] = {}
        self._listeners: list[Callable[[], None]] = []
        self._closers: list[Callable[[], Awaitable[None]]] = []
        self._stale_emitted = False

    @property
    def serial_open(self) -> bool:
        """Return whether the serial port is open."""
        return self._serial_open

    @property
    def gateway_open(self) -> bool:
        """Return whether the WG1000 session is logged in."""
        return self._gateway_open

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register ``listener`` and return an unsubscribe callable.

        Args:
            listener: Called with no arguments after a relevant change.
        """
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    def add_closer(self, closer: Callable[[], Awaitable[None]]) -> None:
        """Run ``closer`` during :meth:`aclose`, in reverse registration order.

        Args:
            closer: Async teardown step owned by the integration wiring.
        """
        self._closers.append(closer)

    def set_serial_open(self, is_open: bool) -> None:
        """Record whether the serial port is open.

        Args:
            is_open: ``True`` after a successful open.
        """
        self._serial_open = is_open
        self._emit()

    def set_gateway_open(self, is_open: bool) -> None:
        """Record whether the WG1000 session is logged in.

        Args:
            is_open: ``True`` after a successful login.
        """
        self._gateway_open = is_open
        self._emit()

    def note_serial_bytes(self, count: int) -> None:
        """Count raw bytes. This does not refresh serial freshness.

        Args:
            count: Size of the chunk just read.
        """
        if count > 0:
            self.serial_bytes_seen += count

    def note_serial_update(self, register_id: int, value: int, *, now: float) -> None:
        """Store a decoded serial sample and mark serial fresh.

        Args:
            register_id: Wire register id.
            value: Raw word.
            now: Monotonic time of the sample.
        """
        self._serial_values[register_id] = value
        self._last_serial = now
        self._stale_emitted = False
        self._emit()

    def note_gateway_update(self, register_id: int, value: int) -> None:
        """Store one polled WG1000 sample.

        Args:
            register_id: Wire register id.
            value: Raw word.
        """
        self._gateway_values[register_id] = value
        self._emit()

    def active_source(self, *, now: float | None = None) -> ActiveSource:
        """Return the transport that owns state at ``now``.

        Args:
            now: Monotonic time. Defaults to :func:`time.monotonic`.
        """
        clock = time.monotonic() if now is None else now
        return choose_source(
            self.config,
            now=clock,
            last_serial_update=self._last_serial,
            serial_open=self._serial_open,
            gateway_open=self._gateway_open,
        )

    def value(self, register_id: int, *, now: float | None = None) -> int | None:
        """Return the raw word from the active transport.

        Args:
            register_id: Wire register id.
            now: Monotonic time. Defaults to :func:`time.monotonic`.
        """
        source = self.active_source(now=now)
        if source is ActiveSource.SERIAL:
            return self._serial_values.get(register_id)
        if source is ActiveSource.WG1000:
            return self._gateway_values.get(register_id)
        return None

    async def watch_fallback(self, stop: asyncio.Event) -> None:
        """Notify listeners when a fresh serial sample ages out.

        Args:
            stop: Set this event to end the watch.

        Raises:
            Exception: Unexpected failures are logged and re-raised.
        """
        try:
            while not stop.is_set():
                delay = self._seconds_until_fallback(time.monotonic())
                if delay is None or delay > 0:
                    await self._wait(stop, self.config.fallback_after if delay is None else delay)
                    continue
                if not self._stale_emitted:
                    self._stale_emitted = True
                    self._emit()
                await self._wait(stop, self.config.fallback_after)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("source fallback watch failed")
            raise

    async def aclose(self) -> None:
        """Run registered teardown steps."""
        while self._closers:
            closer = self._closers.pop()
            await closer()

    def _seconds_until_fallback(self, now: float) -> float | None:
        if not (self.config.serial and self.config.wg1000) or self._last_serial is None:
            return None
        remaining = self.config.fallback_after - (now - self._last_serial)
        return max(remaining, 0.0)

    async def _wait(self, stop: asyncio.Event, delay: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            return

    def _emit(self) -> None:
        for listener in tuple(self._listeners):
            listener()
