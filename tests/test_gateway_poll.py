"""WG1000 poll reconnects after a dropped WebSocket."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pyatmos_wg1000.protocol.data import InfoDump, InfoItem

from custom_components.atmos.gateway_poll import await_cancelled, login_gateway, pull_gateway
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


def _title_dump(ac16: int = 0) -> InfoDump:
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


class _FakeClient:
    """Fails the first Info fetch, then accepts a re-login and later dumps."""

    def __init__(
        self,
        *,
        login_results: list[_LoginResult] | None = None,
        connect_errors: list[BaseException | None] | None = None,
        circuit_errors: int = 0,
    ) -> None:
        self.fetch_calls = 0
        self.connect_calls = 0
        self.aclose_calls = 0
        self.write_registers = AsyncMock()
        self._login_results = list(login_results or [_LoginResult()])
        self._connect_errors = list(connect_errors or [])
        self._circuit_errors_left = circuit_errors

    async def fetch_info(self, ac16: int = 0) -> InfoDump:
        self.fetch_calls += 1
        if self.fetch_calls == 1:
            raise ConnectionError("no close frame received or sent")
        return _title_dump(ac16)

    async def read_registers(self, register_ids: Any, **kwargs: Any) -> tuple[()]:
        if self._circuit_errors_left > 0:
            self._circuit_errors_left -= 1
            raise RuntimeError("circuit read failed")
        return ()

    async def connect(self) -> None:
        self.connect_calls += 1
        if self._connect_errors:
            err = self._connect_errors.pop(0)
            if err is not None:
                raise err

    async def hello(self) -> int:
        return 0

    async def login(self, username: str, password: str, *, stay: bool = False) -> _LoginResult:
        assert username == "user"
        assert password == _TEST_PASSWORD
        assert stay is True
        if self._login_results:
            return self._login_results.pop(0)
        return _LoginResult()

    async def aclose(self) -> None:
        self.aclose_calls += 1


async def _run_until_reconnected(client: _FakeClient, runtime: AtmosRuntime, **kwargs: Any) -> list[float]:
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
            info_interval=0.01,
            circuit_schedule={0.05: ()},
            reconnect_initial=0.01,
            reconnect_max=0.04,
            sleep=_sleep,
            **kwargs,
        )
    )
    for _ in range(400):
        await asyncio.sleep(0.01)
        if client.fetch_calls >= 2 and runtime.gateway_open and runtime.info_groups:
            break
    else:
        task.cancel()
        await await_cancelled(task)
        pytest.fail(
            "WG1000 poll did not reconnect "
            f"(fetch={client.fetch_calls} open={runtime.gateway_open} groups={len(runtime.info_groups)})"
        )

    task.cancel()
    await await_cancelled(task)
    return sleeps


@pytest.mark.asyncio
async def test_await_cancelled_on_success_and_cancel() -> None:
    """``await_cancelled`` returns for finished and cancelled tasks."""

    async def _ok() -> None:
        return None

    done = asyncio.create_task(_ok())
    await await_cancelled(done)

    pending = asyncio.create_task(asyncio.sleep(60))
    pending.cancel()
    await await_cancelled(pending)


@pytest.mark.asyncio
async def test_login_gateway_returns_login_result() -> None:
    """Bootstrap login goes through connect, hello, and stay=True login."""
    client = _FakeClient()
    result = await login_gateway(client, "user", _TEST_PASSWORD)  # type: ignore[arg-type]
    assert result.logged_in
    assert client.connect_calls == 1


@pytest.mark.asyncio
async def test_pull_gateway_reconnects_after_transport_drop() -> None:
    """After ConnectionError the session is rebuilt and polling resumes."""
    runtime = AtmosRuntime(SourceConfig(serial=False, wg1000=True, fallback_after=10))
    client = _FakeClient()
    sleeps = await _run_until_reconnected(client, runtime)

    assert client.aclose_calls >= 1
    assert client.connect_calls >= 1
    assert client.fetch_calls >= 2
    assert sleeps == [0.01]
    assert runtime.info_groups
    assert runtime.active_source() is ActiveSource.WG1000


@pytest.mark.asyncio
async def test_pull_gateway_retries_rejected_then_failed_reconnect() -> None:
    """Rejected login and connect errors back off until a session succeeds."""
    runtime = AtmosRuntime(SourceConfig(serial=False, wg1000=True, fallback_after=10))
    client = _FakeClient(
        login_results=[
            _LoginResult(role=0, blocked=True, retry_after_s=30),
            _LoginResult(),
        ],
        connect_errors=[ConnectionError("gateway down"), None],
        circuit_errors=1,
    )
    sleeps = await _run_until_reconnected(client, runtime)

    assert sleeps[:3] == [0.01, 0.02, 0.04]
    assert client.fetch_calls >= 2
    assert runtime.info_groups
    assert runtime.active_source() is ActiveSource.WG1000


@pytest.mark.asyncio
async def test_pull_gateway_cancel_during_reconnect_login() -> None:
    """Cancellation while re-login is in flight exits cleanly."""
    runtime = AtmosRuntime(SourceConfig(serial=False, wg1000=True, fallback_after=10))
    client = _FakeClient()
    started = asyncio.Event()

    async def _hang_connect() -> None:
        client.connect_calls += 1
        started.set()
        await asyncio.Event().wait()

    client.connect = _hang_connect  # type: ignore[method-assign]

    async def _sleep(delay: float) -> None:
        return None

    task = asyncio.create_task(
        pull_gateway(
            client,  # type: ignore[arg-type]
            runtime,
            _FakeCatalog(),  # type: ignore[arg-type]
            (),
            username="user",
            password=_TEST_PASSWORD,
            info_interval=0.01,
            circuit_schedule={0.05: ()},
            reconnect_initial=0.01,
            sleep=_sleep,
        )
    )
    await started.wait()
    task.cancel()
    await await_cancelled(task)
    assert runtime.gateway_open is False
