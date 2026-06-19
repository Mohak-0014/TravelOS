"""Unit tests for auth + preferences router."""

import pytest
from httpx import AsyncClient

# ── helpers ───────────────────────────────────────────────────────────────────


async def _register(
    client: AsyncClient,
    email: str = "user@example.com",
    password: str = "Pass1234!",
    full_name: str = "Test User",
) -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    return resp.json() | {"_status": resp.status_code}


async def _login(client: AsyncClient, email: str = "user@example.com") -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Pass1234!"},
    )
    return resp.json()["access_token"]


async def _auth(client: AsyncClient, email: str = "user@example.com") -> str:
    await _register(client, email)
    return await _login(client, email)


# ── register ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_201_with_correct_fields(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "reg@test.com", "password": "Abc123!", "full_name": "Reg User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "reg@test.com"
    assert body["full_name"] == "Reg User"
    assert body["is_active"] is True
    assert "hashed_password" not in body
    assert "id" in body


@pytest.mark.asyncio
async def test_register_duplicate_email_422(client: AsyncClient) -> None:
    for _ in range(2):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "dup@test.com", "password": "Pass1!", "full_name": "Dup"},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


# ── login ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_returns_bearer_token(client: AsyncClient) -> None:
    await _register(client, "login@test.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.com", "password": "Pass1234!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password_401(client: AsyncClient) -> None:
    await _register(client, "wp@test.com")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wp@test.com", "password": "WRONG_PASSWORD"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.asyncio
async def test_login_unknown_email_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nowhere.com", "password": "anything"},
    )
    assert resp.status_code == 401


# ── /me ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_me_returns_current_user(client: AsyncClient) -> None:
    token = await _auth(client, "getme@test.com")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "getme@test.com"


@pytest.mark.asyncio
async def test_get_me_no_token_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_me_changes_full_name(client: AsyncClient) -> None:
    token = await _auth(client, "updateme@test.com")
    resp = await client.put(
        "/api/v1/auth/me",
        json={"full_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_me_ignores_unknown_fields(client: AsyncClient) -> None:
    token = await _auth(client, "ignoreme@test.com")
    resp = await client.put(
        "/api/v1/auth/me",
        json={"full_name": "New Name", "is_admin": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json().get("is_admin") is None


# ── preferences ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_preferences_returns_row_created_at_register(client: AsyncClient) -> None:
    token = await _auth(client, "prefs@test.com")
    resp = await client.get("/api/v1/preferences", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_preferences_persists_values(client: AsyncClient) -> None:
    token = await _auth(client, "prefs2@test.com")
    resp = await client.put(
        "/api/v1/preferences",
        json={"pace": "relaxed", "luxury_tier": "budget", "budget_behavior": "frugal"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pace"] == "relaxed"
    assert body["luxury_tier"] == "budget"
    assert body["budget_behavior"] == "frugal"


@pytest.mark.asyncio
async def test_get_preferences_returns_updated_values(client: AsyncClient) -> None:
    token = await _auth(client, "prefs3@test.com")
    await client.put(
        "/api/v1/preferences",
        json={"pace": "packed", "interests": ["food", "museums"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get("/api/v1/preferences", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["pace"] == "packed"
    assert "food" in body["interests"]


@pytest.mark.asyncio
async def test_update_preferences_partial_update(client: AsyncClient) -> None:
    token = await _auth(client, "partial@test.com")
    await client.put(
        "/api/v1/preferences",
        json={"pace": "moderate"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Update only budget_behavior, pace should stay
    resp = await client.put(
        "/api/v1/preferences",
        json={"budget_behavior": "splurge"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["budget_behavior"] == "splurge"


@pytest.mark.asyncio
async def test_preferences_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/preferences")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_preferences_require_auth(client: AsyncClient) -> None:
    resp = await client.put("/api/v1/preferences", json={"pace": "relaxed"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_forbidden_403(client: AsyncClient, db_session) -> None:
    """Inactive users get 403 on protected endpoints (covers dependencies.py:41)."""
    from sqlalchemy import update

    from backend.db.models import User

    token = await _auth(client, "inactive@test.com")

    # Deactivate the user directly in the DB
    await db_session.execute(
        update(User).where(User.email == "inactive@test.com").values(is_active=False)
    )
    await db_session.commit()

    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_preferences_not_found_if_no_row(client: AsyncClient, db_session) -> None:
    """GET /preferences returns 404 if the preference row was deleted (covers auth.py:99)."""
    from sqlalchemy import delete, select

    from backend.db.models import Preference, User

    token = await _auth(client, "nopref@test.com")

    # Delete the auto-created preference row
    result = await db_session.execute(select(User).where(User.email == "nopref@test.com"))
    user = result.scalar_one()
    await db_session.execute(delete(Preference).where(Preference.user_id == user.id))
    await db_session.commit()

    resp = await client.get("/api/v1/preferences", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_preferences_creates_row_if_missing(client: AsyncClient, db_session) -> None:
    """PUT /preferences auto-creates the pref row if it was deleted (covers auth.py:114-115)."""
    from sqlalchemy import delete, select

    from backend.db.models import Preference, User

    token = await _auth(client, "autopref@test.com")

    result = await db_session.execute(select(User).where(User.email == "autopref@test.com"))
    user = result.scalar_one()
    await db_session.execute(delete(Preference).where(Preference.user_id == user.id))
    await db_session.commit()

    resp = await client.put(
        "/api/v1/preferences",
        json={"pace": "relaxed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["pace"] == "relaxed"
