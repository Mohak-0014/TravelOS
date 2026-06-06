import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Preference, User


@pytest.mark.asyncio
async def test_user_orm_round_trip(db_session: AsyncSession) -> None:
    user = User(
        email="test@example.com",
        hashed_password="hashed",
        full_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.is_active is True


@pytest.mark.asyncio
async def test_preference_created_with_user(db_session: AsyncSession) -> None:
    user = User(email="pref@example.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    pref = Preference(
        user_id=user.id,
        pace="moderate",
        luxury_tier="mid",
        interests=["museums", "food"],
    )
    db_session.add(pref)
    await db_session.commit()
    await db_session.refresh(pref)

    assert pref.user_id == user.id
    assert pref.interests == ["museums", "food"]
