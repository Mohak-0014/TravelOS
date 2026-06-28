"""Qdrant vector store — upsert and search for user preferences and trip memories."""

from __future__ import annotations

import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_PREFERENCES = "user_preferences"
COLLECTION_TRIPS = "trip_memories"
COLLECTION_FEEDBACK = "user_feedback"
_VECTOR_SIZE = settings.EMBEDDING_DIM  # 384


def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        api_key=settings.QDRANT_API_KEY,
    )


def _point_id(namespace: str, name: str) -> str:
    """Deterministic UUID5 so upserts are idempotent."""
    return str(uuid.uuid5(uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"), f"{namespace}:{name}"))


# ── Collection bootstrap ──────────────────────────────────────────────────────


async def ensure_collections(client: AsyncQdrantClient) -> None:
    """Create the three collections if they do not already exist."""
    for name in (COLLECTION_PREFERENCES, COLLECTION_TRIPS, COLLECTION_FEEDBACK):
        try:
            exists = await client.collection_exists(name)
            if not exists:
                await client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info("qdrant_collection_created", collection=name)
            else:
                logger.debug("qdrant_collection_exists", collection=name)
        except Exception as exc:
            logger.error("qdrant_ensure_collection_failed", collection=name, error=str(exc))
            raise


# ── Upsert ────────────────────────────────────────────────────────────────────


async def upsert_preferences(
    client: AsyncQdrantClient,
    user_id: str,
    vector: list[float],
    payload: dict,  # type: ignore[type-arg]
) -> None:
    """Upsert a user's preference vector. Idempotent — same user_id overwrites."""
    point_id = _point_id("pref", user_id)
    try:
        await client.upsert(
            collection_name=COLLECTION_PREFERENCES,
            points=[
                PointStruct(id=point_id, vector=vector, payload={"user_id": user_id, **payload})
            ],
        )
        logger.info("qdrant_preferences_upserted", user_id=user_id)
    except Exception as exc:
        logger.error("qdrant_upsert_preferences_failed", user_id=user_id, error=str(exc))
        raise


async def upsert_trip_memory(
    client: AsyncQdrantClient,
    trip_id: str,
    user_id: str,
    vector: list[float],
    payload: dict,  # type: ignore[type-arg]
) -> None:
    """Upsert a completed trip as a memory vector. Idempotent — same trip_id overwrites."""
    point_id = _point_id("trip", trip_id)
    try:
        await client.upsert(
            collection_name=COLLECTION_TRIPS,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"trip_id": trip_id, "user_id": user_id, **payload},
                )
            ],
        )
        logger.info("qdrant_trip_memory_upserted", trip_id=trip_id)
    except Exception as exc:
        logger.error("qdrant_upsert_trip_memory_failed", trip_id=trip_id, error=str(exc))
        raise


# ── Search ────────────────────────────────────────────────────────────────────


async def search_trip_memories(
    client: AsyncQdrantClient,
    vector: list[float],
    user_id: str,
    limit: int = 5,
) -> list[dict]:  # type: ignore[type-arg]
    """
    Search trip_memories for the closest past trips belonging to user_id.
    Returns a list of payload dicts with an added 'score' key.
    Degrades gracefully to [] on any error.
    """
    try:
        results = await client.search(
            collection_name=COLLECTION_TRIPS,
            query_vector=vector,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=limit,
            with_payload=True,
        )
        hits = []
        for r in results:
            payload = dict(r.payload or {})
            payload["score"] = round(r.score, 4)
            hits.append(payload)
        logger.info("qdrant_trip_search_ok", user_id=user_id, hits=len(hits))
        return hits
    except Exception as exc:
        logger.warning("qdrant_trip_search_failed", user_id=user_id, error=str(exc))
        return []


async def search_preferences(
    client: AsyncQdrantClient,
    vector: list[float],
    user_id: str,
    limit: int = 5,
) -> list[dict]:  # type: ignore[type-arg]
    """
    Search user_preferences for vectors similar to the given query.
    Degrades gracefully to [] on any error.
    """
    try:
        results = await client.search(
            collection_name=COLLECTION_PREFERENCES,
            query_vector=vector,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=limit,
            with_payload=True,
        )
        hits = []
        for r in results:
            payload = dict(r.payload or {})
            payload["score"] = round(r.score, 4)
            hits.append(payload)
        return hits
    except Exception as exc:
        logger.warning("qdrant_pref_search_failed", user_id=user_id, error=str(exc))
        return []


async def upsert_feedback(
    client: AsyncQdrantClient,
    approval_id: str,
    user_id: str,
    vector: list[float],
    payload: dict,  # type: ignore[type-arg]
) -> None:
    """Upsert a feedback event vector. Idempotent — same approval_id overwrites."""
    point_id = _point_id("feedback", approval_id)
    try:
        await client.upsert(
            collection_name=COLLECTION_FEEDBACK,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"user_id": user_id, **payload},
                )
            ],
        )
        logger.info("qdrant_feedback_upserted", approval_id=approval_id, user_id=user_id)
    except Exception as exc:
        logger.error("qdrant_upsert_feedback_failed", approval_id=approval_id, error=str(exc))
        raise


async def search_feedback(
    client: AsyncQdrantClient,
    vector: list[float],
    user_id: str,
    limit: int = 10,
) -> list[dict]:  # type: ignore[type-arg]
    """
    Search user_feedback for semantically similar past decisions belonging to user_id.
    Returns payload dicts sorted by relevance with an added 'score' key.
    Degrades gracefully to [] on any error.
    """
    try:
        results = await client.search(
            collection_name=COLLECTION_FEEDBACK,
            query_vector=vector,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=limit,
            with_payload=True,
        )
        hits = []
        for r in results:
            payload = dict(r.payload or {})
            payload["score"] = round(r.score, 4)
            hits.append(payload)
        logger.info("qdrant_feedback_search_ok", user_id=user_id, hits=len(hits))
        return hits
    except Exception as exc:
        logger.warning("qdrant_feedback_search_failed", user_id=user_id, error=str(exc))
        return []
