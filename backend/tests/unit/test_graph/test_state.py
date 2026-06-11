from langchain_core.messages import HumanMessage

from backend.graphs.state import TravelOSState


def _minimal_state() -> TravelOSState:
    return TravelOSState(
        trip_id="trip-1",
        user_id="user-1",
        traveler_profiles=[],
        itinerary=[],
        weather_state={},
        budget_state={},
        hotel_state={},
        memory_context={},
        approval_queue=[],
        agent_messages=[],
        current_step="supervisor",
        error_state=None,
        run_checkpoint_ref=None,
        replan_iterations=0,
    )


def test_state_has_all_required_keys() -> None:
    required = {
        "trip_id",
        "user_id",
        "traveler_profiles",
        "itinerary",
        "weather_state",
        "budget_state",
        "hotel_state",
        "memory_context",
        "approval_queue",
        "agent_messages",
        "current_step",
        "error_state",
        "run_checkpoint_ref",
        "replan_iterations",
    }
    state = _minimal_state()
    assert required.issubset(set(state.keys()))


def test_state_string_fields() -> None:
    state = _minimal_state()
    assert isinstance(state["trip_id"], str)
    assert isinstance(state["user_id"], str)
    assert isinstance(state["current_step"], str)


def test_state_list_fields_are_empty_by_default() -> None:
    state = _minimal_state()
    assert state["itinerary"] == []
    assert state["approval_queue"] == []
    assert state["agent_messages"] == []
    assert state["traveler_profiles"] == []


def test_state_dict_fields_are_empty_by_default() -> None:
    state = _minimal_state()
    assert state["weather_state"] == {}
    assert state["budget_state"] == {}
    assert state["hotel_state"] == {}
    assert state["memory_context"] == {}


def test_state_optional_fields_default_none() -> None:
    state = _minimal_state()
    assert state["error_state"] is None
    assert state["run_checkpoint_ref"] is None


def test_state_replan_iterations_starts_at_zero() -> None:
    state = _minimal_state()
    assert state["replan_iterations"] == 0


def test_agent_messages_accepts_langchain_messages() -> None:
    state = _minimal_state()
    state["agent_messages"] = [HumanMessage(content="Hello")]
    assert len(state["agent_messages"]) == 1
    assert state["agent_messages"][0].content == "Hello"
