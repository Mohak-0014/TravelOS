"""
Embedding generation using sentence-transformers all-MiniLM-L6-v2 (384-dim).

MUST only be called from Celery tasks or the trip graph (which runs inside
a Celery task) — never from FastAPI request handlers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.core.config import settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)

# Lazy singleton — loaded once per worker process on first call
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        logger.info("embedding_model_loading", model=settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("embedding_model_ready", dim=settings.EMBEDDING_DIM)
    return _model


def embed_text(text: str) -> list[float]:
    """Return a 384-dim embedding vector for the given text string."""
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


# ── Text builders ─────────────────────────────────────────────────────────────

def preference_text(prefs: dict) -> str:  # type: ignore[type-arg]
    """Build a short natural-language summary of user preferences for embedding."""
    parts: list[str] = []
    if prefs.get("pace"):
        parts.append(f"pace: {prefs['pace']}")
    if prefs.get("luxury_tier"):
        parts.append(f"accommodation: {prefs['luxury_tier']}")
    if prefs.get("walking_tolerance"):
        parts.append(f"walking: {prefs['walking_tolerance']}")
    interests = prefs.get("interests") or []
    if interests:
        parts.append(f"interests: {', '.join(interests)}")
    food = prefs.get("food_prefs") or []
    if food:
        parts.append(f"food: {', '.join(food)}")
    if prefs.get("budget_behavior"):
        parts.append(f"budget: {prefs['budget_behavior']}")
    return "Traveler profile — " + "; ".join(parts) if parts else "Traveler profile — unspecified"


def trip_memory_text(
    city: str,
    country: str | None,
    style_tags: list[str],
    item_titles: list[str],
) -> str:
    """Build a natural-language summary of a completed trip for embedding."""
    dest = f"{city}, {country}" if country else city
    tags_str = ", ".join(style_tags) if style_tags else "mixed"
    items_str = "; ".join(item_titles[:10]) if item_titles else "various activities"
    return f"Trip to {dest}. Style: {tags_str}. Activities included: {items_str}."
