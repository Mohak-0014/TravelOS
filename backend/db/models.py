import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    trips: Mapped[list["Trip"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preference: Mapped["Preference | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    event_logs: Mapped[list["EventLog"]] = relationship(back_populates="user")


class Preference(Base):
    __tablename__ = "preferences"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    pace: Mapped[str | None] = mapped_column(String(20))  # relaxed|moderate|packed
    luxury_tier: Mapped[str | None] = mapped_column(String(20))  # budget|mid|luxury
    walking_tolerance: Mapped[str | None] = mapped_column(String(20))  # low|medium|high
    food_prefs: Mapped[list | None] = mapped_column(JSON, default=list)
    interests: Mapped[list | None] = mapped_column(JSON, default=list)
    budget_behavior: Mapped[str | None] = mapped_column(String(20))  # frugal|balanced|splurge
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="preference")


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="chk_trip_dates"),
        Index("idx_trips_user_id", "user_id"),
        Index("idx_trips_status", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_city: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_country: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Double)
    longitude: Mapped[float | None] = mapped_column(Double)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    num_travelers: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    budget_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    budget_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="trips")
    traveler_profiles: Mapped[list["TravelerProfile"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    itinerary_items: Mapped[list["ItineraryItem"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    hotel_candidates: Mapped[list["HotelCandidate"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    budget_logs: Mapped[list["BudgetLog"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    weather_snapshots: Mapped[list["WeatherSnapshot"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    event_logs: Mapped[list["EventLog"]] = relationship(back_populates="trip")


class TravelerProfile(Base):
    __tablename__ = "traveler_profiles"
    __table_args__ = (Index("idx_traveler_profiles_trip_id", "trip_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    trip_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    age_band: Mapped[str | None] = mapped_column(String(20))  # child|teen|adult|senior
    prefs_override: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    trip: Mapped["Trip"] = relationship(back_populates="traveler_profiles")


class ItineraryItem(Base):
    __tablename__ = "itinerary_items"
    __table_args__ = (Index("idx_itinerary_items_trip_day", "trip_id", "day_number"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    trip_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    item_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # activity|meal|transport|lodging|free
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Double)
    longitude: Mapped[float | None] = mapped_column(Double)
    address: Mapped[str | None] = mapped_column(Text)
    source_provider: Mapped[str | None] = mapped_column(String(50))
    source_ref: Mapped[str | None] = mapped_column(String(255))
    est_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    est_cost_currency: Mapped[str | None] = mapped_column(String(3))
    is_outdoor: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    trip: Mapped["Trip"] = relationship(back_populates="itinerary_items")


class HotelCandidate(Base):
    __tablename__ = "hotel_candidates"
    __table_args__ = (Index("idx_hotel_candidates_trip_id", "trip_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    trip_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # liteapi|hotelsnl
    provider_hotel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    star_rating: Mapped[float | None] = mapped_column(Numeric(2, 1))
    latitude: Mapped[float | None] = mapped_column(Double)
    longitude: Mapped[float | None] = mapped_column(Double)
    address: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    price_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_currency: Mapped[str | None] = mapped_column(String(3))
    price_per_night: Mapped[float | None] = mapped_column(Numeric(12, 2))
    meal_plan: Mapped[str | None] = mapped_column(String(20))
    refundable: Mapped[bool | None] = mapped_column(Boolean)
    booking_ref: Mapped[str | None] = mapped_column(String(255))
    match_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    trip: Mapped["Trip"] = relationship(back_populates="hotel_candidates")


class BudgetLog(Base):
    __tablename__ = "budget_logs"
    __table_args__ = (Index("idx_budget_logs_trip_id", "trip_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    trip_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # lodging|food|activity|transport
    planned_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    actual_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    note: Mapped[str | None] = mapped_column(Text)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    trip: Mapped["Trip"] = relationship(back_populates="budget_logs")


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (Index("idx_approvals_trip_status", "trip_id", "status"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    trip_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    proposed_by: Mapped[str] = mapped_column(String(50), nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    trip: Mapped["Trip"] = relationship(back_populates="approvals")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"
    __table_args__ = (Index("idx_weather_trip_date", "trip_id", "snapshot_date"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    trip_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    temp_min_c: Mapped[float | None] = mapped_column(Numeric(5, 2))
    temp_max_c: Mapped[float | None] = mapped_column(Numeric(5, 2))
    precipitation_mm: Mapped[float | None] = mapped_column(Numeric(6, 2))
    condition_code: Mapped[int | None] = mapped_column(Integer)
    is_adverse: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    trip: Mapped["Trip"] = relationship(back_populates="weather_snapshots")


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("idx_event_logs_trip_id", "trip_id"),
        Index("idx_event_logs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    trip_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("trips.id", ondelete="CASCADE")
    )
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    trip: Mapped["Trip | None"] = relationship(back_populates="event_logs")
    user: Mapped["User | None"] = relationship(back_populates="event_logs")
