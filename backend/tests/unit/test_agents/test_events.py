"""Unit tests for the Local Events agent and events tool."""

from __future__ import annotations

from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.events import (
    _cosine_similarity,
    _find_open_evening_slots,
    _haversine_m,
    _score_events,
)
from backend.tools.events import (
    EventOffer,
    _parse_eb_event,
    _parse_tm_event,
    fetch_events,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _tm_raw(
    *,
    name: str = "Rock Concert",
    date_str: str = "2026-07-10",
    time_str: str = "20:00:00",
    venue: str = "O2 Arena",
    lat: str = "51.5033",
    lng: str = "-0.0030",
    segment: str = "Music",
    price_min: float = 50.0,
    price_max: float = 150.0,
) -> dict:
    return {
        "name": name,
        "dates": {"start": {"localDate": date_str, "localTime": time_str}},
        "_embedded": {
            "venues": [
                {
                    "name": venue,
                    "location": {"latitude": lat, "longitude": lng},
                }
            ]
        },
        "classifications": [{"segment": {"name": segment}}],
        "priceRanges": [{"min": price_min, "max": price_max, "currency": "GBP"}],
        "images": [{"ratio": "16_9", "url": "https://img.example.com/event.jpg"}],
        "url": "https://www.ticketmaster.com/event/123",
    }


def _eb_raw(
    *,
    name: str = "Food Festival",
    utc: str = "2026-07-11T14:00:00Z",
    category_id: str = "101",
    venue_name: str = "Victoria Park",
    lat: str = "51.5370",
    lng: str = "-0.0397",
) -> dict:
    return {
        "name": {"text": name},
        "start": {"utc": utc},
        "category_id": category_id,
        "venue": {
            "name": venue_name,
            "address": {"latitude": lat, "longitude": lng},
        },
        "url": "https://www.eventbrite.com/e/food-festival-123",
        "logo": {"original": {"url": "https://img.example.com/food.jpg"}},
    }


def _event(
    *,
    name: str = "Test Event",
    event_date: date = date(2026, 7, 10),
    start_time: time | None = time(20, 0),
    venue: str = "Test Venue",
    lat: float | None = 51.5,
    lng: float | None = -0.1,
    category: str = "Music",
    source: str = "ticketmaster",
) -> EventOffer:
    return EventOffer(
        name=name,
        event_date=event_date,
        start_time=start_time,
        venue_name=venue,
        lat=lat,
        lng=lng,
        category=category,
        source=source,
        url="https://example.com",
    )


# ── _parse_tm_event ───────────────────────────────────────────────────────────


def test_parse_tm_event_happy_path() -> None:
    offer = _parse_tm_event(_tm_raw())
    assert offer is not None
    assert offer.name == "Rock Concert"
    assert offer.event_date == date(2026, 7, 10)
    assert offer.start_time == time(20, 0)
    assert offer.venue_name == "O2 Arena"
    assert offer.lat == pytest.approx(51.5033)
    assert offer.lng == pytest.approx(-0.003)
    assert offer.category == "Music"
    assert offer.price_min == 50.0
    assert offer.price_max == 150.0
    assert offer.price_currency == "GBP"
    assert offer.source == "ticketmaster"
    assert offer.image_url is not None


def test_parse_tm_event_missing_name_returns_none() -> None:
    raw = _tm_raw()
    raw["name"] = ""
    assert _parse_tm_event(raw) is None


def test_parse_tm_event_missing_date_returns_none() -> None:
    raw = _tm_raw()
    raw["dates"]["start"]["localDate"] = None
    assert _parse_tm_event(raw) is None


def test_parse_tm_event_missing_coords_still_parses() -> None:
    raw = _tm_raw()
    raw["_embedded"]["venues"][0]["location"] = {}
    offer = _parse_tm_event(raw)
    assert offer is not None
    assert offer.lat is None
    assert offer.lng is None


# ── _parse_eb_event ───────────────────────────────────────────────────────────


def test_parse_eb_event_happy_path() -> None:
    offer = _parse_eb_event(_eb_raw())
    assert offer is not None
    assert offer.name == "Food Festival"
    assert offer.event_date == date(2026, 7, 11)
    assert offer.category == "Food & Drink"
    assert offer.source == "eventbrite"
    assert offer.lat == pytest.approx(51.537)
    assert offer.lng == pytest.approx(-0.0397)


def test_parse_eb_event_non_travel_category_returns_none() -> None:
    raw = _eb_raw(category_id="108")  # Business & Professional
    assert _parse_eb_event(raw) is None


def test_parse_eb_event_missing_name_returns_none() -> None:
    raw = _eb_raw()
    raw["name"]["text"] = ""
    assert _parse_eb_event(raw) is None


def test_parse_eb_event_missing_utc_returns_none() -> None:
    raw = _eb_raw()
    raw["start"]["utc"] = ""
    assert _parse_eb_event(raw) is None


# ── fetch_events (merge + dedup) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_events_merges_and_deduplicates() -> None:
    tm_event = _event(venue="Wembley", event_date=date(2026, 7, 10), source="ticketmaster")
    eb_event_same = _event(
        name="Same Event EB", venue="Wembley", event_date=date(2026, 7, 10), source="eventbrite"
    )
    eb_event_unique = _event(
        name="Unique EB Event", venue="Hyde Park", event_date=date(2026, 7, 11), source="eventbrite"
    )

    with (
        patch(
            "backend.tools.events.fetch_ticketmaster",
            new_callable=AsyncMock,
            return_value=[tm_event],
        ),
        patch(
            "backend.tools.events.fetch_eventbrite",
            new_callable=AsyncMock,
            return_value=[eb_event_same, eb_event_unique],
        ),
    ):
        result = await fetch_events(
            city="London",
            country="GB",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            ticketmaster_key="fake-key",
            eventbrite_token="fake-token",
        )

    assert len(result) == 2
    # Ticketmaster record wins for Wembley collision
    wembley = next(e for e in result if e.venue_name == "Wembley")
    assert wembley.source == "ticketmaster"
    # Unique EB event also present
    assert any(e.venue_name == "Hyde Park" for e in result)
    # Sorted by date
    assert result[0].event_date <= result[1].event_date


@pytest.mark.asyncio
async def test_fetch_events_degrades_if_one_source_fails() -> None:
    tm_event = _event(venue="O2", event_date=date(2026, 7, 10), source="ticketmaster")

    with (
        patch(
            "backend.tools.events.fetch_ticketmaster",
            new_callable=AsyncMock,
            return_value=[tm_event],
        ),
        patch(
            "backend.tools.events.fetch_eventbrite",
            new_callable=AsyncMock,
            side_effect=Exception("API down"),
        ),
    ):
        result = await fetch_events(
            city="London",
            country="GB",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            ticketmaster_key="fake-key",
            eventbrite_token="fake-token",
        )

    # Eventbrite failure is caught by gather(return_exceptions=True); TM results survive
    assert len(result) == 1
    assert result[0].source == "ticketmaster"


# ── _haversine_m ──────────────────────────────────────────────────────────────


def test_haversine_same_point_is_zero() -> None:
    assert _haversine_m(51.5, -0.1, 51.5, -0.1) == pytest.approx(0.0, abs=1.0)


def test_haversine_known_distance() -> None:
    # London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ≈ 340 km
    dist = _haversine_m(51.5074, -0.1278, 48.8566, 2.3522)
    assert 330_000 < dist < 350_000


def test_haversine_short_distance() -> None:
    # ~500m south along meridian
    dist = _haversine_m(51.5, 0.0, 51.4955, 0.0)
    assert 480 < dist < 520


# ── _cosine_similarity ────────────────────────────────────────────────────────


def test_cosine_similarity_identical_vectors() -> None:
    v = [1.0, 0.0, 0.5]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert _cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector() -> None:
    assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


# ── _score_events ─────────────────────────────────────────────────────────────


def test_score_events_orders_by_relevance() -> None:
    music_event = _event(name="Jazz Night", category="Music")
    sports_event = _event(name="Football Match", category="Sports", venue="Stadium")

    # embed_text is imported lazily inside _score_events; patch at its source module
    def fake_embed(text: str) -> list[float]:
        if "music" in text.lower() or "jazz" in text.lower():
            return [1.0, 0.0]
        return [0.0, 1.0]

    with patch("backend.memory.embeddings.embed_text", side_effect=fake_embed):
        result = _score_events([sports_event, music_event], "jazz music concerts")

    assert result[0][0].name == "Jazz Night"
    assert result[0][1] > result[1][1]


def test_score_events_falls_back_on_embedding_error() -> None:
    events = [_event(name="A"), _event(name="B")]

    with patch("backend.memory.embeddings.embed_text", side_effect=RuntimeError("no model")):
        result = _score_events(events, "anything")

    assert len(result) == 2
    assert all(score == 0.5 for _, score in result)


# ── _find_open_evening_slots ──────────────────────────────────────────────────


def test_open_slots_day_with_evening_item_excluded() -> None:
    itinerary = [
        {
            "item_date": "2026-07-10",
            "day_number": 1,
            "start_time": "20:00",
        }
    ]
    slots = _find_open_evening_slots(
        itinerary, trip_start=date(2026, 7, 10), trip_end=date(2026, 7, 11)
    )
    dates = [s[1] for s in slots]
    assert date(2026, 7, 10) not in dates  # has 20:00 item
    assert date(2026, 7, 11) in dates      # no evening item


def test_open_slots_day_with_only_morning_item_is_open() -> None:
    itinerary = [
        {
            "item_date": "2026-07-10",
            "day_number": 1,
            "start_time": "09:00",
        }
    ]
    slots = _find_open_evening_slots(
        itinerary, trip_start=date(2026, 7, 10), trip_end=date(2026, 7, 10)
    )
    assert len(slots) == 1
    assert slots[0][1] == date(2026, 7, 10)


def test_open_slots_empty_itinerary_all_days_open() -> None:
    slots = _find_open_evening_slots(
        [], trip_start=date(2026, 7, 10), trip_end=date(2026, 7, 12)
    )
    assert len(slots) == 3


def test_open_slots_exactly_18_counts_as_evening() -> None:
    itinerary = [
        {
            "item_date": "2026-07-10",
            "day_number": 1,
            "start_time": "18:00",
        }
    ]
    slots = _find_open_evening_slots(
        itinerary, trip_start=date(2026, 7, 10), trip_end=date(2026, 7, 10)
    )
    assert len(slots) == 0  # 18:00 counts as evening → slot is taken


# ── events agent run() ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_events_agent_run_no_api_keys_returns_empty() -> None:
    """When both API keys are empty, fetch_events returns [] and agent exits cleanly."""
    from backend.agents.events import run

    state = {
        "trip_id": "test-trip-id",
        "user_id": "test-user-id",
        "itinerary": [],
        "memory_context": {},
        "events_state": {},
        "agent_messages": [],
    }

    mock_trip = MagicMock()
    mock_trip.destination_city = "London"
    mock_trip.destination_country = "GB"
    mock_trip.start_date = date(2026, 7, 10)
    mock_trip.end_date = date(2026, 7, 15)

    with (
        patch("backend.agents.events.AsyncSessionLocal") as mock_session_ctx,
        patch("backend.agents.events.fetch_events", new_callable=AsyncMock, return_value=[]),
        patch("backend.agents.events.settings") as mock_settings,
        patch("backend.agents.events.get_redis_client", return_value=None),
    ):
        mock_settings.TICKETMASTER_API_KEY = ""
        mock_settings.EVENTBRITE_TOKEN = ""

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_trip
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_session_ctx.return_value = mock_db

        result = await run(state)  # type: ignore[arg-type]

    assert result["events_state"]["fetched"] == 0
    assert result["events_state"]["proposed"] == []
    assert result["events_state"]["conflict_warnings"] == 0


@pytest.mark.asyncio
async def test_events_agent_caps_proposals_at_three() -> None:
    """Even with many matching events, at most 3 ApprovalRequests are created."""
    from backend.agents.events import run

    state = {
        "trip_id": "trip-abc",
        "user_id": "user-abc",
        "itinerary": [],
        "memory_context": {
            "travel_style_profile": {"style_tags": ["music", "food"]},
            "preferences": {"interests": ["concerts"]},
        },
        "events_state": {},
        "agent_messages": [],
    }

    # 5 events, all on different days within date range, all with coordinates
    events = [
        _event(
            name=f"Event {i}",
            event_date=date(2026, 7, 10 + i),
            lat=51.5 + i * 0.01,
            lng=-0.1,
        )
        for i in range(5)
    ]

    mock_trip = MagicMock()
    mock_trip.destination_city = "London"
    mock_trip.destination_country = "GB"
    mock_trip.start_date = date(2026, 7, 10)
    mock_trip.end_date = date(2026, 7, 14)

    created_approvals: list = []

    with (
        patch("backend.agents.events.AsyncSessionLocal") as mock_session_ctx,
        patch("backend.agents.events.fetch_events", new_callable=AsyncMock, return_value=events),
        patch("backend.agents.events.settings") as mock_settings,
        patch("backend.agents.events.get_redis_client", return_value=None),
        patch(
            "backend.agents.events._proposal_summary",
            new_callable=AsyncMock,
            return_value="A great event for you!",
        ),
        patch(
            "backend.agents.events._score_events",
            return_value=[(e, 0.9 - i * 0.1) for i, e in enumerate(events)],
        ),
    ):
        mock_settings.TICKETMASTER_API_KEY = "key"
        mock_settings.EVENTBRITE_TOKEN = "token"

        # First call: load trip; subsequent calls: conflict check + approval inserts
        call_count = 0

        async def session_factory() -> AsyncMock:
            nonlocal call_count
            call_count += 1
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=False)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_trip
            mock_result.scalars.return_value.all.return_value = []  # no conflict items
            mock_db.execute = AsyncMock(return_value=mock_result)

            def capture_add(obj: object) -> None:
                if hasattr(obj, "change_type"):
                    created_approvals.append(obj)

            mock_db.add = MagicMock(side_effect=capture_add)
            return mock_db

        mock_session_ctx.return_value = AsyncMock(
            __aenter__=AsyncMock(side_effect=lambda: session_factory()),
            __aexit__=AsyncMock(return_value=False),
        )

        # Patch __aenter__ properly for the context manager
        async def ctx_enter(self):  # type: ignore[no-untyped-def]
            return await session_factory()

        mock_session_ctx.return_value.__aenter__ = ctx_enter

        result = await run(state)  # type: ignore[arg-type]

    assert len(result["events_state"]["proposed"]) <= 3
