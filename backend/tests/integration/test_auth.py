import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Preference, User


# ── helpers ──────────────────────────────────────────────────────────────────

async def _register(client: AsyncClient, email: str = "test@example.com") -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Secret123!", "full_name": "Test User"},
    )
    return resp


async def _login(client: AsyncClient, email: str = "test@example.com") -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secret123!"},
    )
    return resp.json()["access_token"]


# ── register ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_returns_201_with_user_out(client: AsyncClient) -> None:
    resp = await _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "test@example.com"
    assert body["full_name"] == "Test User"
    assert body["is_active"] is True
    assert "hashed_password" not in body


@pytest.mark.asyncio
async def test_register_creates_preference_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await _register(client)
    user_id = resp.json()["id"]
    result = await db_session.execute(
        select(Preference).where(Preference.user_id == user_id)
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_422(client: AsyncClient) -> None:
    await _register(client)
    resp = await _register(client)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


# ── login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_returns_token(client: AsyncClient) -> None:
    await _register(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Secret123!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    await _register(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "WRONG"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_with_valid_token_returns_200(client: AsyncClient) -> None:
    await _register(client)
    token = await _login(client)
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_me_without_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_garbage_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert resp.status_code == 401


# ── preferences ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_preferences_persists_values(client: AsyncClient) -> None:
    await _register(client)
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.put(
        "/api/v1/preferences",
        json={"pace": "relaxed", "luxury_tier": "mid", "interests": ["museums", "food"]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pace"] == "relaxed"
    assert body["interests"] == ["museums", "food"]


@pytest.mark.asyncio
async def test_get_preferences_returns_saved_values(client: AsyncClient) -> None:
    await _register(client)
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.put(
        "/api/v1/preferences",
        json={"pace": "packed", "budget_behavior": "frugal"},
        headers=headers,
    )
    resp = await client.get("/api/v1/preferences", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["pace"] == "packed"
    assert resp.json()["budget_behavior"] == "frugal"


@pytest.mark.asyncio
async def test_preferences_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/preferences")
    assert resp.status_code == 401
