"""WG1000 poll reconnects after a dropped WebSocket."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pyatmos_wg1000.protocol.data import InfoDump, InfoItem

from custom_components.atmos.gateway_poll import pull_gateway
from custom_components.atmos.runtime import AtmosRuntime
from custom_components.atmos.source import ActiveSource, SourceConfig

_TEST_PASSWORD = "pw-for-test"  # noqa: S105


def test_gateway_poll_import_does_not_load_home_assistant() -> None:
    """Reconnect loop stays free of Home Assistant imports."""
    assert "homeassistant" not in sys.modules
    assert "custom_components.atmos.wiring" not in sys.modules


@dataclass
class _LoginResult:
    role: int = 1
    blocked: bool = False
    retry_after_s: int | None = None

    @property
    def logged_in(self) -> bool:
        return self.role > 0


class _FakeCatalog:
    @dataclass(frozen=True)
    class _Language:
        code: str = "POL"

    language = _Language()

    def text(self, key: str) -> str | None:
        return None


class _FakeClient:
    """Fails the first Info fetch, then accepts a re-login and second dump."""

    def __init__(self) -> None:
        self.fetch_calls = 0
        self.connect_calls = 0
        self.aclose_calls = 0
        self.write_registers = AsyncMock()

    async def fetch_info(self, ac16: int = 0) -> InfoDump:
        self.fetch_calls += 1
        if self.fetch_calls == 1:
            raise ConnectionError("no close frame received or sent")
        item = InfoItem(
            typ=0,
            vzhled=0,
            skupina=1,
            text_a=0,
            text_b=0,
            caption=1011,
            value=b"",
        )
        return InfoDump(ac16=ac16, items=(item,))

    async def read_registers(self, register_ids: Any, **kwargs: Any) -> tuple[()]:
        return ()

    async def connect(self) -> None:
        self.connect_calls += 1

    async def hello(self) -> int:
        return 0

    async def login(self, username: str, password: str, *, stay: bool = False) -> _LoginResult:
        assert username == "user"
        assert password == _TEST_PASSWORD
        assert stay is True
        return _LoginResult()

    async def aclose(self) -> None:
        self.aclose_calls += 1


@pytest.mark.asyncio
async def test_pull_gateway_reconnects_after_transport_drop() -> None:
    """After ConnectionError the session is rebuilt and polling resumes."""
    runtime = AtmosRuntime(SourceConfig(serial=False, wg1000=True, fallback_after=10))
    client = _FakeClient()
    sleeps: list[float] = []

    async def _sleep(delay: float) -> None:
        sleeps.append(delay)

    task = asyncio.create_task(
        pull_gateway(
            client,  # type: ignore[arg-type]
            runtime,
            _FakeCatalog(),  # type: ignore[arg-type]
            (),
            username="user",
            password=_TEST_PASSWORD,
            interval=0.01,
            reconnect_initial=0.01,
            sleep=_sleep,
        )
    )
    for _ in range(200):
        await asyncio.sleep(0.01)
        if client.fetch_calls >= 2 and runtime.gateway_open:
            break
    else:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        pytest.fail("WG1000 poll did not reconnect")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert client.aclose_calls >= 1
    assert client.connect_calls >= 1
    assert client.fetch_calls >= 2
    assert sleeps == [0.01]
    assert runtime.active_source() is ActiveSource.WG1000
