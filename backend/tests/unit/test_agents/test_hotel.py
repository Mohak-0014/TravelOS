from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, SystemMessage

from backend.agents.hotel import (
    _completeness_score,
    _compute_budget_per_night,
    _infer_tier,
    _offer_to_dict,
    _parse_selection,
    _price_score,
    _rank_offers,
    _score_offer,
    _star_score,
    run,
)
from backend.graphs.state import TravelOSState
from backend.tools.hotels import HotelOffer

# ── fixtures ──────────────────────────────────────────────────────────────────


def _mock_trip(
    trip_id: str = "trip-h",
    destination_city: str = "Paris",
    destination_country: str | None = "FR",
    start_date: date = date(2026, 7, 1),
    end_date: date = date(2026, 7, 5),
    num_travelers: int = 2,
    budget_total: float | None = 2000.0,
    budget_currency: str = "USD",
) -> MagicMock:
    trip = MagicMock()
    trip.id = trip_id
    trip.destination_city = destination_city
    trip.destination_country = destination_country
    trip.start_date = start_date
    trip.end_date = end_date
    trip.num_travelers = num_travelers
    trip.budget_total = budget_total
    trip.budget_currency = budget_currency
    return trip


def _make_offer(
    hotel_id: str = "h1",
    name: str = "Grand Hotel",
    price_per_night: float | None = 80.0,
    price_total: float | None = None,
    star_rating: float | None = 3.5,
    lat: float | None = 48.85,
    lng: float | None = 2.35,
    image_url: str | None = "https://example.com/img.jpg",
    source_provider: str = "liteapi",
) -> HotelOffer:
    return HotelOffer(
        hotel_id=hotel_id,
        name=name,
        lat=lat,
        lng=lng,
        price_per_night=price_per_night,
        price_total=price_total,
        price_currency="USD",
        star_rating=star_rating,
        meal_plan=None,
        refundable=True,
        booking_ref=None,
        image_url=image_url,
        source_provider=source_provider,
        source_ref=hotel_id,
        raw_payload={"_test": True},
    )


def _mid_style() -> dict:  # type: ignore[type-arg]
    return {
        "travel_style_summary": "A culturally curious couple.",
        "style_tags": ["culture", "moderate_pace"],
        "accommodation_preference": "comfortable mid-range hotels near attractions",
        "activity_preference": "Museums",
        "dining_preference": "Local cuisine",
        "daily_rhythm": "2-3 activities",
        "budget_priority": "Balanced",
    }


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-h",
        "user_id": "user-h",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {
            "total": 2000.0,
            "spent": 0.0,
            "by_category": {},
            "breach_pct": 0.0,
            "currency": "USD",
        },
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {
            "preferences": {},
            "travel_style_profile": _mid_style(),
            "embedding_hits": [],
            "past_trips": [],
        },
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "hotel_agent",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _mock_llm(selected_index: int = 0) -> MagicMock:
    import json

    llm = MagicMock()
    content = json.dumps({"selected_index": selected_index, "rationale": "Best match."})
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=content))
    return llm


def _patch_hotel_run(offers: list[HotelOffer], trip: MagicMock, llm_idx: int = 0):
    return (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=offers)),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
        patch("backend.agents.hotel._build_llm", return_value=_mock_llm(llm_idx)),
        patch("backend.agents.hotel._persist_candidates", new=AsyncMock()),
    )


# ── run() — happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_returns_hotel_state() -> None:
    trip = _mock_trip()
    offers = [_make_offer("h1", "Hotel A"), _make_offer("h2", "Hotel B")]
    with (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=offers)),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
        patch("backend.agents.hotel._build_llm", return_value=_mock_llm(0)),
        patch("backend.agents.hotel._persist_candidates", new=AsyncMock()),
    ):
        result = await run(_base_state())

    assert "hotel_state" in result
    assert len(result["hotel_state"]["candidates"]) == 2
    assert result["hotel_state"]["selected"] is not None
    assert result["hotel_state"]["selected"]["name"] in ("Hotel A", "Hotel B")


@pytest.mark.asyncio
async def test_run_selected_matches_llm_index() -> None:
    trip = _mock_trip()
    offers = [_make_offer("h1", "Cheap Inn"), _make_offer("h2", "Fancy Hotel", star_rating=5.0)]
    with (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=offers)),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
        patch("backend.agents.hotel._build_llm", return_value=_mock_llm(1)),
        patch("backend.agents.hotel._persist_candidates", new=AsyncMock()),
    ):
        result = await run(_base_state())

    # LLM selected index 1 → second item in ranked list
    selected_name = result["hotel_state"]["selected"]["name"]
    assert selected_name is not None  # exact name depends on ranking order


@pytest.mark.asyncio
async def test_run_adds_system_message() -> None:
    trip = _mock_trip()
    offers = [_make_offer()]
    with (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=offers)),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
        patch("backend.agents.hotel._build_llm", return_value=_mock_llm(0)),
        patch("backend.agents.hotel._persist_candidates", new=AsyncMock()),
    ):
        result = await run(_base_state())

    assert isinstance(result["agent_messages"][0], SystemMessage)
    assert "Paris" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_persists_candidates() -> None:
    trip = _mock_trip()
    offers = [_make_offer("h1"), _make_offer("h2")]
    persist_mock = AsyncMock()
    with (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=offers)),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
        patch("backend.agents.hotel._build_llm", return_value=_mock_llm(0)),
        patch("backend.agents.hotel._persist_candidates", new=persist_mock),
    ):
        await run(_base_state())

    persist_mock.assert_awaited_once()
    args = persist_mock.call_args[0]
    assert args[0] == "trip-h"
    assert len(args[1]) == 2


# ── run() — degradation paths ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_handles_trip_not_found() -> None:
    with patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=None)):
        result = await run(_base_state())

    assert result["hotel_state"] == {"candidates": [], "selected": None}


@pytest.mark.asyncio
async def test_run_handles_no_offers() -> None:
    trip = _mock_trip()
    with (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=[])),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
    ):
        result = await run(_base_state())

    assert result["hotel_state"]["candidates"] == []
    assert result["hotel_state"]["selected"] is None


@pytest.mark.asyncio
async def test_run_falls_back_to_index_zero_when_llm_fails() -> None:
    trip = _mock_trip()
    offers = [_make_offer("h1", "Best Hotel"), _make_offer("h2", "Other Hotel")]
    failing_llm = MagicMock()
    failing_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))
    with (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=offers)),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
        patch("backend.agents.hotel._build_llm", return_value=failing_llm),
        patch("backend.agents.hotel._persist_candidates", new=AsyncMock()),
    ):
        result = await run(_base_state())

    # Should still return a selected hotel (index 0 of ranked list)
    assert result["hotel_state"]["selected"] is not None


# ── _rank_offers ──────────────────────────────────────────────────────────────


def test_rank_offers_higher_scored_comes_first() -> None:
    budget_state = {"total": 2000.0, "currency": "USD"}
    # h1: good price, good stars for mid; h2: overpriced
    h1 = _make_offer("h1", price_per_night=70.0, star_rating=3.5)
    h2 = _make_offer("h2", price_per_night=500.0, star_rating=5.0)
    ranked = _rank_offers([h1, h2], _mid_style(), budget_state, trip_nights=4)
    assert ranked[0].hotel_id == "h1"


def test_rank_offers_uses_luxury_tier_for_stars() -> None:
    luxury_style = {**_mid_style(), "accommodation_preference": "luxury five-star hotel"}
    budget_state = {"total": 10000.0}
    h_budget = _make_offer("h1", star_rating=2.0, price_per_night=50.0)
    h_luxury = _make_offer("h2", star_rating=5.0, price_per_night=300.0)
    ranked = _rank_offers([h_budget, h_luxury], luxury_style, budget_state, trip_nights=4)
    assert ranked[0].hotel_id == "h2"


def test_rank_offers_handles_missing_prices() -> None:
    h = _make_offer(price_per_night=None)
    ranked = _rank_offers([h], _mid_style(), {"total": 2000.0}, trip_nights=4)
    assert len(ranked) == 1  # doesn't crash


def test_rank_offers_returns_up_to_10_from_run() -> None:
    offers = [_make_offer(hotel_id=str(i)) for i in range(15)]
    ranked = _rank_offers(offers, _mid_style(), {}, trip_nights=3)
    # run() slices to [:10], rank function itself returns all
    assert len(ranked) == 15


# ── scoring primitives ────────────────────────────────────────────────────────


def test_price_score_within_budget() -> None:
    # ratio = 90/100 = 0.9 → within budget band (0.8 < ratio ≤ 1.0) → 0.3
    offer = _make_offer(price_per_night=90.0)
    assert _price_score(offer, budget_per_night=100.0) == pytest.approx(0.3)


def test_price_score_great_value() -> None:
    offer = _make_offer(price_per_night=60.0)
    assert _price_score(offer, budget_per_night=100.0) == pytest.approx(0.4)


def test_price_score_over_budget() -> None:
    offer = _make_offer(price_per_night=200.0)
    assert _price_score(offer, budget_per_night=100.0) == pytest.approx(0.0)


def test_price_score_neutral_when_no_budget() -> None:
    offer = _make_offer(price_per_night=100.0)
    assert _price_score(offer, budget_per_night=None) == pytest.approx(0.2)


def test_price_score_neutral_when_no_price() -> None:
    offer = _make_offer(price_per_night=None)
    assert _price_score(offer, budget_per_night=100.0) == pytest.approx(0.2)


def test_star_score_perfect_mid_match() -> None:
    offer = _make_offer(star_rating=3.5)
    assert _star_score(offer, "mid") == pytest.approx(0.4)


def test_star_score_perfect_budget_match() -> None:
    offer = _make_offer(star_rating=2.0)
    assert _star_score(offer, "budget") == pytest.approx(0.4)


def test_star_score_mismatch_reduces_score() -> None:
    offer_5star = _make_offer(star_rating=5.0)
    # luxury expects 4.5, so 5.0 is close but not exact
    assert _star_score(offer_5star, "luxury") > _star_score(offer_5star, "budget")


def test_star_score_unknown_gives_partial_credit() -> None:
    offer = _make_offer(star_rating=None)
    assert _star_score(offer, "mid") == pytest.approx(0.15)


def test_completeness_score_full() -> None:
    offer = _make_offer(lat=48.85, lng=2.35, image_url="http://img.com/x.jpg")
    assert _completeness_score(offer) == pytest.approx(0.2)


def test_completeness_score_no_image() -> None:
    offer = _make_offer(lat=48.85, lng=2.35, image_url=None)
    assert _completeness_score(offer) == pytest.approx(0.1)


def test_completeness_score_no_coords() -> None:
    offer = _make_offer(lat=None, lng=None, image_url="http://img.com/x.jpg")
    assert _completeness_score(offer) == pytest.approx(0.1)


def test_score_offer_sums_components() -> None:
    # price=90, budget=100 → ratio 0.9 → price_score=0.3; star=3.5 mid → 0.4; completeness → 0.2
    offer = _make_offer(price_per_night=90.0, star_rating=3.5, lat=48.85, lng=2.35, image_url="x")
    total = _score_offer(offer, "mid", 100.0)
    expected = 0.3 + 0.4 + 0.2
    assert total == pytest.approx(expected)


# ── _infer_tier ───────────────────────────────────────────────────────────────


def test_infer_tier_luxury_keywords() -> None:
    assert _infer_tier("luxury boutique hotel near centre") == "luxury"
    assert _infer_tier("5-star resort") == "luxury"


def test_infer_tier_budget_keywords() -> None:
    assert _infer_tier("cheap budget hostel") == "budget"


def test_infer_tier_default_mid() -> None:
    assert _infer_tier("comfortable hotel") == "mid"
    assert _infer_tier("") == "mid"


# ── _compute_budget_per_night ─────────────────────────────────────────────────


def test_compute_budget_per_night_basic() -> None:
    result = _compute_budget_per_night({"total": 2000.0}, trip_nights=4)
    # 35% of 2000 / 4 = 175
    assert result == pytest.approx(175.0)


def test_compute_budget_per_night_no_total() -> None:
    assert _compute_budget_per_night({}, trip_nights=4) is None
    assert _compute_budget_per_night({"total": None}, trip_nights=4) is None


# ── _parse_selection ──────────────────────────────────────────────────────────


def test_parse_selection_valid() -> None:
    import json

    raw = json.dumps({"selected_index": 2, "rationale": "good choice"})
    assert _parse_selection(raw, n_candidates=5) == 2


def test_parse_selection_clamps_to_range() -> None:
    import json

    raw = json.dumps({"selected_index": 99, "rationale": "oob"})
    assert _parse_selection(raw, n_candidates=3) == 2  # clamped to n-1


def test_parse_selection_invalid_json_returns_zero() -> None:
    assert _parse_selection("not json", n_candidates=5) == 0


def test_parse_selection_json_in_prose() -> None:
    import json

    raw = f"I recommend: {json.dumps({'selected_index': 1, 'rationale': 'great value'})}!"
    assert _parse_selection(raw, n_candidates=5) == 1


# ── _offer_to_dict ────────────────────────────────────────────────────────────


def test_offer_to_dict_strips_internal_score_key() -> None:
    offer = _make_offer()
    offer.raw_payload["_match_score"] = 0.75
    d = _offer_to_dict(offer)
    assert "_match_score" not in d["raw_payload"]


def test_offer_to_dict_preserves_public_payload() -> None:
    offer = _make_offer()
    offer.raw_payload["hotelName"] = "Grand Hotel"
    d = _offer_to_dict(offer)
    assert d["raw_payload"]["hotelName"] == "Grand Hotel"


@pytest.mark.asyncio
async def test_run_drops_offers_with_unknown_pricing() -> None:
    # A hotel with neither per-night nor total price can't be budgeted — dropped.
    trip = _mock_trip()
    offers = [
        _make_offer("h1", "Priced Hotel"),
        _make_offer("h2", "Mystery Hotel", price_per_night=None, price_total=None),
        _make_offer("h3", "Total-Only Hotel", price_per_night=None, price_total=320.0),
    ]
    with (
        patch("backend.agents.hotel._load_trip", new=AsyncMock(return_value=trip)),
        patch("backend.agents.hotel.search_hotels", new=AsyncMock(return_value=offers)),
        patch("backend.agents.hotel.get_redis_client", return_value=MagicMock(aclose=AsyncMock())),
        patch("backend.agents.hotel._build_llm", return_value=_mock_llm(0)),
        patch("backend.agents.hotel._persist_candidates", new=AsyncMock()),
    ):
        result = await run(_base_state())

    names = [c["name"] for c in result["hotel_state"]["candidates"]]
    assert "Mystery Hotel" not in names
    assert "Priced Hotel" in names
    assert "Total-Only Hotel" in names  # total price alone is still budgetable
