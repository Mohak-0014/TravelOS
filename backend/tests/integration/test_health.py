import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # db may be "connected" or "unavailable" depending on test DB setup
    assert "db" in body


@pytest.mark.asyncio
async def test_health_has_process_time_header(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "x-process-time" in response.headers
