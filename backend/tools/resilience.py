"""Resilience primitives for outbound HTTP — retry with backoff + circuit breaker.

External providers (Nominatim, Open-Meteo, LiteAPI, Duffel, …) fail transiently. The
tools already wrap calls in try/except and degrade to empty/None per the grounding
guardrail; this module adds two layers in front of that fallback:

* **Retry** — a few attempts with exponential backoff on transient errors (network
  failures, timeouts, HTTP 429/5xx) so a momentary blip doesn't surface as degraded.
* **Circuit breaker** — once a provider fails repeatedly, stop hammering it: fail fast
  for a cooldown, then probe with a single trial before restoring traffic.

Both are gated by ``settings.RESILIENCE_ENABLED`` (disabled in tests) and never change
the degraded-state contract: when retries are exhausted or the circuit is open,
``resilient_request`` raises and the caller's existing ``except`` returns the fallback.
"""

import asyncio
import time
from typing import Any

import httpx

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Transient HTTP statuses worth retrying (throttling / server-side, not client errors).
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class CircuitOpenError(Exception):
    """Raised when a request is short-circuited because the breaker is open."""


class ProviderUnavailableError(Exception):
    """Raised when all retry attempts are exhausted for a provider."""


class _RetryableStatus(Exception):
    """Internal marker: the response carried a transient (retryable) status code."""


# Network-level + retryable-status exceptions that should trigger a retry.
_RETRY_ON: tuple[type[Exception], ...] = (
    _RetryableStatus,
    httpx.TimeoutException,
    httpx.TransportError,
)


class CircuitBreaker:
    """Per-provider breaker: CLOSED → (failures) → OPEN → (cooldown) → HALF_OPEN → …

    State is in-process (per worker) — intentionally simple. A Redis-backed breaker
    shared across all workers is a natural future enhancement.
    """

    def __init__(
        self, name: str, *, failure_threshold: int = 5, recovery_timeout: float = 30.0
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if time.monotonic() - self._opened_at >= self.recovery_timeout:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        """Whether a call may proceed right now (``open`` = blocked)."""
        return self.state != "open"

    def record_success(self) -> None:
        if self._failures or self._opened_at is not None:
            logger.info("circuit_closed", provider=self.name)
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        if self.state == "half_open":
            # A failed trial re-opens the circuit for another cooldown.
            self._opened_at = time.monotonic()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.warning("circuit_opened", provider=self.name, failures=self._failures)


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    breaker = _breakers.get(name)
    if breaker is None:
        breaker = CircuitBreaker(name)
        _breakers[name] = breaker
    return breaker


def reset_breakers() -> None:
    """Clear all breaker state — used by tests to stay isolated."""
    _breakers.clear()


async def resilient_request(
    breaker_name: str,
    method: str,
    url: str,
    *,
    timeout: float = 10.0,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    **kwargs: Any,
) -> httpx.Response:
    """Issue an HTTP request with retry + circuit breaker, returning the response.

    Raises ``CircuitOpenError`` when the breaker is open, or the last transient error
    when retries are exhausted, so the caller's existing try/except falls back to
    degraded state. Non-retryable responses (2xx–4xx except 429) are returned as-is.
    """
    method_l = method.lower()

    # Fast path: resilience disabled (tests) → single attempt, no breaker state.
    if not settings.RESILIENCE_ENABLED:
        async with httpx.AsyncClient(timeout=timeout) as client:
            result: httpx.Response = await getattr(client, method_l)(url, **kwargs)
        return result

    breaker = get_breaker(breaker_name)
    if not breaker.allow():
        raise CircuitOpenError(f"circuit open for {breaker_name}")

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp: httpx.Response = await getattr(client, method_l)(url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS:
                raise _RetryableStatus(str(resp.status_code))
            breaker.record_success()
            return resp
        except _RETRY_ON as exc:
            last_exc = exc
            breaker.record_failure()
            logger.warning(
                "resilient_request_retry",
                provider=breaker_name,
                attempt=attempt,
                error=str(exc),
            )
            if attempt < max_attempts:
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))

    assert last_exc is not None
    raise ProviderUnavailableError(
        f"{breaker_name} unavailable after {max_attempts} attempts"
    ) from last_exc
