import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.core.config import settings
from backend.core.logging import configure_logging, get_logger
from backend.db.base import AsyncSessionLocal

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="TravelOS API",
    version="0.1.0",
    description="AI-native multi-agent travel operating system",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error("health_check_db_failed", error=str(exc))
        db_status = "unavailable"

    return {"status": "ok", "db": db_status}


from backend.api.routers.approvals import router as approvals_router  # noqa: E402
from backend.api.routers.auth import preferences_router  # noqa: E402
from backend.api.routers.auth import router as auth_router  # noqa: E402
from backend.api.routers.concierge import router as concierge_router  # noqa: E402
from backend.api.routers.trips import router as trips_router  # noqa: E402

app.include_router(auth_router)
app.include_router(preferences_router)
app.include_router(trips_router)
app.include_router(approvals_router)
app.include_router(concierge_router)
