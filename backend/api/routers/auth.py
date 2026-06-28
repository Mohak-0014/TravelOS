from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_active_user
from backend.api.rate_limit import limiter
from backend.core.config import settings
from backend.core.security import create_access_token, hash_password, verify_password
from backend.db.base import get_db
from backend.db.models import Preference, User
from backend.db.schemas import (
    LoginRequest,
    PreferenceOut,
    PreferenceUpdate,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Precomputed bcrypt hash used to equalize login timing when the email is unknown,
# so an attacker can't distinguish "no such user" from "wrong password" by latency.
_DUMMY_PASSWORD_HASH = hash_password("timing-equalization-decoy")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "Email already registered."},
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()

    # Create empty preference row so agents always have something to load
    pref = Preference(user_id=user.id)
    db.add(pref)

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Always run one bcrypt verify (even for unknown emails) to keep response time
    # constant and avoid a user-enumeration timing oracle.
    hashed = user.hashed_password if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, hashed)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "Invalid email or password."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user


@router.put("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if body.full_name is not None:
        current_user.full_name = body.full_name
    await db.commit()
    await db.refresh(current_user)
    return current_user


# ── Preferences (also lives under auth since they're user-scoped) ──────────

preferences_router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])


@preferences_router.get("", response_model=PreferenceOut)
async def get_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Preference:
    result = await db.execute(select(Preference).where(Preference.user_id == current_user.id))
    pref = result.scalar_one_or_none()
    if pref is None:
        raise HTTPException(
            status_code=404, detail={"code": "NOT_FOUND", "message": "Preferences not found."}
        )
    return pref


@preferences_router.put("", response_model=PreferenceOut)
async def update_preferences(
    body: PreferenceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Preference:
    result = await db.execute(select(Preference).where(Preference.user_id == current_user.id))
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = Preference(user_id=current_user.id)
        db.add(pref)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)
    return pref
