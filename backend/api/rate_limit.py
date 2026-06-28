"""Shared slowapi limiter.

Defined in its own module so both the app (which registers the 429 handler) and
the routers (which apply ``@limiter.limit(...)`` decorators) can import it without
a circular dependency. Backed by Redis so limits hold across uvicorn workers;
``swallow_errors`` keeps auth available (fail-open) if Redis briefly hiccups.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    enabled=settings.RATE_LIMIT_ENABLED,
    swallow_errors=True,
)
