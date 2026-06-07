from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from backend.tools.geocode import GeoPoint, geocode


def _nominatim_response(lat: str = "48.8566", lon: str = "2.3522") -> list[dict]:
    return [{"lat": lat, "lon": lon, "display_name": "Paris, France"}]


# ── cache hit ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_geocode_returns_cached_value() -> None:
    mock_cache = AsyncMock()
    mock_cache.get = AsyncMock(return_value='{"lat": 48.8566, "lng": 2.3522, "display_name": "Paris"}')

    with patch("backend.tools.geocode.redis_get_cached", return_value={"lat": 48.8566, "lng": 2.3522, "display_name": "Paris"}):
        result = await geocode("Paris", cache=mock_cache)

    assert result is not None
    assert result.lat == 48.8566
    assert result.lng == 2.3522


# ── cache miss → API call ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_geocode_calls_nominatim_on_cache_miss() -> None:
    with (
        patch("backend.tools.geocode.redis_get_cached", return_value=None),
        patch("backend.tools.geocode.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=_nominatim_response())
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await geocode("Paris", cache=None)

    assert result is not None
    assert isinstance(result, GeoPoint)
    assert result.lat == 48.8566
    assert result.lng == 2.3522


@pytest.mark.asyncio
async def test_geocode_writes_to_cache_after_api_call() -> None:
    set_mock = AsyncMock()
    with (
        patch("backend.tools.geocode.redis_get_cached", return_value=None),
        patch("backend.tools.geocode.redis_set_cached", set_mock),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=_nominatim_response())
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await geocode("Paris", cache=None)

    set_mock.assert_awaited_once()


# ── failure paths ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_geocode_returns_none_on_http_error() -> None:
    with (
        patch("backend.tools.geocode.redis_get_cached", return_value=None),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await geocode("NowherePlace", cache=None)

    assert result is None


@pytest.mark.asyncio
async def test_geocode_returns_none_on_empty_results() -> None:
    with (
        patch("backend.tools.geocode.redis_get_cached", return_value=None),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=[])
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await geocode("Atlantis", cache=None)

    assert result is None
