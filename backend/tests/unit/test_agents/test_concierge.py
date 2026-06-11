from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.concierge import (
    ConciergeResponse,
    _build_system_prompt,
    _extract_text,
    _load_memory_context,
    _load_trip_context,
    _run_tool,
    ask,
)
from backend.tools.places import Attraction
from backend.tools.restaurants import Restaurant

# ── fixtures ──────────────────────────────────────────────────────────────────


def _mock_trip(
    trip_id: str = "trip-1",
    user_id: str = "user-1",
    city: str = "Paris",
    country: str = "FR",
    lat: float | None = 48.8566,
    lng: float | None = 2.3522,
) -> MagicMock:
    t = MagicMock()
    t.id = trip_id
    t.user_id = user_id
    t.destination_city = city
    t.destination_country = country
    t.latitude = lat
    t.longitude = lng
    t.start_date = MagicMock()
    t.start_date.__str__ = lambda _: "2026-09-01"
    t.end_date = MagicMock()
    t.end_date.__str__ = lambda _: "2026-09-07"
    t.end_date.__sub__ = lambda _, other: MagicMock(days=6)
    t.num_travelers = 2
    t.budget_total = 2000.0
    t.budget_currency = "EUR"
    return t


def _mock_item(title: str = "Eiffel Tower", day: int = 1, kind: str = "activity") -> MagicMock:
    i = MagicMock()
    i.title = title
    i.day_number = day
    i.sort_order = 0
    i.item_type = kind
    return i


def _mock_hotel(name: str = "Hotel Paris") -> MagicMock:
    h = MagicMock()
    h.name = name
    h.star_rating = 4.0
    h.address = "1 Rue de Rivoli, Paris"
    h.price_total = 900.0
    h.price_currency = "EUR"
    return h


def _mock_pref(pace: str = "moderate", tier: str = "mid") -> MagicMock:
    p = MagicMock()
    p.pace = pace
    p.luxury_tier = tier
    p.interests = ["culture", "food"]
    p.food_prefs = ["vegetarian"]
    p.walking_tolerance = "medium"
    return p


def _fake_llm_response(
    text: str = "Here is my answer.", tool_calls: list | None = None
) -> MagicMock:
    r = MagicMock()
    r.content = text
    r.tool_calls = tool_calls or []
    return r


# ── ask() — happy paths ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_answers_without_tool_calls() -> None:
    with (
        patch("backend.agents.concierge._load_trip_context", new_callable=AsyncMock) as mock_ctx,
        patch("backend.agents.concierge._load_preferences", new_callable=AsyncMock) as mock_pref,
        patch("backend.agents.concierge._load_memory_context", new_callable=AsyncMock) as mock_mem,
        patch("backend.agents.concierge._build_llm") as mock_build,
    ):
        mock_ctx.return_value = (_mock_trip(), [_mock_item()], _mock_hotel())
        mock_pref.return_value = _mock_pref()
        mock_mem.return_value = {"past_trips": [], "pref_hits": []}

        llm_instance = MagicMock()
        llm_instance.bind_tools.return_value = llm_instance
        llm_instance.ainvoke = AsyncMock(
            return_value=_fake_llm_response("The Eiffel Tower is open daily.")
        )
        mock_build.return_value = llm_instance

        result = await ask("trip-1", "user-1", "When does the Eiffel Tower open?")

    assert isinstance(result, ConciergeResponse)
    assert "Eiffel Tower" in result.answer
    assert result.sources == []


@pytest.mark.asyncio
async def test_ask_calls_search_attractions_tool() -> None:
    tool_call = {"name": "SearchAttractions", "args": {"lat": 48.85, "lng": 2.35}, "id": "tc-1"}
    final_answer = _fake_llm_response("Here are nearby museums.")

    with (
        patch("backend.agents.concierge._load_trip_context", new_callable=AsyncMock) as mock_ctx,
        patch("backend.agents.concierge._load_preferences", new_callable=AsyncMock) as mock_pref,
        patch("backend.agents.concierge._load_memory_context", new_callable=AsyncMock) as mock_mem,
        patch("backend.agents.concierge._build_llm") as mock_build,
        patch("backend.agents.concierge._run_tool", new_callable=AsyncMock) as mock_tool,
    ):
        mock_ctx.return_value = (_mock_trip(), [], None)
        mock_pref.return_value = None
        mock_mem.return_value = {"past_trips": [], "pref_hits": []}
        mock_tool.return_value = (
            '[{"name": "Louvre"}]',
            [{"type": "attraction", "name": "Louvre"}],
        )

        llm_instance = MagicMock()
        llm_instance.bind_tools.return_value = llm_instance
        llm_instance.ainvoke = AsyncMock(
            side_effect=[_fake_llm_response(tool_calls=[tool_call]), final_answer]
        )
        mock_build.return_value = llm_instance

        result = await ask("trip-1", "user-1", "What museums are near me?")

    mock_tool.assert_awaited_once_with("SearchAttractions", {"lat": 48.85, "lng": 2.35})
    assert len(result.sources) == 1
    assert result.sources[0]["name"] == "Louvre"


@pytest.mark.asyncio
async def test_ask_calls_search_restaurants_tool() -> None:
    tool_call = {
        "name": "SearchRestaurants",
        "args": {"lat": 48.86, "lng": 2.34, "radius_m": 500},
        "id": "tc-2",
    }
    final_answer = _fake_llm_response("There are great bistros nearby.")

    with (
        patch("backend.agents.concierge._load_trip_context", new_callable=AsyncMock) as mock_ctx,
        patch("backend.agents.concierge._load_preferences", new_callable=AsyncMock) as mock_pref,
        patch("backend.agents.concierge._load_memory_context", new_callable=AsyncMock) as mock_mem,
        patch("backend.agents.concierge._build_llm") as mock_build,
        patch("backend.agents.concierge._run_tool", new_callable=AsyncMock) as mock_tool,
    ):
        mock_ctx.return_value = (_mock_trip(), [], None)
        mock_pref.return_value = None
        mock_mem.return_value = {"past_trips": [], "pref_hits": []}
        mock_tool.return_value = (
            '[{"name": "Le Relais"}]',
            [{"type": "restaurant", "name": "Le Relais"}],
        )

        llm_instance = MagicMock()
        llm_instance.bind_tools.return_value = llm_instance
        llm_instance.ainvoke = AsyncMock(
            side_effect=[_fake_llm_response(tool_calls=[tool_call]), final_answer]
        )
        mock_build.return_value = llm_instance

        result = await ask("trip-1", "user-1", "Best restaurant near my hotel?")

    mock_tool.assert_awaited_once_with(
        "SearchRestaurants", {"lat": 48.86, "lng": 2.34, "radius_m": 500}
    )
    assert result.sources[0]["type"] == "restaurant"


@pytest.mark.asyncio
async def test_ask_sources_accumulate_across_rounds() -> None:
    """Two sequential tool calls should both appear in sources."""
    tool_call_1 = {"name": "SearchAttractions", "args": {"lat": 48.0, "lng": 2.0}, "id": "tc-a"}
    tool_call_2 = {"name": "SearchRestaurants", "args": {"lat": 48.0, "lng": 2.0}, "id": "tc-b"}
    final = _fake_llm_response("Done.")
    src_a = [{"type": "attraction", "name": "Museum A"}]
    src_b = [{"type": "restaurant", "name": "Bistro B"}]

    with (
        patch("backend.agents.concierge._load_trip_context", new_callable=AsyncMock) as mock_ctx,
        patch("backend.agents.concierge._load_preferences", new_callable=AsyncMock),
        patch("backend.agents.concierge._load_memory_context", new_callable=AsyncMock) as mock_mem,
        patch("backend.agents.concierge._build_llm") as mock_build,
        patch("backend.agents.concierge._run_tool", new_callable=AsyncMock) as mock_tool,
    ):
        mock_ctx.return_value = (_mock_trip(), [], None)
        mock_mem.return_value = {"past_trips": [], "pref_hits": []}
        mock_tool.side_effect = [("[]", src_a), ("[]", src_b)]

        llm_instance = MagicMock()
        llm_instance.bind_tools.return_value = llm_instance
        llm_instance.ainvoke = AsyncMock(
            side_effect=[
                _fake_llm_response(tool_calls=[tool_call_1]),
                _fake_llm_response(tool_calls=[tool_call_2]),
                final,
            ]
        )
        mock_build.return_value = llm_instance

        result = await ask("trip-1", "user-1", "Museums and restaurants?")

    assert len(result.sources) == 2


@pytest.mark.asyncio
async def test_ask_degrades_on_llm_error() -> None:
    with (
        patch("backend.agents.concierge._load_trip_context", new_callable=AsyncMock) as mock_ctx,
        patch("backend.agents.concierge._load_preferences", new_callable=AsyncMock),
        patch("backend.agents.concierge._load_memory_context", new_callable=AsyncMock) as mock_mem,
        patch("backend.agents.concierge._build_llm") as mock_build,
    ):
        mock_ctx.return_value = (_mock_trip(), [], None)
        mock_mem.return_value = {"past_trips": [], "pref_hits": []}

        llm_instance = MagicMock()
        llm_instance.bind_tools.return_value = llm_instance
        llm_instance.ainvoke = AsyncMock(side_effect=RuntimeError("API timeout"))
        mock_build.return_value = llm_instance

        result = await ask("trip-1", "user-1", "What should I pack?")

    assert isinstance(result, ConciergeResponse)
    assert "sorry" in result.answer.lower()
    assert result.sources == []


# ── _run_tool() ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_tool_attractions_returns_results() -> None:
    places = [
        Attraction(
            osm_id="node/1", name="Louvre", lat=48.86, lng=2.34, kinds="museum", source_ref="node/1"
        )
    ]
    with patch("backend.agents.concierge._search_attractions", new_callable=AsyncMock) as mock_sa:
        mock_sa.return_value = places
        result_text, sources = await _run_tool("SearchAttractions", {"lat": 48.86, "lng": 2.34})

    assert "Louvre" in result_text
    assert len(sources) == 1
    assert sources[0]["type"] == "attraction"
    assert sources[0]["name"] == "Louvre"


@pytest.mark.asyncio
async def test_run_tool_restaurants_returns_results() -> None:
    rests = [
        Restaurant(
            fsq_id="abc",
            name="Le Petit Bistro",
            lat=48.86,
            lng=2.34,
            categories=["French"],
            price_level=2,
            address="10 Rue X",
            source_ref="abc",
        )
    ]
    with patch("backend.agents.concierge._search_restaurants", new_callable=AsyncMock) as mock_sr:
        mock_sr.return_value = rests
        result_text, sources = await _run_tool("SearchRestaurants", {"lat": 48.86, "lng": 2.34})

    assert "Le Petit Bistro" in result_text
    assert sources[0]["type"] == "restaurant"
    assert sources[0]["price_level"] == 2


@pytest.mark.asyncio
async def test_run_tool_unknown_name_returns_empty() -> None:
    result_text, sources = await _run_tool("UnknownTool", {"lat": 0.0, "lng": 0.0})
    assert result_text == "[]"
    assert sources == []


@pytest.mark.asyncio
async def test_run_tool_on_exception_returns_empty() -> None:
    with patch(
        "backend.agents.concierge._search_attractions",
        new_callable=AsyncMock,
        side_effect=Exception("timeout"),
    ):
        result_text, sources = await _run_tool("SearchAttractions", {"lat": 0.0, "lng": 0.0})

    assert result_text == "[]"
    assert sources == []


@pytest.mark.asyncio
async def test_run_tool_uses_default_radius() -> None:
    with patch("backend.agents.concierge._search_attractions", new_callable=AsyncMock) as mock_sa:
        mock_sa.return_value = []
        await _run_tool("SearchAttractions", {"lat": 1.0, "lng": 2.0})

    _, call_kwargs = mock_sa.call_args
    # radius_m arg is positional (3rd)
    assert mock_sa.call_args.args[2] == 2000


# ── _load_trip_context() ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_trip_context_returns_trip_and_items() -> None:
    mock_trip = _mock_trip()
    mock_item_obj = _mock_item()
    mock_hotel_obj = _mock_hotel()

    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = mock_trip

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [mock_item_obj]

    hotel_result = MagicMock()
    hotel_result.scalar_one_or_none.return_value = mock_hotel_obj

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(side_effect=[trip_result, items_result, hotel_result])

    with patch("backend.agents.concierge.AsyncSessionLocal", return_value=mock_session):
        trip, items, hotel = await _load_trip_context("trip-1", "user-1")

    assert trip is mock_trip
    assert len(items) == 1
    assert hotel is mock_hotel_obj


@pytest.mark.asyncio
async def test_load_trip_context_wrong_user_returns_none() -> None:
    mock_trip = _mock_trip(user_id="different-user")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_trip)

    with patch("backend.agents.concierge.AsyncSessionLocal", return_value=mock_session):
        trip, items, hotel = await _load_trip_context("trip-1", "user-1")

    assert trip is None
    assert items == []
    assert hotel is None


@pytest.mark.asyncio
async def test_load_trip_context_on_db_error_returns_none() -> None:
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB unavailable"))
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.agents.concierge.AsyncSessionLocal", return_value=mock_session):
        trip, items, hotel = await _load_trip_context("trip-1", "user-1")

    assert trip is None
    assert items == []
    assert hotel is None


# ── _load_memory_context() ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_memory_context_returns_hits() -> None:
    fake_vector = [0.1] * 384
    past = [{"destination_city": "Rome", "score": 0.9}]

    with (
        patch("backend.agents.concierge.embed_text", return_value=fake_vector),
        patch("backend.agents.concierge.get_qdrant_client") as mock_client_fn,
        patch(
            "backend.agents.concierge.search_trip_memories", new_callable=AsyncMock
        ) as mock_trips,
        patch("backend.agents.concierge.search_preferences", new_callable=AsyncMock) as mock_prefs,
    ):
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client_fn.return_value = mock_client
        mock_trips.return_value = past
        mock_prefs.return_value = []

        result = await _load_memory_context("user-1", "best restaurant near me")

    assert result["past_trips"] == past
    assert result["pref_hits"] == []


@pytest.mark.asyncio
async def test_load_memory_context_degrades_on_qdrant_error() -> None:
    with (
        patch("backend.agents.concierge.embed_text", return_value=[0.0] * 384),
        patch(
            "backend.agents.concierge.get_qdrant_client",
            side_effect=Exception("Qdrant down"),
        ),
    ):
        result = await _load_memory_context("user-1", "any question")

    assert result == {"past_trips": [], "pref_hits": []}


# ── _build_system_prompt() ────────────────────────────────────────────────────


def test_build_system_prompt_includes_grounding_rules() -> None:
    prompt = _build_system_prompt(None, [], None, None, {"past_trips": [], "pref_hits": []})
    assert "Never invent" in prompt
    assert "Grounding rules" in prompt


def test_build_system_prompt_includes_trip_details() -> None:
    trip = _mock_trip(city="Barcelona", country="ES")
    prompt = _build_system_prompt(trip, [], None, None, {"past_trips": [], "pref_hits": []})
    assert "Barcelona" in prompt
    assert "ES" in prompt
    assert "48.8566" in prompt  # coordinates


def test_build_system_prompt_includes_hotel() -> None:
    trip = _mock_trip()
    hotel = _mock_hotel("Grand Hotel")
    prompt = _build_system_prompt(trip, [], hotel, None, {"past_trips": [], "pref_hits": []})
    assert "Grand Hotel" in prompt
    assert "4.0" in prompt


def test_build_system_prompt_includes_itinerary() -> None:
    trip = _mock_trip()
    items = [_mock_item("Louvre", day=1), _mock_item("Seine Cruise", day=2)]
    prompt = _build_system_prompt(trip, items, None, None, {"past_trips": [], "pref_hits": []})
    assert "Louvre" in prompt
    assert "Day 1" in prompt
    assert "Day 2" in prompt


def test_build_system_prompt_includes_preferences() -> None:
    trip = _mock_trip()
    pref = _mock_pref(pace="relaxed", tier="luxury")
    prompt = _build_system_prompt(trip, [], None, pref, {"past_trips": [], "pref_hits": []})
    assert "relaxed" in prompt
    assert "luxury" in prompt
    assert "culture" in prompt


def test_build_system_prompt_includes_past_trips() -> None:
    trip = _mock_trip()
    memory = {
        "past_trips": [{"destination_city": "Rome", "destination_country": "IT"}],
        "pref_hits": [],
    }
    prompt = _build_system_prompt(trip, [], None, None, memory)
    assert "Rome" in prompt
    assert "Past trips" in prompt


def test_build_system_prompt_no_trip_still_renders() -> None:
    prompt = _build_system_prompt(None, [], None, None, {"past_trips": [], "pref_hits": []})
    assert "Trip details not available" in prompt


# ── _extract_text() ───────────────────────────────────────────────────────────


def test_extract_text_from_string_content() -> None:
    msg = MagicMock()
    msg.content = "Hello world"
    assert _extract_text(msg) == "Hello world"


def test_extract_text_from_list_content() -> None:
    msg = MagicMock()
    msg.content = [
        {"type": "text", "text": "Here is"},
        {"type": "tool_use", "id": "x"},
        {"type": "text", "text": " the answer."},
    ]
    assert _extract_text(msg) == "Here is  the answer."


def test_extract_text_ignores_non_text_blocks() -> None:
    msg = MagicMock()
    msg.content = [{"type": "tool_use", "id": "abc"}]
    assert _extract_text(msg) == ""
