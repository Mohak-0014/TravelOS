from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ── Auth ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: str
    password: str


# ── Preferences ──────────────────────────────────────────────────────────────

class PreferenceUpdate(BaseModel):
    pace: str | None = None
    luxury_tier: str | None = None
    walking_tolerance: str | None = None
    food_prefs: list[str] | None = None
    interests: list[str] | None = None
    budget_behavior: str | None = None


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    pace: str | None
    luxury_tier: str | None
    walking_tolerance: str | None
    food_prefs: list[str] | None
    interests: list[str] | None
    budget_behavior: str | None
    updated_at: datetime


# ── Trips ────────────────────────────────────────────────────────────────────

class TripCreate(BaseModel):
    title: str
    destination_city: str
    destination_country: str | None = None
    start_date: date
    end_date: date
    num_travelers: int = 1
    budget_total: float | None = None
    budget_currency: str = "USD"


class TripUpdate(BaseModel):
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    num_travelers: int | None = None
    budget_total: float | None = None
    budget_currency: str | None = None


class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    destination_city: str
    destination_country: str | None
    latitude: float | None
    longitude: float | None
    start_date: date
    end_date: date
    num_travelers: int
    budget_total: float | None
    budget_currency: str
    status: str
    created_at: datetime
    updated_at: datetime


# ── Itinerary ────────────────────────────────────────────────────────────────

class ItineraryItemCreate(BaseModel):
    day_number: int
    item_date: date
    start_time: str | None = None
    end_time: str | None = None
    item_type: str
    title: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    source_provider: str | None = None
    source_ref: str | None = None
    est_cost: float | None = None
    est_cost_currency: str | None = None
    is_outdoor: bool = False
    sort_order: int = 0


class ItineraryItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    est_cost: float | None = None
    sort_order: int | None = None
    is_outdoor: bool | None = None


class ItineraryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    day_number: int
    item_date: date
    start_time: Any | None
    end_time: Any | None
    item_type: str
    title: str
    description: str | None
    latitude: float | None
    longitude: float | None
    address: str | None
    source_provider: str | None
    source_ref: str | None
    est_cost: float | None
    est_cost_currency: str | None
    is_outdoor: bool
    sort_order: int


# ── Approvals ─────────────────────────────────────────────────────────────────

class ApprovalDecision(BaseModel):
    decision: str  # "approved" | "rejected"
    resolution_note: str | None = None


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trip_id: str
    proposed_by: str
    change_type: str
    summary: str
    payload: dict
    status: str
    created_at: datetime
    resolved_at: datetime | None
