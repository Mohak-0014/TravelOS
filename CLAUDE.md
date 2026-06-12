# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TravelOS is an AI-native multi-agent travel operating system built on LangGraph + FastAPI (Python 3.11) + Next.js 14 (TypeScript 5). The full spec lives in `Documentations/spec.md`; guardrails and SOPs in `Documentations/GUARDRAILS.md`. Read those before making architectural decisions.

## Commands

### Backend (run from repo root or `backend/`)

```bash
# Setup (one-time)
cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"

# Dev server
uvicorn api.main:app --reload --port 8000

# Celery (separate terminals) — must run from repo root, not backend/
# Windows requires --pool=solo; all tasks now use the default queue (no -Q flag needed)
backend/.venv/Scripts/celery -A backend.workflows.celery_tasks worker --loglevel=info --pool=solo
backend/.venv/Scripts/celery -A backend.workflows.celery_tasks beat --loglevel=info   # weather polling scheduler

# Lint + format (ruff handles BOTH — no separate black/flake8)
ruff format .
ruff check .
mypy .

# Tests
pytest tests/ -v
pytest tests/ --cov=. --cov-report=term-missing
pytest tests/unit/ -v                                   # unit only (no infra needed)
pytest tests/integration/ -v                            # needs docker-compose infra up

# Database migrations
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
alembic downgrade -1
```

### Frontend (from `frontend/`)

```bash
npm run dev         # http://localhost:3000
npm run build
npm run lint        # ESLint
npm run format      # Prettier
npm run type-check  # tsc --noEmit
npm test
```

### Infrastructure

```bash
# Local dev — start ONLY the three infra services, never the backend/celery services
docker compose -f infra/docker-compose.yml up -d postgres redis qdrant

# Full prod stack (EC2 only)
docker compose -f infra/docker-compose.prod.yml up -d
```

### Local dev server (from repo root, not backend/)

```bash
backend/.venv/Scripts/uvicorn backend.api.main:app --reload --port 8000
```

## Windows Dev Gotchas

**PostgreSQL port conflict:** A native Windows PostgreSQL 18 service (`postgresql-x64-18`) owns port 5432. Docker postgres is mapped to **port 5433** (`infra/docker-compose.yml` `ports: "5433:5432"`) and `DATABASE_URL` in `.env` uses `localhost:5433`. Do not change these back to 5432.

**Docker backend container:** `infra-backend-1` maps to port 8000 and will shadow the local uvicorn process. For local dev, never start the `backend` / `celery_worker` / `celery_beat` Docker services — always run `uvicorn` directly. Only start `postgres redis qdrant` via Docker.

**pg_hba.conf trust auth:** `POSTGRES_HOST_AUTH_METHOD: trust` is set in `docker-compose.yml` because Docker Desktop on Windows (WSL2) routes port-forwarded connections through the bridge network IP, not `127.0.0.1`, so the standard loopback trust rules never match.

**Run alembic from repo root:** Use `backend/.venv/Scripts/alembic` (not the venv-activated `alembic`) so the `backend` package resolves correctly on the Python path.

## Code Style

### Python
- **Line length:** 100 chars (configured in pyproject.toml — not the ruff default of 88)
- **Type hints:** mandatory on all function signatures
- **Pydantic models** for all API bodies and external API responses — never pass raw dicts past a tool boundary
- **Async I/O:** all DB, HTTP, Redis calls must be async
- **Logging:** use `core/logging.py` structured logger; never `print()`
- **Exceptions:** raise from `core/exceptions.py`; map to FastAPI error envelope in routers

### TypeScript/React
- **Indentation:** 2 spaces
- **Server Components:** default in App Router — add `"use client"` only when strictly needed
- **API calls:** always through `lib/api.ts` typed client; no inline `fetch`
- **Server state:** TanStack Query; **client/UI state:** Zustand — never store server data in localStorage
- **Components:** one per file; props explicitly typed; no implicit `any`

### Database
- Table names: plural `snake_case`; PKs: `id UUID`; timestamps: `TIMESTAMPTZ` UTC, named `*_at`
- **Every schema change goes through Alembic** — never hand-edit a shared database
- After `alembic revision --autogenerate`, **always review the generated file by hand** before applying (autogenerate misses enums and backfills)

## Environment Setup

Copy `.env.example` → `.env` and fill in all keys before running anything. Required:

- `ANTHROPIC_API_KEY` — Sonnet for heavy agents (Supervisor, Itinerary Planner, Concierge, Travel Style), Haiku for fast ones (Hotel, Weather)
- `DATABASE_URL`, `REDIS_URL`, `QDRANT_HOST`/`QDRANT_PORT`
- `LITEAPI_KEY`, `HOTELSNL_API_KEY`, `OPENTRIPMAP_API_KEY`, `FOURSQUARE_API_KEY`
- `JWT_SECRET_KEY` — generate with `openssl rand -hex 32`

Open-Meteo, Nominatim, and OSM tiles require **no API key**.

All config is read through Pydantic Settings in `backend/core/config.py` — never hardcode keys or connection strings.

## Architecture

### Multi-Agent Graph
`backend/graphs/state.py` defines `TravelOSState` (TypedDict) — the single source of truth passed between all agents. Always propagate state through the graph; never use module-level globals.

### Hotel Provider Abstraction
`backend/tools/hotels.py` exposes a single `HotelProvider` interface. LiteAPI is primary; Hotels.nl is the fallback (rate limit: 5 req/min, 200 req/day — must cache via Redis). Both normalize to the same `HotelOffer` Pydantic model.

### Celery for Heavy Work
Local embedding generation (sentence-transformers, all-MiniLM-L6-v2, 384-dim) must run as Celery tasks — **never in the request/response path**.

### Approval Gate Pattern
Consequential itinerary changes (rerouting cities, hotel changes, weather replanning, >15% budget deviation) must follow this pattern:
1. Create an `ApprovalRequest` record with status `pending` and a structured diff payload
2. **Do not mutate the itinerary yet**
3. On user `approved`: apply diff, save LangGraph checkpoint, log
4. On `rejected`: mark resolved, change nothing

## Hard Guardrails

**Grounding (non-negotiable):** Hotels, restaurants, attractions, prices, and coordinates must come from real API responses. If an API is unavailable, surface a degraded state message — never fabricate data.

**Secrets:** Never commit `.env`, API keys, or JWT secrets. Never log full secrets (redact to last 4 chars if needed). Read config exclusively from `core/config.py`.

**Database:** Never run `DROP`, `TRUNCATE`, or mass `DELETE`/`UPDATE` without `WHERE` on a shared environment. Always use Alembic for schema changes.

**Booking:** MVP scope is search/read endpoints only — never call paid or booking endpoints of any provider.

## Commit Conventions

Conventional Commits format, imperative mood, < 72 chars:

```
feat(hotel-agent): add LiteAPI provider with Hotels.nl fallback
fix(itinerary): correct day-indexing off-by-one
test(weather): cover adverse-condition replan trigger
chore(deps): bump langgraph to 0.2.x
```

Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`

Branch naming: `feature/<name>`, `fix/<name>`, `docs/<name>`

## Pre-Commit Checklist (SOP-6)

Before committing, all of these must pass:

1. `ruff format . && ruff check . && mypy .` (backend)
2. `npm run lint && npm run type-check` (frontend, if changed)
3. `pytest` — all pass, coverage not regressed
4. Confirm no secrets staged (`git diff --staged` — `.env` must not be tracked)

Run `/pre-commit` to execute all checks in one step.
