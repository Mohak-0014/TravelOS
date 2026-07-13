from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.main import app
from backend.db.base import Base, get_db
from backend.tools.geocode import GeoPoint

# Use an in-memory SQLite database for unit/integration tests that don't need Postgres features.
# For tests that need Postgres-specific features (UUID, JSONB), point at a real test DB.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_MOCK_GEOPOINT = GeoPoint(lat=48.8566, lng=2.3522, display_name="Paris, France")


@pytest.fixture(autouse=True)
def mock_geocode():
    """Prevent tests from hitting real Nominatim — avoids 18-20 min suite runtimes."""
    with patch(
        "backend.tools.geocode.geocode",
        new=AsyncMock(return_value=_MOCK_GEOPOINT),
    ):
        yield


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
