import pytest
from langchain_core.messages import SystemMessage

from backend.graphs.conflict_detection import _budget_approval, _find_time_overlaps, run
from backend.graphs.state import TravelOSState

# ── helpers ───────────────────────────────────────────────────────────────────


def _base_state(**overrides) -> TravelOSState:  # type: ignore[type-arg]
    state: TravelOSState = {
        "trip_id": "trip-cd",
        "user_id": "user-cd",
        "traveler_profiles": [],
        "itinerary": [],
        "weather_state": {"risk_flags": [], "last_checked": None, "forecast": []},
        "budget_state": {
            "total": 1000.0,
            "spent": 0.0,
            "by_category": {},
            "breach_pct": 0.0,
        },
        "hotel_state": {"candidates": [], "selected": {"name": "Grand Hotel"}},
        "memory_context": {},
        "approval_queue": [],
        "agent_messages": [],
        "current_step": "conflict_detection",
        "error_state": None,
        "run_checkpoint_ref": None,
        "replan_iterations": 0,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


def _item(
    day: int = 1,
    item_date: str = "2026-07-01",
    start_time: str | None = "09:00",
    end_time: str | None = "12:00",
    item_type: str = "activity",
    is_outdoor: bool = False,
    title: str = "Activity",
) -> dict:  # type: ignore[type-arg]
    return {
        "day_number": day,
        "item_date": item_date,
        "start_time": start_time,
        "end_time": end_time,
        "item_type": item_type,
        "title": title,
        "is_outdoor": is_outdoor,
        "est_cost": None,
        "sort_order": 0,
    }


# ── run() — clean path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_no_conflicts_routes_to_approval_gate() -> None:
    items = [
        _item(day=1, start_time="09:00", end_time="12:00"),
        _item(day=1, start_time="14:00", end_time="17:00", title="Afternoon"),
    ]
    result = await run(_base_state(itinerary=items))
    assert result["current_step"] == "approval_gate"
    assert result["replan_iterations"] == 0


@pytest.mark.asyncio
async def test_run_adds_system_message() -> None:
    result = await run(_base_state())
    assert isinstance(result["agent_messages"][0], SystemMessage)
    assert "trip-cd" in result["agent_messages"][0].content


@pytest.mark.asyncio
async def test_run_empty_itinerary_proceeds_without_replan_on_max_iterations() -> None:
    # Even though all items are "free", if replan_iterations >= 3, must not replan
    items = [_item(item_type="free")]
    result = await run(_base_state(itinerary=items, replan_iterations=3))
    assert result["current_step"] == "approval_gate"


# ── run() — replan triggers ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_time_overlap_is_warning_not_replan() -> None:
    # Validation repairs overlaps deterministically before this node — a leftover
    # overlap is reported as a conflict but no longer burns an LLM replan cycle.
    items = [
        _item(day=1, start_time="09:00", end_time="13:00"),
        _item(day=1, start_time="11:00", end_time="15:00", title="Overlap"),
    ]
    result = await run(_base_state(itinerary=items))
    assert result["current_step"] == "approval_gate"
    assert result["replan_iterations"] == 0
    assert "overlap" in result["agent_messages"][0].content.lower()


@pytest.mark.asyncio
async def test_run_all_free_items_triggers_replan() -> None:
    items = [_item(item_type="free"), _item(item_type="free", title="Free 2")]
    result = await run(_base_state(itinerary=items))
    assert result["current_step"] == "itinerary_planner"
    assert result["replan_iterations"] == 1


@pytest.mark.asyncio
async def test_run_replan_increments_iterations() -> None:
    items = [_item(item_type="free")]
    result = await run(_base_state(itinerary=items, replan_iterations=1))
    assert result["replan_iterations"] == 2


@pytest.mark.asyncio
async def test_run_no_replan_when_iterations_at_max() -> None:
    items = [_item(item_type="free")]
    result = await run(_base_state(itinerary=items, replan_iterations=3))
    assert result["current_step"] == "approval_gate"
    assert result["replan_iterations"] == 3


# ── run() — budget breach ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_budget_breach_creates_approval() -> None:
    budget = {
        "total": 1000.0,
        "spent": 0.0,
        "by_category": {},
        "breach_pct": 0.0,
        "estimated_planned": 1200.0,
    }
    result = await run(_base_state(budget_state=budget))
    assert len(result["approval_queue"]) == 1
    approval = result["approval_queue"][0]
    assert approval["change_type"] == "budget_exceed"
    assert approval["status"] == "pending"


@pytest.mark.asyncio
async def test_run_budget_breach_updates_breach_pct() -> None:
    budget = {
        "total": 1000.0,
        "spent": 0.0,
        "by_category": {},
        "breach_pct": 0.0,
        "estimated_planned": 1200.0,
    }
    result = await run(_base_state(budget_state=budget))
    assert result["budget_state"]["breach_pct"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_run_budget_breach_does_not_trigger_replan() -> None:
    # Budget breach → approval, not replan
    budget = {
        "total": 1000.0,
        "spent": 0.0,
        "by_category": {},
        "breach_pct": 0.0,
        "estimated_planned": 1500.0,
    }
    result = await run(_base_state(budget_state=budget))
    assert result["current_step"] == "approval_gate"


@pytest.mark.asyncio
async def test_run_no_approval_when_breach_within_threshold() -> None:
    # 10% over — below 15% threshold
    budget = {
        "total": 1000.0,
        "spent": 0.0,
        "by_category": {},
        "breach_pct": 0.0,
        "estimated_planned": 1100.0,
    }
    result = await run(_base_state(budget_state=budget))
    assert len(result["approval_queue"]) == 0


@pytest.mark.asyncio
async def test_run_preserves_existing_approvals_in_queue() -> None:
    existing = [
        {
            "id": "existing-1",
            "change_type": "other",
            "status": "pending",
            "proposed_by": "x",
            "summary": "x",
            "payload": {},
        }
    ]
    budget = {
        "total": 1000.0,
        "spent": 0.0,
        "by_category": {},
        "breach_pct": 0.0,
        "estimated_planned": 1200.0,
    }
    result = await run(_base_state(budget_state=budget, approval_queue=existing))
    assert len(result["approval_queue"]) == 2
    ids = [a.get("id", "") for a in result["approval_queue"]]
    assert "existing-1" in ids


# ── run() — weather + hotel warnings ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_flags_outdoor_on_adverse_day_in_message() -> None:
    weather = {"risk_flags": ["2026-07-01"], "last_checked": None, "forecast": []}
    items = [_item(item_date="2026-07-01", is_outdoor=True, title="Hike")]
    result = await run(_base_state(itinerary=items, weather_state=weather))
    msg = result["agent_messages"][0].content
    assert "outdoor" in msg.lower() or "adverse" in msg.lower()


@pytest.mark.asyncio
async def test_run_outdoor_adverse_does_not_trigger_replan() -> None:
    # Weather adaptation handles this — conflict detection just flags it
    weather = {"risk_flags": ["2026-07-01"], "last_checked": None, "forecast": []}
    items = [_item(item_date="2026-07-01", is_outdoor=True, title="Hike")]
    result = await run(_base_state(itinerary=items, weather_state=weather))
    assert result["current_step"] == "approval_gate"


@pytest.mark.asyncio
async def test_run_no_hotel_flagged_in_message() -> None:
    result = await run(_base_state(hotel_state={"candidates": [], "selected": None}))
    msg = result["agent_messages"][0].content
    assert "hotel" in msg.lower()


@pytest.mark.asyncio
async def test_run_no_hotel_does_not_trigger_replan() -> None:
    result = await run(_base_state(hotel_state={"candidates": [], "selected": None}))
    assert result["current_step"] == "approval_gate"


# ── _find_time_overlaps ───────────────────────────────────────────────────────


def test_find_overlaps_detects_overlap() -> None:
    items = [
        _item(day=1, start_time="09:00", end_time="13:00"),
        _item(day=1, start_time="11:00", end_time="15:00"),
    ]
    assert 1 in _find_time_overlaps(items)


def test_find_overlaps_no_overlap() -> None:
    items = [
        _item(day=1, start_time="09:00", end_time="12:00"),
        _item(day=1, start_time="13:00", end_time="16:00"),
    ]
    assert _find_time_overlaps(items) == []


def test_find_overlaps_adjacent_times_not_overlapping() -> None:
    # End of first == start of second is NOT an overlap
    items = [
        _item(day=1, start_time="09:00", end_time="12:00"),
        _item(day=1, start_time="12:00", end_time="15:00"),
    ]
    assert _find_time_overlaps(items) == []


def test_find_overlaps_skips_items_without_times() -> None:
    items = [
        _item(day=1, start_time=None, end_time=None),
        _item(day=1, start_time="09:00", end_time="12:00"),
    ]
    assert _find_time_overlaps(items) == []


def test_find_overlaps_only_flags_affected_days() -> None:
    items = [
        # Day 1: overlap
        _item(day=1, start_time="09:00", end_time="13:00"),
        _item(day=1, start_time="11:00", end_time="15:00"),
        # Day 2: no overlap
        _item(day=2, start_time="09:00", end_time="12:00"),
        _item(day=2, start_time="14:00", end_time="17:00"),
    ]
    overlaps = _find_time_overlaps(items)
    assert overlaps == [1]


def test_find_overlaps_returns_sorted_list() -> None:
    items = [
        _item(day=3, start_time="09:00", end_time="13:00"),
        _item(day=3, start_time="11:00", end_time="15:00"),
        _item(day=1, start_time="09:00", end_time="13:00"),
        _item(day=1, start_time="11:00", end_time="15:00"),
    ]
    assert _find_time_overlaps(items) == [1, 3]


def test_find_overlaps_empty_itinerary() -> None:
    assert _find_time_overlaps([]) == []


# ── _budget_approval ──────────────────────────────────────────────────────────


def test_budget_approval_has_required_fields() -> None:
    approval = _budget_approval(1200.0, 1000.0, 20.0)
    assert approval["change_type"] == "budget_exceed"
    assert approval["status"] == "pending"
    assert approval["proposed_by"] == "conflict_detection"
    assert "id" in approval


def test_budget_approval_payload_values() -> None:
    approval = _budget_approval(1200.0, 1000.0, 20.0)
    assert approval["payload"]["estimated_total"] == pytest.approx(1200.0)
    assert approval["payload"]["budget_total"] == pytest.approx(1000.0)
    assert approval["payload"]["breach_pct"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_run_replan_carries_feedback_for_planner() -> None:
    # All-free itinerary triggers a replan — the reasons must be handed to the
    # planner via replan_feedback, not buried in message prose.
    items = [
        {"title": "Free block", "item_type": "free", "day_number": 1},
        {"title": "Free block", "item_type": "free", "day_number": 2},
    ]
    result = await run(_base_state(itinerary=items))
    assert result["current_step"] == "itinerary_planner"
    assert result["replan_feedback"]
    assert any("free" in f.lower() for f in result["replan_feedback"])


@pytest.mark.asyncio
async def test_run_no_replan_clears_feedback() -> None:
    result = await run(_base_state(itinerary=[]))
    assert result["replan_feedback"] == []
