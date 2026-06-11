import pytest
from httpx import AsyncClient

# ── helpers ──────────────────────────────────────────────────────────────────


async def _auth(client: AsyncClient, email: str = "traveler@example.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Pass1234!", "full_name": "Traveler"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Pass1234!"},
    )
    return resp.json()["access_token"]


def _trip_body(
    *,
    title: str = "Paris Adventure",
    destination_city: str = "Paris",
    start_date: str = "2025-06-01",
    end_date: str = "2025-06-07",
) -> dict:
    return {
        "title": title,
        "destination_city": destination_city,
        "start_date": start_date,
        "end_date": end_date,
        "num_travelers": 2,
        "budget_total": 3000,
        "budget_currency": "USD",
    }


async def _create_trip(client: AsyncClient, token: str, **overrides) -> dict:
    body = {**_trip_body(), **overrides}
    resp = await client.post(
        "/api/v1/trips", json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    return resp.json()


# ── trip CRUD ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_trip_returns_201(client: AsyncClient) -> None:
    token = await _auth(client)
    resp = await client.post(
        "/api/v1/trips",
        json=_trip_body(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Paris Adventure"
    assert body["destination_city"] == "Paris"
    assert body["status"] == "planning"
    assert body["budget_currency"] == "USD"


@pytest.mark.asyncio
async def test_create_trip_end_before_start_422(client: AsyncClient) -> None:
    token = await _auth(client)
    resp = await client.post(
        "/api/v1/trips",
        json=_trip_body(start_date="2025-06-10", end_date="2025-06-05"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_list_trips_returns_own_trips_only(client: AsyncClient) -> None:
    token_a = await _auth(client, "user_a@example.com")
    token_b = await _auth(client, "user_b@example.com")

    await _create_trip(client, token_a, title="User A Trip")
    await _create_trip(client, token_b, title="User B Trip")

    resp = await client.get("/api/v1/trips", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "User A Trip" in titles
    assert "User B Trip" not in titles


@pytest.mark.asyncio
async def test_get_trip_by_id(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == trip["id"]


@pytest.mark.asyncio
async def test_get_trip_other_user_returns_404(client: AsyncClient) -> None:
    token_a = await _auth(client, "owner@example.com")
    token_b = await _auth(client, "intruder@example.com")

    trip = await _create_trip(client, token_a)
    resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_trip(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    resp = await client.put(
        f"/api/v1/trips/{trip['id']}",
        json={"title": "Updated Title", "num_travelers": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"
    assert resp.json()["num_travelers"] == 4


@pytest.mark.asyncio
async def test_soft_delete_trip(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)

    resp = await client.delete(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204

    # Should disappear from list (cancelled trips excluded)
    list_resp = await client.get("/api/v1/trips", headers={"Authorization": f"Bearer {token}"})
    assert all(t["id"] != trip["id"] for t in list_resp.json())


@pytest.mark.asyncio
async def test_cancelled_trip_still_fetchable_by_id(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    await client.delete(f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"})

    resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


# ── itinerary ─────────────────────────────────────────────────────────────────


def _item_body(item_date: str = "2025-06-02") -> dict:
    return {
        "day_number": 2,
        "item_date": item_date,
        "item_type": "activity",
        "title": "Louvre Museum",
        "source_provider": "opentripmap",
        "source_ref": "W12345",
        "is_outdoor": False,
        "sort_order": 0,
    }


@pytest.mark.asyncio
async def test_add_itinerary_item_returns_201(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary",
        json=_item_body(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Louvre Museum"
    assert body["source_provider"] == "opentripmap"
    assert body["trip_id"] == trip["id"]


@pytest.mark.asyncio
async def test_add_item_outside_date_range_422(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token, start_date="2025-06-01", end_date="2025-06-07")
    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary",
        json=_item_body(item_date="2025-07-15"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_itinerary_items(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)

    for sort in range(3):
        body = {**_item_body(), "sort_order": sort, "title": f"Activity {sort}"}
        await client.post(
            f"/api/v1/trips/{trip['id']}/itinerary",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_update_itinerary_item(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    item_resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary",
        json=_item_body(),
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = item_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/trips/{trip['id']}/itinerary/{item_id}",
        json={"title": "Musée d'Orsay", "est_cost": 15.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Musée d'Orsay"


@pytest.mark.asyncio
async def test_delete_itinerary_item(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    item_resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary",
        json=_item_body(),
        headers={"Authorization": f"Bearer {token}"},
    )
    item_id = item_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/trips/{trip['id']}/itinerary/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_generate_itinerary_returns_not_implemented(client: AsyncClient) -> None:
    token = await _auth(client)
    trip = await _create_trip(client, token)
    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_implemented"
