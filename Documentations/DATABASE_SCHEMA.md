# TravelOS — Database Schema

> **PostgreSQL 16.** This is the authoritative data contract. Agents and code must use these exact
> table and column names. Do not guess. ORM models live in `backend/db/models.py`.

---

## 1. Entity-Relationship Overview

```
users (1) ───< (N) trips
trips (1) ───< (N) traveler_profiles
trips (1) ───< (N) itinerary_items
trips (1) ───< (N) hotel_candidates
trips (1) ───< (N) budget_logs
trips (1) ───< (N) approvals
trips (1) ───< (N) event_logs
users (1) ───< (N) preferences
users (1) ───< (N) trips ───< (N) weather_snapshots
```

**Textual description of relationships**

- A **user** owns many **trips**. Deleting a user cascades to their trips.
- A **trip** has many **traveler_profiles** (solo = 1 row; group trips = many).
- A **trip** has many **itinerary_items** (one row per activity/meal/transport block per day).
- A **trip** has many **hotel_candidates** (normalized results from LiteAPI/Hotels.nl), one of which may be `is_selected = true`.
- A **trip** has many **budget_logs** (planned vs. actual spend entries).
- A **trip** has many **approvals** (human-in-the-loop requests, each with a status).
- A **trip** has many **event_logs** (audit trail of agent actions and triggers).
- A **trip** has many **weather_snapshots** (Open-Meteo poll results over time).
- A **user** has many **preferences** (key-value preference profile; mirrored as embeddings in Qdrant).

Long-term **semantic memory** (preference embeddings, past-trip summaries) lives in **Qdrant**, keyed by `user_id`. LangGraph **checkpoints** are stored in their own `langgraph_checkpoints` table (managed by the LangGraph Postgres checkpointer).

---

## 2. DDL

```sql
-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- PREFERENCES  (structured travel-style profile per user)
-- ============================================================
CREATE TABLE preferences (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pace            VARCHAR(20),      -- 'relaxed' | 'moderate' | 'packed'
    luxury_tier     VARCHAR(20),      -- 'budget' | 'mid' | 'luxury'
    walking_tolerance VARCHAR(20),    -- 'low' | 'medium' | 'high'
    food_prefs      JSONB DEFAULT '[]'::jsonb,   -- ['vegetarian','no-pork',...]
    interests       JSONB DEFAULT '[]'::jsonb,   -- ['museums','nightlife','nature',...]
    budget_behavior VARCHAR(20),      -- 'frugal' | 'balanced' | 'splurge'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

-- ============================================================
-- TRIPS
-- ============================================================
CREATE TABLE trips (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    destination_city VARCHAR(255) NOT NULL,
    destination_country VARCHAR(2),  -- ISO 3166-1 alpha-2
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    num_travelers   INTEGER NOT NULL DEFAULT 1,
    budget_total    NUMERIC(12,2),
    budget_currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status          VARCHAR(20) NOT NULL DEFAULT 'planning',
                    -- 'planning' | 'active' | 'completed' | 'cancelled'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_date >= start_date)
);
CREATE INDEX idx_trips_user_id ON trips(user_id);
CREATE INDEX idx_trips_status ON trips(status);

-- ============================================================
-- TRAVELER PROFILES  (per-traveler within a trip; supports groups)
-- ============================================================
CREATE TABLE traveler_profiles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    display_name    VARCHAR(255) NOT NULL,
    is_lead         BOOLEAN NOT NULL DEFAULT FALSE,
    age_band        VARCHAR(20),      -- 'child' | 'teen' | 'adult' | 'senior'
    prefs_override  JSONB DEFAULT '{}'::jsonb,  -- per-traveler overrides
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_traveler_profiles_trip_id ON traveler_profiles(trip_id);

-- ============================================================
-- ITINERARY ITEMS
-- ============================================================
CREATE TABLE itinerary_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number      INTEGER NOT NULL,         -- 1-based day index
    item_date       DATE NOT NULL,
    start_time      TIME,
    end_time        TIME,
    item_type       VARCHAR(20) NOT NULL,     -- 'activity'|'meal'|'transport'|'lodging'|'free'
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    address         TEXT,
    source_provider VARCHAR(50),              -- 'opentripmap'|'foursquare'|'liteapi'|'hotelsnl'|'ai'
    source_ref      VARCHAR(255),             -- external provider id (grounding ref)
    est_cost        NUMERIC(12,2),
    est_cost_currency VARCHAR(3),
    is_outdoor      BOOLEAN DEFAULT FALSE,     -- used by weather replanning
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_itinerary_items_trip_day ON itinerary_items(trip_id, day_number);

-- ============================================================
-- HOTEL CANDIDATES  (normalized from LiteAPI / Hotels.nl)
-- ============================================================
CREATE TABLE hotel_candidates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    provider        VARCHAR(20) NOT NULL,     -- 'liteapi' | 'hotelsnl'
    provider_hotel_id VARCHAR(255) NOT NULL,  -- external id (grounding ref)
    name            VARCHAR(255) NOT NULL,
    star_rating     NUMERIC(2,1),
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    address         TEXT,
    image_url       TEXT,
    price_total     NUMERIC(12,2),
    price_currency  VARCHAR(3),
    price_per_night NUMERIC(12,2),
    meal_plan       VARCHAR(20),              -- 'nomeal'|'breakfast'|...
    refundable      BOOLEAN,
    booking_ref     VARCHAR(255),             -- e.g. hotelsnl_hash / liteapi rateId
    match_score     NUMERIC(4,3),             -- agent's style/budget match (0-1)
    is_selected     BOOLEAN NOT NULL DEFAULT FALSE,
    raw_payload     JSONB,                    -- original provider response (audit)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_hotel_candidates_trip_id ON hotel_candidates(trip_id);

-- ============================================================
-- BUDGET LOGS
-- ============================================================
CREATE TABLE budget_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    category        VARCHAR(20) NOT NULL,     -- 'lodging'|'food'|'activity'|'transport'
    planned_amount  NUMERIC(12,2) NOT NULL DEFAULT 0,
    actual_amount   NUMERIC(12,2) NOT NULL DEFAULT 0,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    note            TEXT,
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_budget_logs_trip_id ON budget_logs(trip_id);

-- ============================================================
-- APPROVALS  (human-in-the-loop queue)
-- ============================================================
CREATE TABLE approvals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    proposed_by     VARCHAR(50) NOT NULL,     -- agent name
    change_type     VARCHAR(50) NOT NULL,     -- 'reroute'|'hotel_change'|'delete_item'|'budget_exceed'|'weather_replan'
    summary         TEXT NOT NULL,            -- human-readable description
    payload         JSONB NOT NULL,           -- structured diff to apply if approved
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- 'pending' | 'approved' | 'rejected' | 'expired'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);
CREATE INDEX idx_approvals_trip_status ON approvals(trip_id, status);

-- ============================================================
-- WEATHER SNAPSHOTS  (Open-Meteo poll history)
-- ============================================================
CREATE TABLE weather_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    snapshot_date   DATE NOT NULL,
    temp_min_c      NUMERIC(5,2),
    temp_max_c      NUMERIC(5,2),
    precipitation_mm NUMERIC(6,2),
    condition_code  INTEGER,                  -- WMO weather code
    is_adverse      BOOLEAN NOT NULL DEFAULT FALSE,  -- triggers replan check
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_weather_trip_date ON weather_snapshots(trip_id, snapshot_date);

-- ============================================================
-- EVENT LOGS  (audit trail of agent actions & triggers)
-- ============================================================
CREATE TABLE event_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id         UUID REFERENCES trips(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    actor           VARCHAR(50) NOT NULL,     -- agent name or 'user' or 'system'
    action          VARCHAR(100) NOT NULL,    -- 'generate_itinerary'|'replan_triggered'|...
    detail          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_event_logs_trip_id ON event_logs(trip_id);
CREATE INDEX idx_event_logs_created_at ON event_logs(created_at);
```

---

## 3. Qdrant Collections (Vector / Semantic Memory)

| Collection | Vector dim | Keyed by | Stores |
|---|---|---|---|
| `user_preferences` | 384 (MiniLM) | `user_id` | Embedded preference statements, free-text travel-style notes |
| `trip_memories` | 384 | `user_id`, `trip_id` | Post-trip summaries, "what worked / what didn't" for personalization |

> Embeddings produced locally by `sentence-transformers/all-MiniLM-L6-v2` (see `memory/embeddings.py`).

---

## 4. Notes & Conventions

- **Primary keys are UUIDs** (`uuid_generate_v4()`) everywhere — avoids enumeration, simplifies merges.
- **All timestamps are `TIMESTAMPTZ`** stored in UTC. Convert at the edge (frontend/display only).
- **`source_provider` + `source_ref`** on every externally-sourced row is mandatory — it's how we prove grounding (no hallucinated venues). See `GUARDRAILS.md`.
- **`raw_payload` JSONB** on `hotel_candidates` keeps the original provider response for audit/debug.
- **Cascade deletes** flow from `users` → `trips` → children, so deleting a user fully removes their data (GDPR-aware).
- Status/enum-like fields are `VARCHAR` with `CHECK`-able values documented inline rather than native PG enums, to keep Alembic migrations simple.
