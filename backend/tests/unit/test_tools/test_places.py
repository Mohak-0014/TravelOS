from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from backend.tools.places import Attraction, _element_to_attraction, search_attractions


# ── helpers ──────────────────────────────────────────────────────────────────

def _node(osm_id: int = 111, name: str = "Louvre Museum", tag: str = "museum") -> dict:
    return {
        "type": "node",
        "id": osm_id,
        "lat": 48.8606,
        "lon": 2.3376,
        "tags": {"name": name, "tourism": tag},
    }


def _way(osm_id: int = 222, name: str = "Eiffel Tower", tag: str = "attraction") -> dict:
    return {
        "type": "way",
        "id": osm_id,
        "center": {"lat": 48.8584, "lon": 2.2945},
        "tags": {"name": name, "tourism": tag},
    }


def _overpass_payload(elements: list[dict]) -> dict:
    return {"elements": elements}


def _mock_client(payload: dict):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=payload)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ── _element_to_attraction unit tests ────────────────────────────────────────

def test_node_element_parsed_correctly() -> None:
    result = _element_to_attraction(_node())
    assert result is not None
    assert result.name == "Louvre Museum"
    assert result.osm_id == "node/111"
    assert result.lat == 48.8606
    assert result.lng == 2.3376
    assert result.kinds == "museum"
    assert result.source_provider == "overpass"
    assert result.source_ref == "node/111"


def test_way_element_uses_center_coordinates() -> None:
    result = _element_to_attraction(_way())
    assert result is not None
    assert result.lat == 48.8584
    assert result.lng == 2.2945
    assert result.osm_id == "way/222"


def test_element_without_name_returns_none() -> None:
    el = {"type": "node", "id": 999, "lat": 0.0, "lon": 0.0, "tags": {"tourism": "museum"}}
    assert _element_to_attraction(el) is None


def test_element_without_coordinates_returns_none() -> None:
    el = {"type": "node", "id": 999, "tags": {"name": "Ghost Place", "tourism": "museum"}}
    assert _element_to_attraction(el) is None


def test_historic_tag_used_when_tourism_absent() -> None:
    el = {
        "type": "node", "id": 1, "lat": 48.0, "lon": 2.0,
        "tags": {"name": "Roman Ruins", "historic": "ruins"},
    }
    result = _element_to_attraction(el)
    assert result is not None
    assert result.kinds == "ruins"


def test_website_tag_extracted() -> None:
    el = {
        "type": "node", "id": 1, "lat": 48.0, "lon": 2.0,
        "tags": {"name": "Museum", "tourism": "museum", "website": "https://example.com"},
    }
    result = _element_to_attraction(el)
    assert result is not None
    assert result.website == "https://example.com"


# ── search_attractions integration (mocked HTTP) ─────────────────────────────

@pytest.mark.asyncio
async def test_search_returns_attractions_from_overpass() -> None:
    payload = _overpass_payload([_node(), _way()])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 2
    assert all(isinstance(r, Attraction) for r in results)


@pytest.mark.asyncio
async def test_search_returns_cached_value() -> None:
    cached_data = [_node()]
    cached_attractions = [_element_to_attraction(cached_data[0]).model_dump()]

    with patch("backend.tools.places.redis_get_cached", return_value=cached_attractions):
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 1
    assert results[0].name == "Louvre Museum"


@pytest.mark.asyncio
async def test_search_writes_results_to_cache() -> None:
    set_mock = AsyncMock()
    payload = _overpass_payload([_node()])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", set_mock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        await search_attractions(48.85, 2.35, cache=None)

    set_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error() -> None:
    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        results = await search_attractions(0.0, 0.0, cache=None)

    assert results == []


@pytest.mark.asyncio
async def test_search_skips_unnamed_elements() -> None:
    unnamed = {"type": "node", "id": 1, "lat": 48.0, "lon": 2.0, "tags": {"tourism": "museum"}}
    payload = _overpass_payload([unnamed, _node(osm_id=2, name="Named Place")])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 1
    assert results[0].name == "Named Place"


@pytest.mark.asyncio
async def test_search_respects_limit() -> None:
    elements = [_node(osm_id=i, name=f"Place {i}") for i in range(30)]
    payload = _overpass_payload(elements)

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, limit=10, cache=None)

    assert len(results) == 10
