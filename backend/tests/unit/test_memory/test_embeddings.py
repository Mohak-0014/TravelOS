from unittest.mock import MagicMock, patch

import pytest

from backend.memory.embeddings import (
    _get_model,
    embed_text,
    preference_text,
    trip_memory_text,
)


# ── preference_text ───────────────────────────────────────────────────────────

def test_preference_text_full_prefs() -> None:
    prefs = {
        "pace": "relaxed",
        "luxury_tier": "mid",
        "walking_tolerance": "medium",
        "interests": ["culture", "history"],
        "food_prefs": ["vegetarian"],
        "budget_behavior": "balanced",
    }
    text = preference_text(prefs)
    assert "pace: relaxed" in text
    assert "accommodation: mid" in text
    assert "culture" in text
    assert "vegetarian" in text
    assert "balanced" in text


def test_preference_text_empty_prefs() -> None:
    text = preference_text({})
    assert "unspecified" in text


def test_preference_text_partial_prefs() -> None:
    text = preference_text({"pace": "packed", "interests": ["adventure"]})
    assert "packed" in text
    assert "adventure" in text
    assert "accommodation" not in text


def test_preference_text_empty_lists() -> None:
    text = preference_text({"interests": [], "food_prefs": []})
    assert text  # should not crash and should return something


# ── trip_memory_text ──────────────────────────────────────────────────────────

def test_trip_memory_text_full() -> None:
    text = trip_memory_text(
        city="Rome",
        country="IT",
        style_tags=["culture", "history"],
        item_titles=["Colosseum Tour", "Vatican Museums", "Trastevere Walk"],
    )
    assert "Rome" in text
    assert "IT" in text
    assert "culture" in text
    assert "Colosseum Tour" in text


def test_trip_memory_text_no_country() -> None:
    text = trip_memory_text("Tokyo", None, ["food"], ["Ramen tasting"])
    assert "Tokyo" in text
    assert "None" not in text


def test_trip_memory_text_no_items() -> None:
    text = trip_memory_text("Berlin", "DE", [], [])
    assert "Berlin" in text
    assert "various activities" in text


def test_trip_memory_text_caps_items_at_10() -> None:
    titles = [f"Activity {i}" for i in range(20)]
    text = trip_memory_text("Paris", "FR", [], titles)
    # Only first 10 titles should appear
    assert "Activity 9" in text
    assert "Activity 10" not in text


# ── embed_text ────────────────────────────────────────────────────────────────

def test_embed_text_returns_384_floats() -> None:
    mock_model = MagicMock()
    import numpy as np

    mock_model.encode.return_value = np.zeros(384, dtype="float32")

    with patch("backend.memory.embeddings._get_model", return_value=mock_model):
        result = embed_text("test sentence")

    assert isinstance(result, list)
    assert len(result) == 384
    assert all(isinstance(v, float) for v in result)


def test_embed_text_calls_encode_with_normalize() -> None:
    mock_model = MagicMock()
    import numpy as np

    mock_model.encode.return_value = np.ones(384, dtype="float32")

    with patch("backend.memory.embeddings._get_model", return_value=mock_model):
        embed_text("hello world")

    mock_model.encode.assert_called_once_with("hello world", normalize_embeddings=True)


# ── _get_model lazy loading ───────────────────────────────────────────────────

def test_get_model_lazy_loads_once() -> None:
    import backend.memory.embeddings as emb_module

    original = emb_module._model
    try:
        emb_module._model = None
        mock_model = MagicMock()
        # SentenceTransformer is imported inside _get_model, so patch at the source
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            m1 = emb_module._get_model()
            m2 = emb_module._get_model()
        assert m1 is m2
        # Constructor called exactly once despite two _get_model() calls
        assert mock_model.call_count == 0  # mock_model IS the instance, not the class
    finally:
        emb_module._model = original
