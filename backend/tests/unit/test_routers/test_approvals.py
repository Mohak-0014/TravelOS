"""Unit tests for the approvals router."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routers.approvals import _extract_context_tags

# ── _extract_context_tags ─────────────────────────────────────────────────────


def test_extract_tags_budget_swap() -> None:
    payload = {"current": {"title": "Museum Island", "id": "abc"}, "replacement": {"title": "Park"}}
    tags = _extract_context_tags("budget_swap", payload)
    assert "budget_swap" in tags
    assert "Museum Island" in tags


def test_extract_tags_event_add() -> None:
    payload = {"event_name": "Jazz Festival", "category": "Music", "url": "http://..."}
    tags = _extract_context_tags("event_add", payload)
    assert "event_add" in tags
    assert "Jazz Festival" in tags
    assert "Music" in tags


def test_extract_tags_concierge_add() -> None:
    payload = {"title": "Boat Tour", "day": 2, "description": "Nice boat ride"}
    tags = _extract_context_tags("concierge_add", payload)
    assert "concierge_add" in tags
    assert "Boat Tour" in tags


def test_extract_tags_no_duplicates() -> None:
    # change_type also appears as a 'category' in payload — should be deduplicated
    payload = {"category": "budget_swap"}
    tags = _extract_context_tags("budget_swap", payload)
    assert tags.count("budget_swap") == 1


def test_extract_tags_empty_payload() -> None:
    tags = _extract_context_tags("budget_exceed", {})
    assert tags == ["budget_exceed"]


# ── helpers ───────────────────────────────────────────────────────────────────


async def _auth(client: AsyncClient, email: str = "approvals@test.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Pass1234!", "full_name": "Approver"},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Pass1234!"})
    return resp.json()["access_token"]


async def _create_trip(client: AsyncClient, token: str, title: str = "Approval Trip") -> dict:
    resp = await client.post(
        "/api/v1/trips",
        json={
            "title": title,
            "destination_city": "Tokyo",
            "start_date": "2026-09-01",
            "end_date": "2026-09-03",
            "num_travelers": 1,
            "budget_total": 1500,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_item(client: AsyncClient, token: str, trip_id: str) -> dict:
    resp = await client.post(
        f"/api/v1/trips/{trip_id}/itinerary",
        json={
            "day_number": 1,
            "item_date": "2026-09-01",
            "item_type": "activity",
            "title": "Shibuya Crossing",
            "sort_order": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_approval(
    client: AsyncClient,
    token: str,
    trip_id: str,
    item_id: str,
    replacement_title: str = "TeamLab Planets",
) -> dict:
    resp = await client.post(
        f"/api/v1/trips/{trip_id}/approvals",
        json={
            "item_id": item_id,
            "replacement_title": replacement_title,
            "reason": "Better alternative",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── create_approval ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_approval_returns_201(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])

    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/approvals",
        json={"item_id": item["id"], "replacement_title": "TeamLab Planets"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["change_type"] == "user_replace"
    assert body["proposed_by"] == "user"
    assert "TeamLab Planets" in body["summary"]
    assert body["payload"]["item_id"] == item["id"]


@pytest.mark.asyncio
async def test_create_approval_sets_trip_awaiting(client: AsyncClient) -> None:
    token = await _auth(client, "awaiting@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    await _create_approval(client, token, trip["id"], item["id"])

    resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.json()["status"] == "awaiting_approval"


@pytest.mark.asyncio
async def test_create_approval_trip_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "notrip@test.com")
    resp = await client.post(
        "/api/v1/trips/no-such-trip/approvals",
        json={"item_id": "any-item", "replacement_title": "X"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_approval_other_user_trip_404(client: AsyncClient) -> None:
    token_a = await _auth(client, "owner_appr@test.com")
    token_b = await _auth(client, "spy_appr@test.com")
    trip = await _create_trip(client, token_a)
    item = await _add_item(client, token_a, trip["id"])

    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/approvals",
        json={"item_id": item["id"], "replacement_title": "X"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_approval_item_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "noitem@test.com")
    trip = await _create_trip(client, token)

    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/approvals",
        json={"item_id": "no-such-item", "replacement_title": "X"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_approval_includes_reason_in_summary(client: AsyncClient) -> None:
    token = await _auth(client, "reason@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])

    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/approvals",
        json={
            "item_id": item["id"],
            "replacement_title": "Senso-ji",
            "reason": "More iconic",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert "More iconic" in resp.json()["summary"]


# ── list_approvals ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_approvals_returns_all(client: AsyncClient) -> None:
    token = await _auth(client, "list_all@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    resp = await client.get(
        f"/api/v1/trips/{trip['id']}/approvals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert any(a["id"] == approval["id"] for a in resp.json())


@pytest.mark.asyncio
async def test_list_approvals_status_filter(client: AsyncClient) -> None:
    token = await _auth(client, "filter@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    # Reject it
    await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "rejected"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Filter pending → empty
    resp = await client.get(
        f"/api/v1/trips/{trip['id']}/approvals?status=pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json() == []

    # Filter rejected → one result
    resp2 = await client.get(
        f"/api/v1/trips/{trip['id']}/approvals?status=rejected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(resp2.json()) == 1
    assert resp2.json()[0]["status"] == "rejected"


# ── get_approval ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_approval_by_id(client: AsyncClient) -> None:
    token = await _auth(client, "getappr@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    resp = await client.get(
        f"/api/v1/approvals/{approval['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == approval["id"]
    assert resp.json()["trip_id"] == trip["id"]


@pytest.mark.asyncio
async def test_get_approval_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "getappr404@test.com")
    resp = await client.get(
        "/api/v1/approvals/no-such-approval",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_approval_other_user_404(client: AsyncClient) -> None:
    token_a = await _auth(client, "appr_owner@test.com")
    token_b = await _auth(client, "appr_spy@test.com")
    trip = await _create_trip(client, token_a)
    item = await _add_item(client, token_a, trip["id"])
    approval = await _create_approval(client, token_a, trip["id"], item["id"])

    resp = await client.get(
        f"/api/v1/approvals/{approval['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── resolve_approval ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_updates_item_title(client: AsyncClient) -> None:
    token = await _auth(client, "approve@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"], "TeamLab Planets")

    resp = await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    items = await client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert any(i["title"] == "TeamLab Planets" for i in items.json())


@pytest.mark.asyncio
async def test_resolve_writes_outbox_embed_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Resolving an approval stages the feedback-embedding task in the outbox (atomically),
    instead of calling .delay() after commit."""
    from sqlalchemy import select

    from backend.db.models import OutboxEvent

    token = await _auth(client, "outbox_appr@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    resp = await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    rows = list((await db_session.execute(select(OutboxEvent))).scalars().all())
    assert len(rows) == 1
    assert rows[0].task_name == "backend.workflows.celery_tasks.embed_feedback_async"
    assert rows[0].status == "pending"
    assert "feedback_id" in rows[0].payload


@pytest.mark.asyncio
async def test_approve_restores_trip_status_to_planned(client: AsyncClient) -> None:
    token = await _auth(client, "approve_status@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    trip_resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert trip_resp.json()["status"] == "planned"


@pytest.mark.asyncio
async def test_reject_does_not_change_item(client: AsyncClient) -> None:
    token = await _auth(client, "reject@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"], "TeamLab Planets")

    await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "rejected"},
        headers={"Authorization": f"Bearer {token}"},
    )

    items = await client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers={"Authorization": f"Bearer {token}"},
    )
    titles = [i["title"] for i in items.json()]
    assert "Shibuya Crossing" in titles
    assert "TeamLab Planets" not in titles


@pytest.mark.asyncio
async def test_reject_restores_trip_status_to_planned(client: AsyncClient) -> None:
    token = await _auth(client, "reject_status@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "rejected"},
        headers={"Authorization": f"Bearer {token}"},
    )

    trip_resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert trip_resp.json()["status"] == "planned"


@pytest.mark.asyncio
async def test_resolve_already_resolved_409(client: AsyncClient) -> None:
    token = await _auth(client, "double_resolve@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "rejected"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_resolve_invalid_decision_422(client: AsyncClient) -> None:
    token = await _auth(client, "invalid_decision@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    approval = await _create_approval(client, token, trip["id"], item["id"])

    resp = await client.post(
        f"/api/v1/approvals/{approval['id']}",
        json={"decision": "maybe"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_resolve_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "resolve404@test.com")
    resp = await client.post(
        "/api/v1/approvals/no-such-approval",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_two_pending_trip_stays_awaiting(client: AsyncClient) -> None:
    """Approving one of two pending approvals keeps trip in awaiting_approval."""
    token = await _auth(client, "two_pending@test.com")
    trip = await _create_trip(client, token)
    item1 = await _add_item(client, token, trip["id"])

    item2_resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary",
        json={
            "day_number": 1,
            "item_date": "2026-09-01",
            "item_type": "restaurant",
            "title": "Sushi Bar",
            "sort_order": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    item2_id = item2_resp.json()["id"]

    a1 = await _create_approval(client, token, trip["id"], item1["id"], "Option A")
    await _create_approval(client, token, trip["id"], item2_id, "Option B")

    # Resolve only the first
    await client.post(
        f"/api/v1/approvals/{a1['id']}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    trip_resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert trip_resp.json()["status"] == "awaiting_approval"


@pytest.mark.asyncio
async def test_approve_budget_upgrade_selects_candidate(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Approving a budget_upgrade approval sets is_selected on the named candidate."""
    from sqlalchemy import select

    from backend.db.models import Approval, HotelCandidate, Trip

    token = await _auth(client, "budget_upgrade@test.com")
    trip = await _create_trip(client, token)

    # Insert two hotel candidates: current selected (3★) and upgrade (5★)
    current = HotelCandidate(
        trip_id=trip["id"],
        provider="liteapi",
        provider_hotel_id="h-current",
        name="Budget Inn",
        star_rating=3.0,
        is_selected=True,
    )
    upgrade = HotelCandidate(
        trip_id=trip["id"],
        provider="liteapi",
        provider_hotel_id="h-upgrade",
        name="Grand Palace Hotel",
        star_rating=5.0,
        is_selected=False,
    )
    db_session.add_all([current, upgrade])

    # Create a budget_upgrade approval pointing at the upgrade candidate
    approval = Approval(
        trip_id=trip["id"],
        proposed_by="budget_optimizer",
        change_type="budget_upgrade",
        summary="Switch to Grand Palace Hotel — 40% under budget",
        payload={"candidate_id": None, "title": "Grand Palace Hotel"},  # filled below
        status="pending",
    )
    db_session.add(approval)
    trip_result = await db_session.execute(select(Trip).where(Trip.id == trip["id"]))
    db_trip = trip_result.scalar_one()
    db_trip.status = "awaiting_approval"
    await db_session.commit()
    await db_session.refresh(upgrade)
    await db_session.refresh(approval)

    # Patch the candidate_id now that we have the real UUID
    approval.payload = {"candidate_id": str(upgrade.id), "title": "Grand Palace Hotel"}
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/approvals/{approval.id}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    # Upgrade candidate must now be selected; current must be deselected
    result = await db_session.execute(
        select(HotelCandidate).where(HotelCandidate.trip_id == trip["id"])
    )
    candidates = {c.name: c for c in result.scalars().all()}
    assert candidates["Grand Palace Hotel"].is_selected is True
    assert candidates["Budget Inn"].is_selected is False


@pytest.mark.asyncio
async def test_concierge_swap_approve_updates_item_with_description(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """concierge_swap type: approval payload includes description → item.description updated."""
    from sqlalchemy import select

    from backend.db.models import Approval, ItineraryItem, Trip

    token = await _auth(client, "conc_swap@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])

    # Create a concierge_swap approval directly in DB (the API only creates user_replace)
    approval = Approval(
        trip_id=trip["id"],
        proposed_by="concierge",
        change_type="concierge_swap",
        summary="Swap with Senso-ji Temple",
        payload={
            "item_id": item["id"],
            "replacement": {
                "title": "Senso-ji Temple",
                "description": "Ancient Buddhist temple in Asakusa.",
            },
        },
        status="pending",
    )
    db_session.add(approval)
    trip_result = await db_session.execute(select(Trip).where(Trip.id == trip["id"]))
    db_trip = trip_result.scalar_one()
    db_trip.status = "awaiting_approval"
    await db_session.commit()
    await db_session.refresh(approval)

    resp = await client.post(
        f"/api/v1/approvals/{approval.id}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Verify item updated
    item_result = await db_session.execute(
        select(ItineraryItem).where(ItineraryItem.id == item["id"])
    )
    updated_item = item_result.scalar_one()
    assert updated_item.title == "Senso-ji Temple"
    assert updated_item.description == "Ancient Buddhist temple in Asakusa."


@pytest.mark.asyncio
async def test_weather_replan_approve_swaps_item_with_grounded_alternative(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """weather_replan approval must APPLY the swap — title, coords and source_ref
    all move to the grounded indoor alternative (regression: this change_type
    previously had no apply-handler, so approving did nothing)."""
    from sqlalchemy import select

    from backend.db.models import Approval, ItineraryItem, Trip

    token = await _auth(client, "weather_swap@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])

    approval = Approval(
        trip_id=trip["id"],
        proposed_by="weather_agent",
        change_type="weather_replan",
        summary="Replace outdoor item due to rain",
        payload={
            "original_item": {"id": item["id"], "title": item["title"]},
            "alternative_item": {
                "title": "Indo-Portuguese Museum",
                "description": "museum",
                "item_type": "activity",
                "is_outdoor": False,
                "latitude": 9.9623,
                "longitude": 76.2412,
                "source_provider": "overpass",
                "source_ref": "node/600348684",
            },
            "weather_condition": "Heavy rain",
        },
        status="pending",
    )
    db_session.add(approval)
    trip_result = await db_session.execute(select(Trip).where(Trip.id == trip["id"]))
    db_trip = trip_result.scalar_one()
    db_trip.status = "awaiting_approval"
    await db_session.commit()
    await db_session.refresh(approval)

    resp = await client.post(
        f"/api/v1/approvals/{approval.id}",
        json={"decision": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    item_result = await db_session.execute(
        select(ItineraryItem).where(ItineraryItem.id == item["id"])
    )
    updated = item_result.scalar_one()
    assert updated.title == "Indo-Portuguese Museum"
    assert updated.is_outdoor is False
    assert updated.source_ref == "node/600348684"
    assert float(updated.latitude) == pytest.approx(9.9623)


@pytest.mark.asyncio
async def test_weather_replan_reject_changes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from sqlalchemy import select

    from backend.db.models import Approval, ItineraryItem, Trip

    token = await _auth(client, "weather_rej@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])
    original_title = item["title"]

    approval = Approval(
        trip_id=trip["id"],
        proposed_by="weather_agent",
        change_type="weather_replan",
        summary="Replace outdoor item due to rain",
        payload={
            "original_item": {"id": item["id"], "title": original_title},
            "alternative_item": {"title": "Some Museum", "source_ref": "node/1"},
        },
        status="pending",
    )
    db_session.add(approval)
    trip_result = await db_session.execute(select(Trip).where(Trip.id == trip["id"]))
    trip_row = trip_result.scalar_one()
    trip_row.status = "awaiting_approval"
    await db_session.commit()
    await db_session.refresh(approval)

    resp = await client.post(
        f"/api/v1/approvals/{approval.id}",
        json={"decision": "rejected"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    item_result = await db_session.execute(
        select(ItineraryItem).where(ItineraryItem.id == item["id"])
    )
    assert item_result.scalar_one().title == original_title
