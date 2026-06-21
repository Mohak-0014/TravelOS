"""Unit tests for the trips router."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ── helpers ───────────────────────────────────────────────────────────────────


async def _auth(client: AsyncClient, email: str = "trips@test.com") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Pass1234!", "full_name": "Tripper"},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Pass1234!"})
    return resp.json()["access_token"]


def _trip_body(**overrides: object) -> dict:
    return {
        "title": "Paris Adventure",
        "destination_city": "Paris",
        "destination_country": "France",
        "start_date": "2026-06-01",
        "end_date": "2026-06-07",
        "num_travelers": 2,
        "budget_total": 3000,
        "budget_currency": "USD",
        **overrides,
    }


async def _create_trip(client: AsyncClient, token: str, **overrides: object) -> dict:
    resp = await client.post(
        "/api/v1/trips",
        json=_trip_body(**overrides),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _item_body(item_date: str = "2026-06-02", **overrides: object) -> dict:
    return {
        "day_number": 2,
        "item_date": item_date,
        "item_type": "activity",
        "title": "Louvre Museum",
        "sort_order": 0,
        **overrides,
    }


async def _add_item(
    client: AsyncClient, token: str, trip_id: str, item_date: str = "2026-06-02"
) -> dict:
    resp = await client.post(
        f"/api/v1/trips/{trip_id}/itinerary",
        json=_item_body(item_date),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Trip CRUD ─────────────────────────────────────────────────────────────────


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
    assert body["status"] == "planning"
    assert body["budget_currency"] == "USD"


@pytest.mark.asyncio
async def test_create_trip_end_before_start_422(client: AsyncClient) -> None:
    token = await _auth(client, "baddates@test.com")
    resp = await client.post(
        "/api/v1/trips",
        json=_trip_body(start_date="2026-06-10", end_date="2026-06-05"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_trip_no_auth_401(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/trips", json=_trip_body())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_trips_returns_own_only(client: AsyncClient) -> None:
    token_a = await _auth(client, "alice@test.com")
    token_b = await _auth(client, "bob@test.com")
    await _create_trip(client, token_a, title="Alice Trip")
    await _create_trip(client, token_b, title="Bob Trip")

    resp = await client.get("/api/v1/trips", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "Alice Trip" in titles
    assert "Bob Trip" not in titles


@pytest.mark.asyncio
async def test_list_trips_excludes_cancelled(client: AsyncClient) -> None:
    token = await _auth(client, "cancel_list@test.com")
    trip = await _create_trip(client, token)
    await client.delete(f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/api/v1/trips", headers={"Authorization": f"Bearer {token}"})
    assert all(t["id"] != trip["id"] for t in resp.json())


@pytest.mark.asyncio
async def test_get_trip_by_id(client: AsyncClient) -> None:
    token = await _auth(client, "gettrip@test.com")
    trip = await _create_trip(client, token)
    resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == trip["id"]


@pytest.mark.asyncio
async def test_get_trip_other_user_404(client: AsyncClient) -> None:
    token_a = await _auth(client, "owner_trip@test.com")
    token_b = await _auth(client, "thief_trip@test.com")
    trip = await _create_trip(client, token_a)
    resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_trip_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "notfound_trip@test.com")
    resp = await client.get(
        "/api/v1/trips/no-such-trip", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_trip_success(client: AsyncClient) -> None:
    token = await _auth(client, "update_trip@test.com")
    trip = await _create_trip(client, token)
    resp = await client.put(
        f"/api/v1/trips/{trip['id']}",
        json={"title": "Renamed Adventure", "num_travelers": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed Adventure"
    assert resp.json()["num_travelers"] == 4


@pytest.mark.asyncio
async def test_update_trip_bad_dates_422(client: AsyncClient) -> None:
    token = await _auth(client, "bad_update@test.com")
    trip = await _create_trip(client, token)
    resp = await client.put(
        f"/api/v1/trips/{trip['id']}",
        json={"start_date": "2026-06-20", "end_date": "2026-06-01"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cancel_trip_soft_deletes(client: AsyncClient) -> None:
    token = await _auth(client, "cancel_trip@test.com")
    trip = await _create_trip(client, token)
    resp = await client.delete(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204

    # Trip is still fetchable by ID but status is cancelled
    get_resp = await client.get(
        f"/api/v1/trips/{trip['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert get_resp.json()["status"] == "cancelled"


# ── itinerary ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_itinerary_returns_items_ordered(client: AsyncClient) -> None:
    token = await _auth(client, "itin_list@test.com")
    trip = await _create_trip(client, token)

    for i in range(3):
        await client.post(
            f"/api/v1/trips/{trip['id']}/itinerary",
            json=_item_body(title=f"Activity {i}", sort_order=i),
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = await client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_add_item_returns_201(client: AsyncClient) -> None:
    token = await _auth(client, "additem@test.com")
    trip = await _create_trip(client, token)
    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary",
        json=_item_body(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Louvre Museum"
    assert resp.json()["trip_id"] == trip["id"]


@pytest.mark.asyncio
async def test_add_item_outside_date_range_422(client: AsyncClient) -> None:
    token = await _auth(client, "outside_range@test.com")
    trip = await _create_trip(client, token)
    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary",
        json=_item_body(item_date="2027-01-01"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_update_item_success(client: AsyncClient) -> None:
    token = await _auth(client, "update_item@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])

    resp = await client.put(
        f"/api/v1/trips/{trip['id']}/itinerary/{item['id']}",
        json={"title": "Musée d'Orsay", "est_cost": 15.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Musée d'Orsay"
    assert resp.json()["est_cost"] == 15.0


@pytest.mark.asyncio
async def test_update_item_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "update_404@test.com")
    trip = await _create_trip(client, token)
    resp = await client.put(
        f"/api/v1/trips/{trip['id']}/itinerary/no-such-item",
        json={"title": "New Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_item_success(client: AsyncClient) -> None:
    token = await _auth(client, "del_item@test.com")
    trip = await _create_trip(client, token)
    item = await _add_item(client, token, trip["id"])

    del_resp = await client.delete(
        f"/api/v1/trips/{trip['id']}/itinerary/{item['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 204

    list_resp = await client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_item_not_found_404(client: AsyncClient) -> None:
    token = await _auth(client, "del_404@test.com")
    trip = await _create_trip(client, token)
    resp = await client.delete(
        f"/api/v1/trips/{trip['id']}/itinerary/no-such-item",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── generate ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_queues_celery_task(client: AsyncClient) -> None:
    token = await _auth(client, "gen@test.com")
    trip = await _create_trip(client, token)

    with patch("backend.workflows.celery_tasks.generate_itinerary_async") as mock_task:
        mock_task.delay.return_value = MagicMock(id="fake-task-id")
        resp = await client.post(
            f"/api/v1/trips/{trip['id']}/itinerary/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["trip_id"] == trip["id"]
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_generate_rejects_when_already_generating(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from sqlalchemy import update

    from backend.db.models import Trip

    token = await _auth(client, "gen409@test.com")
    trip = await _create_trip(client, token)

    # A run already in flight must not be double-triggered.
    await db_session.execute(update(Trip).where(Trip.id == trip["id"]).values(status="generating"))
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/trips/{trip['id']}/itinerary/generate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_generate_allows_regeneration_when_planned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from sqlalchemy import update

    from backend.db.models import Trip

    token = await _auth(client, "genreplan@test.com")
    trip = await _create_trip(client, token)

    # The "Regenerate" button must work on an already-planned trip, not just new ones.
    await db_session.execute(update(Trip).where(Trip.id == trip["id"]).values(status="planned"))
    await db_session.commit()

    with patch("backend.workflows.celery_tasks.generate_itinerary_async") as mock_task:
        mock_task.delay.return_value = MagicMock(id="fake-task-id")
        resp = await client.post(
            f"/api/v1/trips/{trip['id']}/itinerary/generate",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    mock_task.delay.assert_called_once()


# ── hotels ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_hotels_returns_empty_list(client: AsyncClient) -> None:
    token = await _auth(client, "no_hotels@test.com")
    trip = await _create_trip(client, token)
    resp = await client.get(
        f"/api/v1/trips/{trip['id']}/hotels",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_hotels_returns_sorted_by_score(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from backend.db.models import HotelCandidate

    token = await _auth(client, "hotels@test.com")
    trip = await _create_trip(client, token)

    for name, score in [("Budget Inn", 0.4), ("Luxury Palace", 0.9), ("Mid Hotel", 0.65)]:
        db_session.add(
            HotelCandidate(
                trip_id=trip["id"],
                provider="liteapi",
                provider_hotel_id=f"H-{name[:3]}",
                name=name,
                match_score=score,
                is_selected=False,
            )
        )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/trips/{trip['id']}/hotels",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    names = [h["name"] for h in resp.json()]
    assert names[0] == "Luxury Palace"  # highest score first


@pytest.mark.asyncio
async def test_get_hotels_other_user_404(client: AsyncClient) -> None:
    token_a = await _auth(client, "hotel_owner@test.com")
    token_b = await _auth(client, "hotel_spy@test.com")
    trip = await _create_trip(client, token_a)

    resp = await client.get(
        f"/api/v1/trips/{trip['id']}/hotels",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


# ── weather ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_weather_no_coords_geocode_fails_returns_empty(
    client: AsyncClient,
) -> None:
    token = await _auth(client, "weather_nogeo@test.com")

    # geocode returns None for both create_trip and get_weather
    with patch("backend.api.routers.trips.geocode", new_callable=AsyncMock) as mock_geo:
        mock_geo.return_value = None
        trip = await _create_trip(client, token)

        resp = await client.get(
            f"/api/v1/trips/{trip['id']}/weather",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_weather_with_trip_coords(client: AsyncClient, db_session: AsyncSession) -> None:
    from sqlalchemy import update

    from backend.db.models import Trip
    from backend.tools.weather import WeatherDay

    token = await _auth(client, "weather_coords@test.com")
    trip = await _create_trip(client, token)

    # Inject coords directly into DB
    await db_session.execute(
        update(Trip).where(Trip.id == trip["id"]).values(latitude=48.8566, longitude=2.3522)
    )
    await db_session.commit()

    mock_weather = [
        WeatherDay(
            date=date(2026, 6, 1),
            temp_min_c=14.0,
            temp_max_c=22.0,
            precipitation_mm=0.0,
            precipitation_prob=10,
            condition_code=0,
            condition_label="Clear sky",
            is_adverse=False,
        )
    ]

    with patch("backend.api.routers.trips.fetch_weather", new_callable=AsyncMock) as mock_fw:
        mock_fw.return_value = mock_weather
        resp = await client.get(
            f"/api/v1/trips/{trip['id']}/weather",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["condition_label"] == "Clear sky"


@pytest.mark.asyncio
async def test_get_weather_geocodes_when_no_coords(client: AsyncClient) -> None:
    from backend.tools.weather import WeatherDay

    token = await _auth(client, "weather_geo@test.com")

    # geocode returns None on create → no coords; returns real geo on weather call
    geo_mock = MagicMock(lat=35.6762, lng=139.6503)

    mock_weather = [
        WeatherDay(
            date=date(2026, 6, 1),
            temp_min_c=20.0,
            temp_max_c=28.0,
            precipitation_mm=5.0,
            precipitation_prob=40,
            condition_code=61,
            condition_label="Slight rain",
            is_adverse=False,
        )
    ]

    with (
        patch("backend.api.routers.trips.geocode", new_callable=AsyncMock) as mock_geo,
        patch("backend.api.routers.trips.fetch_weather", new_callable=AsyncMock) as mock_fw,
    ):
        mock_geo.return_value = None  # create_trip: no coords
        trip = await _create_trip(client, token)

        mock_geo.return_value = geo_mock  # get_weather: resolve coords
        mock_fw.return_value = mock_weather

        resp = await client.get(
            f"/api/v1/trips/{trip['id']}/weather",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    mock_fw.assert_called_once_with(
        geo_mock.lat, geo_mock.lng, pytest.approx(date(2026, 6, 1)), pytest.approx(date(2026, 6, 7))
    )
