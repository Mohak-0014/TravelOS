import time

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.core.config import settings
from backend.core.logging import configure_logging, get_logger
from backend.db.base import AsyncSessionLocal

configure_logging()
logger = get_logger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1,
    )

_is_prod = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="TravelOS API",
    version="0.1.0",
    description="AI-native multi-agent travel operating system",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time"] = str(elapsed_ms)
    return response


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    # DB
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error("health_check_db_failed", error=str(exc))
        db_status = "unavailable"

    # Redis
    try:
        import redis.asyncio as aioredis  # noqa: PLC0415

        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)  # type: ignore[no-untyped-call]
        await r.ping()
        await r.aclose()
        redis_status = "connected"
    except Exception as exc:
        logger.error("health_check_redis_failed", error=str(exc))
        redis_status = "unavailable"

    # Qdrant
    try:
        from qdrant_client import AsyncQdrantClient  # noqa: PLC0415

        qc = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY,
            timeout=3,
        )
        await qc.get_collections()
        await qc.close()
        qdrant_status = "connected"
    except Exception as exc:
        logger.error("health_check_qdrant_failed", error=str(exc))
        qdrant_status = "unavailable"

    return {"status": "ok", "db": db_status, "redis": redis_status, "qdrant": qdrant_status}


from backend.api.routers.approvals import router as approvals_router  # noqa: E402
from backend.api.routers.auth import preferences_router  # noqa: E402
from backend.api.routers.auth import router as auth_router  # noqa: E402
from backend.api.routers.concierge import router as concierge_router  # noqa: E402
from backend.api.routers.share import router as share_router  # noqa: E402
from backend.api.routers.trips import router as trips_router  # noqa: E402

app.include_router(auth_router)
app.include_router(preferences_router)
app.include_router(trips_router)
app.include_router(approvals_router)
app.include_router(concierge_router)
app.include_router(share_router)


@app.on_event("startup")
async def _init_qdrant_collections() -> None:
    from backend.memory.semantic import ensure_collections, get_qdrant_client  # noqa: PLC0415

    client = get_qdrant_client()
    try:
        await ensure_collections(client)
        logger.info("qdrant_collections_ready")
    except Exception as exc:
        logger.warning("qdrant_collections_init_failed", error=str(exc))
    finally:
        await client.close()
