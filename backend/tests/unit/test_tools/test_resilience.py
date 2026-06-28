"""Unit tests for the retry + circuit-breaker resilience layer.

Resilience is disabled globally in conftest, so these tests re-enable it explicitly
(via monkeypatch) and reset breaker state to stay isolated.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.config import settings
from backend.tools.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    ProviderUnavailableError,
    get_breaker,
    reset_breakers,
    resilient_request,
)


def _client_returning(*responses: object) -> AsyncMock:
    """Build a mocked httpx.AsyncClient whose .get/.post yield the given responses."""
    client = AsyncMock()
    client.get = AsyncMock(side_effect=list(responses))
    client.post = AsyncMock(side_effect=list(responses))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ── CircuitBreaker state machine (with a controlled clock) ─────────────────────


def test_breaker_full_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr("backend.tools.resilience.time.monotonic", lambda: clock["t"])

    b = CircuitBreaker("svc", failure_threshold=2, recovery_timeout=30.0)
    assert b.state == "closed"
    assert b.allow() is True

    b.record_failure()
    assert b.state == "closed"  # still under threshold
    b.record_failure()
    assert b.state == "open"  # threshold reached
    assert b.allow() is False

    clock["t"] += 31  # cooldown elapses
    assert b.state == "half_open"
    assert b.allow() is True

    b.record_failure()  # trial fails → re-open
    assert b.state == "open"

    clock["t"] += 31
    assert b.state == "half_open"
    b.record_success()  # trial succeeds → closed
    assert b.state == "closed"


def test_breaker_success_resets_failure_count() -> None:
    b = CircuitBreaker("svc", failure_threshold=3)
    b.record_failure()
    b.record_failure()
    b.record_success()
    # Count was reset, so two more failures must not open it yet.
    b.record_failure()
    b.record_failure()
    assert b.state == "closed"


# ── resilient_request ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retries_transient_status_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RESILIENCE_ENABLED", True)
    reset_breakers()

    client = _client_returning(MagicMock(status_code=503), MagicMock(status_code=200))
    with patch("httpx.AsyncClient", return_value=client):
        result = await resilient_request("svc", "GET", "http://x", base_delay=0.0)

    assert result.status_code == 200
    assert client.get.await_count == 2  # one retry after the 503


@pytest.mark.asyncio
async def test_raises_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RESILIENCE_ENABLED", True)
    reset_breakers()

    client = _client_returning(*[MagicMock(status_code=503) for _ in range(3)])
    with patch("httpx.AsyncClient", return_value=client):
        with pytest.raises(ProviderUnavailableError):
            await resilient_request("svc", "GET", "http://x", max_attempts=3, base_delay=0.0)

    assert client.get.await_count == 3


@pytest.mark.asyncio
async def test_open_circuit_blocks_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RESILIENCE_ENABLED", True)
    reset_breakers()

    breaker = get_breaker("svc")
    for _ in range(breaker.failure_threshold):
        breaker.record_failure()
    assert breaker.state == "open"

    client = _client_returning(MagicMock(status_code=200))
    with patch("httpx.AsyncClient", return_value=client):
        with pytest.raises(CircuitOpenError):
            await resilient_request("svc", "GET", "http://x")

    client.get.assert_not_awaited()  # short-circuited, no HTTP attempted


@pytest.mark.asyncio
async def test_disabled_makes_single_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "RESILIENCE_ENABLED", False)
    reset_breakers()

    client = _client_returning(MagicMock(status_code=503))
    with patch("httpx.AsyncClient", return_value=client):
        result = await resilient_request("svc", "GET", "http://x")

    # Disabled → returns the response as-is with no retry, no breaker involvement.
    assert result.status_code == 503
    assert client.get.await_count == 1
