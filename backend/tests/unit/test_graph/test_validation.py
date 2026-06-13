import pytest
from langchain_core.messages import SystemMessage

from backend.graphs.state import TravelOSState
from backend.graphs.validation import _parse_time, _validate_and_fix, run

# ── helpers ───────────────────────────────────────────────────────────────────


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-v",
        "user_id": "user-v",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {},
        "budget_state": {"total": 1000.0, "spent": 0.0, "by_category": {}, "breach_pct": 0.0},
        "hotel_state": {"candidates": [], "selected": None},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "validation",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _item(
    title: str = "Louvre Museum",
    day_number: int = 1,
    item_date: str = "2026-07-01",
    item_type: str = "activity",
    start_time: str | None = "09:00",
    end_time: str | None = "12:00",
    est_cost: float | None = 20.0,
    is_outdoor: bool = False,
) -> dict:  # type: ignore[type-arg]
    return {
        "day_number": day_number,
        "item_date": item_date,
        "start_time": start_time,
        "end_time": end_time,
        "item_type": item_type,
        "title": title,
        "description": None,
        "latitude": 48.86,
        "longitude": 2.34,
        "address": None,
        "source_provider": "overpass",
        "source_ref": "way/123",
        "est_cost": est_cost,
        "est_cost_currency": "EUR",
        "is_outdoor": is_outdoor,
        "sort_order": 99,  # should be reassigned
    }


# ── run() — cleaning behaviour ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_passes_valid_items_through() -> None:
    items = [_item("Louvre"), _item("Lunch", item_type="meal")]
    result = await run(_base_state(itinerary=items))
    assert len(result["itinerary"]) == 2


@pytest.mark.asyncio
async def test_run_removes_items_with_empty_title() -> None:
    items = [_item("Good item"), _item(""), _item("  ")]
    result = await run(_base_state(itinerary=items))
    assert len(result["itinerary"]) == 1
    assert result["itinerary"][0]["title"] == "Good item"


@pytest.mark.asyncio
async def test_run_removes_items_with_invalid_day_number() -> None:
    items = [
        _item("Good", day_number=1),
        _item("Bad", day_number=0),
        _item("Also bad", day_number=-1),
    ]
    result = await run(_base_state(itinerary=items))
    assert len(result["itinerary"]) == 1


@pytest.mark.asyncio
async def test_run_coerces_invalid_item_type_to_free() -> None:
    items = [_item(item_type="sightseeing")]
    result = await run(_base_state(itinerary=items))
    assert result["itinerary"][0]["item_type"] == "free"


@pytest.mark.asyncio
async def test_run_reassigns_sort_order_per_day() -> None:
    items = [
        _item("A", day_number=1),
        _item("B", day_number=1),
        _item("C", day_number=2),
    ]
    result = await run(_base_state(itinerary=items))
    day1 = [it for it in result["itinerary"] if it["day_number"] == 1]
    day2 = [it for it in result["itinerary"] if it["day_number"] == 2]
    assert [it["sort_order"] for it in day1] == [0, 1]
    assert [it["sort_order"] for it in day2] == [0]


@pytest.mark.asyncio
async def test_run_fixes_swapped_times() -> None:
    items = [_item(start_time="14:00", end_time="09:00")]
    result = await run(_base_state(itinerary=items))
    assert result["itinerary"][0]["start_time"] == "09:00"
    assert result["itinerary"][0]["end_time"] == "14:00"


@pytest.mark.asyncio
async def test_run_nullifies_negative_est_cost() -> None:
    items = [_item(est_cost=-50.0)]
    result = await run(_base_state(itinerary=items))
    assert result["itinerary"][0]["est_cost"] is None


@pytest.mark.asyncio
async def test_run_calculates_estimated_planned_in_budget_state() -> None:
    items = [_item(est_cost=100.0), _item(est_cost=50.0, title="Dinner")]
    result = await run(_base_state(itinerary=items))
    assert result["budget_state"]["estimated_planned"] == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_run_skips_estimated_planned_when_all_costs_null() -> None:
    items = [_item(est_cost=None), _item(est_cost=None, title="Dinner")]
    result = await run(_base_state(itinerary=items))
    assert "estimated_planned" not in result.get("budget_state", {})


@pytest.mark.asyncio
async def test_run_handles_empty_itinerary() -> None:
    result = await run(_base_state(itinerary=[]))
    assert result["itinerary"] == []
    assert isinstance(result["agent_messages"][0], SystemMessage)


@pytest.mark.asyncio
async def test_run_adds_system_message() -> None:
    items = [_item()]
    result = await run(_base_state(itinerary=items))
    msg = result["agent_messages"][0]
    assert isinstance(msg, SystemMessage)
    assert "trip-v" in msg.content


@pytest.mark.asyncio
async def test_run_preserves_existing_budget_state_keys() -> None:
    budget = {"total": 2000.0, "spent": 100.0, "by_category": {}, "breach_pct": 0.0}
    items = [_item(est_cost=50.0)]
    result = await run(_base_state(itinerary=items, budget_state=budget))
    assert result["budget_state"]["total"] == 2000.0
    assert result["budget_state"]["spent"] == 100.0


# ── pace under-count checks ───────────────────────────────────────────────────


def _state_with_pace(pace: str, items: list) -> TravelOSState:  # type: ignore[type-arg]
    return _base_state(
        itinerary=items,
        memory_context={"preferences": {"pace": pace}},
    )


@pytest.mark.asyncio
async def test_pace_relaxed_flags_day_with_one_item() -> None:
    # relaxed min = 2; one item on day 1 should be flagged
    result = await run(_state_with_pace("relaxed", [_item("Solo activity", day_number=1)]))
    msgs = result["agent_messages"][0].content
    assert "Day 1" in msgs
    assert "pace minimum" in msgs


@pytest.mark.asyncio
async def test_pace_relaxed_ok_with_two_items() -> None:
    items = [_item("Morning", day_number=1), _item("Lunch", day_number=1, item_type="meal")]
    result = await run(_state_with_pace("relaxed", items))
    assert "pace minimum" not in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_pace_moderate_flags_day_below_three() -> None:
    # moderate min = 3; two items should be flagged
    items = [_item("A", day_number=1), _item("B", day_number=1)]
    result = await run(_state_with_pace("moderate", items))
    assert "Day 1" in result["agent_messages"][0].content
    assert "pace minimum" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_pace_packed_flags_day_below_five() -> None:
    # packed min = 5; four items should be flagged
    items = [_item(f"Item {i}", day_number=1) for i in range(4)]
    result = await run(_state_with_pace("packed", items))
    assert "Day 1" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_pace_check_only_flags_sparse_days() -> None:
    # Day 1 has 3 items (ok for moderate), day 2 has 1 item (flagged)
    items = [_item(f"D1-{i}", day_number=1) for i in range(3)]
    items += [_item("D2-only", day_number=2)]
    result = await run(_state_with_pace("moderate", items))
    content = result["agent_messages"][0].content
    assert "Day 2" in content
    assert "Day 1" not in content


@pytest.mark.asyncio
async def test_pace_defaults_to_moderate_when_missing() -> None:
    # No pace in state — should default to moderate (min=3); one item flagged
    result = await run(_base_state(itinerary=[_item("Only item")]))
    assert "pace minimum" in result["agent_messages"][0].content


# ── _validate_and_fix ─────────────────────────────────────────────────────────


def test_validate_and_fix_valid_item() -> None:
    item, issues = _validate_and_fix(_item())
    assert item is not None
    assert issues == []


def test_validate_and_fix_strips_whitespace_from_title() -> None:
    item, _ = _validate_and_fix(_item(title="  Eiffel Tower  "))
    assert item is not None
    assert item["title"] == "Eiffel Tower"


def test_validate_and_fix_drops_empty_title() -> None:
    item, issues = _validate_and_fix(_item(title=""))
    assert item is None
    assert any("empty title" in i for i in issues)


def test_validate_and_fix_drops_zero_day_number() -> None:
    item, issues = _validate_and_fix(_item(day_number=0))
    assert item is None


def test_validate_and_fix_coerces_bad_item_type() -> None:
    item, issues = _validate_and_fix(_item(item_type="unknown"))
    assert item is not None
    assert item["item_type"] == "free"
    assert any("item_type" in i for i in issues)


def test_validate_and_fix_swaps_inverted_times() -> None:
    item, issues = _validate_and_fix(_item(start_time="18:00", end_time="09:00"))
    assert item is not None
    assert item["start_time"] == "09:00"
    assert item["end_time"] == "18:00"
    assert any("swapped" in i for i in issues)


def test_validate_and_fix_nullifies_negative_cost() -> None:
    item, issues = _validate_and_fix(_item(est_cost=-10.0))
    assert item is not None
    assert item["est_cost"] is None
    assert any("negative" in i for i in issues)


def test_validate_and_fix_allows_zero_cost() -> None:
    item, issues = _validate_and_fix(_item(est_cost=0.0))
    assert item is not None
    assert item["est_cost"] == 0.0


def test_validate_and_fix_coerces_is_outdoor_to_bool() -> None:
    raw = {**_item(), "is_outdoor": 1}  # int truthy
    item, _ = _validate_and_fix(raw)
    assert item is not None
    assert item["is_outdoor"] is True


# ── _parse_time ───────────────────────────────────────────────────────────────


def test_parse_time_valid() -> None:
    from datetime import time

    assert _parse_time("09:30") == time(9, 30)
    assert _parse_time("00:00") == time(0, 0)
    assert _parse_time("23:59") == time(23, 59)


def test_parse_time_none_input() -> None:
    assert _parse_time(None) is None


def test_parse_time_non_string() -> None:
    assert _parse_time(930) is None


def test_parse_time_invalid_format() -> None:
    assert _parse_time("not-a-time") is None
    assert _parse_time("25:00") is None
