from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.memory.semantic import (
    COLLECTION_PREFERENCES,
    COLLECTION_TRIPS,
    _point_id,
    ensure_collections,
    search_preferences,
    search_trip_memories,
    upsert_preferences,
    upsert_trip_memory,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_client() -> AsyncMock:
    client = AsyncMock()
    client.collection_exists = AsyncMock(return_value=False)
    client.create_collection = AsyncMock()
    client.upsert = AsyncMock()
    client.search = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


def _scored_point(payload: dict, score: float = 0.9) -> MagicMock:  # type: ignore[type-arg]
    p = MagicMock()
    p.payload = payload
    p.score = score
    return p


def _fake_vector(dim: int = 384) -> list[float]:
    return [0.1] * dim


# ── _point_id ─────────────────────────────────────────────────────────────────

def test_point_id_is_deterministic() -> None:
    id1 = _point_id("pref", "user-1")
    id2 = _point_id("pref", "user-1")
    assert id1 == id2


def test_point_id_differs_by_namespace() -> None:
    assert _point_id("pref", "user-1") != _point_id("trip", "user-1")


def test_point_id_differs_by_name() -> None:
    assert _point_id("pref", "user-1") != _point_id("pref", "user-2")


def test_point_id_is_valid_uuid_string() -> None:
    import uuid

    id_str = _point_id("trip", "trip-abc")
    uuid.UUID(id_str)  # raises ValueError if invalid


# ── ensure_collections ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ensure_collections_creates_when_missing() -> None:
    client = _mock_client()
    client.collection_exists = AsyncMock(return_value=False)

    await ensure_collections(client)

    assert client.create_collection.await_count == 2
    created_names = {c.kwargs["collection_name"] for c in client.create_collection.call_args_list}
    assert COLLECTION_PREFERENCES in created_names
    assert COLLECTION_TRIPS in created_names


@pytest.mark.asyncio
async def test_ensure_collections_skips_when_exists() -> None:
    client = _mock_client()
    client.collection_exists = AsyncMock(return_value=True)

    await ensure_collections(client)

    client.create_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_collections_raises_on_error() -> None:
    client = _mock_client()
    client.collection_exists = AsyncMock(side_effect=Exception("connection refused"))

    with pytest.raises(Exception, match="connection refused"):
        await ensure_collections(client)


# ── upsert_preferences ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_preferences_calls_upsert() -> None:
    client = _mock_client()
    vector = _fake_vector()
    payload = {"pace": "relaxed", "text_summary": "relaxed traveler"}

    await upsert_preferences(client, "user-1", vector, payload)

    client.upsert.assert_awaited_once()
    call_kwargs = client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION_PREFERENCES
    point = call_kwargs["points"][0]
    assert point.payload["user_id"] == "user-1"
    assert point.payload["pace"] == "relaxed"


@pytest.mark.asyncio
async def test_upsert_preferences_idempotent_same_id() -> None:
    client = _mock_client()
    vector = _fake_vector()

    await upsert_preferences(client, "user-1", vector, {})
    await upsert_preferences(client, "user-1", vector, {})

    ids = [c.kwargs["points"][0].id for c in client.upsert.call_args_list]
    assert ids[0] == ids[1]


@pytest.mark.asyncio
async def test_upsert_preferences_raises_on_qdrant_error() -> None:
    client = _mock_client()
    client.upsert = AsyncMock(side_effect=Exception("qdrant error"))

    with pytest.raises(Exception, match="qdrant error"):
        await upsert_preferences(client, "user-1", _fake_vector(), {})


# ── upsert_trip_memory ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_trip_memory_calls_upsert() -> None:
    client = _mock_client()
    vector = _fake_vector()
    payload = {"destination_city": "Paris", "text_summary": "Great trip to Paris"}

    await upsert_trip_memory(client, "trip-1", "user-1", vector, payload)

    client.upsert.assert_awaited_once()
    call_kwargs = client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION_TRIPS
    point = call_kwargs["points"][0]
    assert point.payload["trip_id"] == "trip-1"
    assert point.payload["user_id"] == "user-1"
    assert point.payload["destination_city"] == "Paris"


@pytest.mark.asyncio
async def test_upsert_trip_memory_idempotent() -> None:
    client = _mock_client()
    vector = _fake_vector()

    await upsert_trip_memory(client, "trip-1", "user-1", vector, {})
    await upsert_trip_memory(client, "trip-1", "user-1", vector, {})

    ids = [c.kwargs["points"][0].id for c in client.upsert.call_args_list]
    assert ids[0] == ids[1]


# ── search_trip_memories ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_trip_memories_returns_hits() -> None:
    client = _mock_client()
    client.search = AsyncMock(
        return_value=[
            _scored_point({"trip_id": "t1", "user_id": "u1", "destination_city": "Rome"}, 0.95),
            _scored_point({"trip_id": "t2", "user_id": "u1", "destination_city": "Paris"}, 0.82),
        ]
    )

    hits = await search_trip_memories(client, _fake_vector(), "u1", limit=5)

    assert len(hits) == 2
    assert hits[0]["destination_city"] == "Rome"
    assert hits[0]["score"] == 0.95
    assert hits[1]["destination_city"] == "Paris"


@pytest.mark.asyncio
async def test_search_trip_memories_filters_by_user() -> None:
    client = _mock_client()
    client.search = AsyncMock(return_value=[])

    await search_trip_memories(client, _fake_vector(), "user-42", limit=3)

    call_kwargs = client.search.call_args.kwargs
    assert call_kwargs["collection_name"] == COLLECTION_TRIPS
    assert call_kwargs["limit"] == 3
    filt = call_kwargs["query_filter"]
    assert filt.must[0].match.value == "user-42"


@pytest.mark.asyncio
async def test_search_trip_memories_degrades_on_error() -> None:
    client = _mock_client()
    client.search = AsyncMock(side_effect=Exception("qdrant unavailable"))

    hits = await search_trip_memories(client, _fake_vector(), "user-1")

    assert hits == []


# ── search_preferences ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_preferences_returns_hits() -> None:
    client = _mock_client()
    client.search = AsyncMock(
        return_value=[_scored_point({"user_id": "u1", "pace": "relaxed"}, 0.88)]
    )

    hits = await search_preferences(client, _fake_vector(), "u1")

    assert len(hits) == 1
    assert hits[0]["pace"] == "relaxed"
    assert hits[0]["score"] == 0.88


@pytest.mark.asyncio
async def test_search_preferences_degrades_on_error() -> None:
    client = _mock_client()
    client.search = AsyncMock(side_effect=Exception("timeout"))

    hits = await search_preferences(client, _fake_vector(), "user-1")

    assert hits == []
