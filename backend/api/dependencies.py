from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import decode_access_token
from backend.db.base import get_db
from backend.db.models import Trip, User
from backend.tools import get_redis_client

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "NOT_AUTHENTICATED", "message": "Invalid or expired token."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exc

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Account is inactive."},
        )
    return user


async def get_owned_trip(
    trip_id: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Trip:
    """Resolve the ``{trip_id}`` path param to a Trip the caller owns.

    Replaces the per-handler "SELECT trip + ownership check" boilerplate with a
    single dependency. A missing trip and a trip owned by someone else both return
    404 (never 403) so the endpoint doesn't leak which trip ids exist.
    """
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if trip is None or trip.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Trip not found."},
        )
    return trip


async def get_cache() -> AsyncGenerator[Redis, None]:
    """Yield a Redis client for cache-aside reads, closing it when the request ends.

    Redis is best-effort: ``redis_get_cached``/``redis_set_cached`` swallow errors, so
    a downed cache degrades to direct upstream fetches rather than failing the request.
    Tests override this to yield ``None`` (see conftest) to stay hermetic.
    """
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
