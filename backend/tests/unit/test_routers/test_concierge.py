"""Unit tests for the concierge chat router."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.agents.concierge import ConciergeResponse

# ── helpers ───────────────────────────────────────────────────────────────────


async def _auth(client: AsyncClient, email: str = "concierge@test.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Pass1234!", "full_name": "Chat User"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Pass1234!"}
    )
    return resp.json()["access_token"]


async def _create_trip(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/api/v1/trips",
        json={
            "title": "Kyoto Trip",
            "destination_city": "Kyoto",
            "start_date": "2026-10-01",
            "end_date": "2026-10-03",
            "num_travelers": 1,
            "budget_total": 800,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── chat endpoint ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_returns_answer_and_sources(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)

    mock_response = ConciergeResponse(
        answer="Fushimi Inari has 10,000 torii gates!",
        sources=[{"title": "Fushimi Inari Shrine", "url": "http://example.com"}],
        proposal_id=None,
    )

    with patch(
        "backend.api.routers.concierge.concierge_agent.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = mock_response
        resp = await client.post(
            f"/api/v1/trips/{trip['id']}/chat",
            json={"question": "Tell me about Fushimi Inari"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Fushimi Inari has 10,000 torii gates!"
    assert len(body["sources"]) == 1
    assert body["proposal_id"] is None


@pytest.mark.asyncio
async def test_chat_forwards_correct_args_to_agent(client: AsyncClient) -> None:
    token = await _auth(client, "args@test.com")
    trip = await _create_trip(client, token)

    mock_response = ConciergeResponse(answer="ok", sources=[], proposal_id=None)

    with patch(
        "backend.api.routers.concierge.concierge_agent.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = mock_response
        await client.post(
            f"/api/v1/trips/{trip['id']}/chat",
            json={"question": "Best ramen spots?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    call_kwargs = mock_ask.call_args.kwargs
    assert call_kwargs["trip_id"] == trip["id"]
    assert call_kwargs["question"] == "Best ramen spots?"


@pytest.mark.asyncio
async def test_chat_returns_proposal_id_when_present(client: AsyncClient) -> None:
    token = await _auth(client, "proposal@test.com")
    trip = await _create_trip(client, token)

    mock_response = ConciergeResponse(
        answer="I've proposed replacing Day 1 activity — please review.",
        sources=[],
        proposal_id="abc123-approval-uuid",
    )

    with patch(
        "backend.api.routers.concierge.concierge_agent.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = mock_response
        resp = await client.post(
            f"/api/v1/trips/{trip['id']}/chat",
            json={"question": "Swap Day 1 with Arashiyama Bamboo Grove"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["proposal_id"] == "abc123-approval-uuid"


@pytest.mark.asyncio
async def test_chat_trip_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "chat404@test.com")
    resp = await client.post(
        "/api/v1/trips/no-such-trip/chat",
        json={"question": "Hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_chat_other_user_trip_404(client: AsyncClient) -> None:
    token_a = await _auth(client, "chat_owner@test.com")
    token_b = await _auth(client, "chat_spy@test.com")
    trip = await _create_trip(client, token_a)

    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/chat",
        json={"question": "Can I see this?"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/trips/any-trip/chat",
        json={"question": "Hello"},
    )
    assert resp.status_code == 401
