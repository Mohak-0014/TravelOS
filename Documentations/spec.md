# TravelOS — Master Specification (spec.md)

> **This is the authoritative reference for all AI agents, developers, and contributors.**
> When in doubt about stack versions, folder structure, commands, or APIs — **this file wins.**
> Pair this with `GUARDRAILS.md` (rules) and `CURRENT_STATE.md` (live status) before doing any work.

---

## 1. Project Identity

| Field | Value |
|---|---|
| Project Name | TravelOS |
| Type | AI-Native Multi-Agent Travel Operating System |
| Purpose | Placement portfolio flagship — deployable & demoable, non-commercial |
| Version | 0.1.0 (MVP, ideation → build) |
| Primary Languages | Python (backend), TypeScript (frontend) |
| LLM | Anthropic Claude |
| Deploy Target | AWS Free Tier |
| License | Proprietary |

---

## 2. Technology Stack (Exact Versions)

### Backend
| Package | Version | Purpose |
|---|---|---|
| Python | 3.11.x | Runtime |
| FastAPI | 0.111.x | REST API framework |
| Uvicorn | 0.30.x | ASGI server |
| LangGraph | 0.2.x | Stateful multi-agent graph orchestration |
| LangChain | 0.2.x | LLM toolchain, tool wrappers, RAG |
| langchain-anthropic | 0.1.x | Claude integration |
| Pydantic | 2.7.x | Data validation, schemas |
| SQLAlchemy | 2.0.x | ORM (async) |
| asyncpg | 0.29.x | Async PostgreSQL driver |
| Alembic | 1.13.x | DB migrations |
| Celery | 5.4.x | Async task queue (weather polling, replan triggers) |
| redis-py | 5.0.x | Redis client (cache + Celery broker) |
| qdrant-client | 1.9.x | Vector DB client (semantic memory) |
| sentence-transformers | 3.0.x | **Local** embeddings (all-MiniLM-L6-v2) — no paid embedding API |
| httpx | 0.27.x | Async HTTP client for external APIs |
| python-jose | 3.3.x | JWT auth |
| passlib[bcrypt] | 1.7.x | Password hashing |
| pytest / pytest-asyncio | 8.x / 0.23.x | Testing |
| ruff | 0.5.x | Lint + format |
| mypy | 1.10.x | Static type checking |

### Frontend
| Package | Version | Purpose |
|---|---|---|
| Node.js | 20.x LTS | Runtime |
| Next.js | 14.x (App Router) | React framework |
| React | 18.x | UI library |
| TypeScript | 5.x | Type safety |
| TailwindCSS | 3.x | Styling |
| shadcn/ui | latest | Component library |
| Zustand | 4.x | Client state |
| TanStack Query | 5.x | Server state / caching |
| Leaflet + react-leaflet | 1.9.x / 4.x | Map rendering (OpenStreetMap tiles, free) |

### Infrastructure
| Service | Version | Purpose | AWS Free-Tier Note |
|---|---|---|---|
| PostgreSQL | 16.x | Primary DB | **RDS free tier** (db.t3.micro, 20 GB) |
| Redis | 7.x | Cache + Celery broker | Runs in **Docker on the EC2** (ElastiCache is NOT free) |
| Qdrant | 1.9.x | Vector DB (memory) | Runs in **Docker on the EC2** |
| Docker / Compose | 26.x / 2.x | Containerization | — |
| Backend host | — | FastAPI + Celery + Redis + Qdrant | **EC2 t3.micro** (single instance, docker-compose) |
| Frontend host | — | Next.js | **AWS Amplify free tier** (or Vercel free tier) |

### LLM Models
| Model | Use Case |
|---|---|
| `claude-sonnet-4-5` (or current Sonnet) | Supervisor, Itinerary Planner, Travel Style, Concierge |
| `claude-haiku` (current) | Fast/cheap agents: Hotel ranking, Weather adaptation |

> Embeddings are **local** (`sentence-transformers`, model `all-MiniLM-L6-v2`, 384-dim). No OpenAI embedding spend.

---

## 3. External APIs (All Free Tier — No Mock Data)

| Domain | Provider | Auth | Key Limits / Notes |
|---|---|---|---|
| **Hotels (primary)** | **LiteAPI** | API key | Real-time rates; supports city/coords/Place ID + **AI natural-language search**. Free signup. *Booking requires going live — MVP does search+rank+display only.* |
| **Hotels (fallback)** | **Hotels.nl** | API key in body | One POST, auto-geocodes text locations. **5 req/min, 200 req/day per IP** → must cache via Redis. |
| **Weather** | **Open-Meteo** | **None** | Fully free, no key, no billing. Used by Weather Adaptation Agent. |
| **Geocoding** | **Nominatim (OSM)** | None | Free. Respect 1 req/sec usage policy; cache results. |
| **Map tiles** | **OpenStreetMap** | None | Free tiles via Leaflet. |
| **Attractions / POI** | **OpenTripMap** | API key | Free tier. Points of interest, attractions. |
| **Restaurants** | **Foursquare Places** | API key | Free tier. Cuisine, dietary, proximity search. |
| **Events (future)** | **Ticketmaster Discovery** | API key | Free tier. Phase 5. |

**Provider abstraction:** `tools/hotels.py` exposes a single `HotelProvider` interface. LiteAPI is primary; on error/quota, fall back to Hotels.nl. All providers normalize into the same Pydantic `HotelOffer` model before any agent or DB sees them.

---

## 4. Project Structure

```
travel-os/
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor.py          # Supervisor Agent — graph coordinator/router
│   │   ├── travel_style.py        # Travel Style Agent — preference learning
│   │   ├── itinerary_planner.py   # Itinerary Planning Agent
│   │   ├── hotel.py               # Hotel Recommendation Agent
│   │   ├── weather.py             # Weather Adaptation Agent
│   │   └── concierge.py           # Concierge Chat Agent
│   ├── graphs/
│   │   ├── __init__.py
│   │   ├── trip_graph.py          # Main LangGraph StateGraph
│   │   ├── replan_graph.py        # Event-driven replanning subgraph
│   │   └── state.py               # Global graph state schema (TypedDict)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── hotels.py              # LiteAPI (primary) + Hotels.nl (fallback), normalized
│   │   ├── weather.py             # Open-Meteo wrapper
│   │   ├── geocode.py             # Nominatim wrapper (cached)
│   │   ├── places.py              # OpenTripMap attractions
│   │   └── restaurants.py         # Foursquare Places
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── semantic.py            # Qdrant long-term semantic memory
│   │   ├── embeddings.py          # sentence-transformers local embedder
│   │   ├── sql_memory.py          # SQLAlchemy structured memory
│   │   └── session.py             # Redis temporal session memory
│   ├── workflows/
│   │   ├── __init__.py
│   │   └── celery_tasks.py        # weather polling, replan triggers
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI entrypoint
│   │   ├── dependencies.py        # DI: db session, current user, etc.
│   │   └── routers/
│   │       ├── auth.py
│   │       ├── trips.py
│   │       ├── itinerary.py
│   │       ├── hotels.py
│   │       ├── approvals.py
│   │       └── concierge.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                # SQLAlchemy declarative base + session
│   │   ├── models.py              # ORM models (see DATABASE_SCHEMA.md)
│   │   ├── schemas.py             # Pydantic request/response schemas
│   │   └── migrations/            # Alembic
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (env vars)
│   │   ├── security.py            # JWT, hashing
│   │   └── logging.py             # structured logging setup
│   └── tests/
│       ├── unit/
│       │   ├── test_agents/
│       │   ├── test_tools/
│       │   └── test_memory/
│       ├── integration/
│       │   ├── test_graph_flows.py
│       │   └── test_api_endpoints.py
│       └── conftest.py
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── onboarding/page.tsx
│   │   └── trips/
│   │       ├── page.tsx           # Trip list
│   │       ├── new/page.tsx       # Trip creation
│   │       └── [tripId]/
│   │           ├── page.tsx       # Itinerary timeline
│   │           ├── map/page.tsx
│   │           ├── approvals/page.tsx
│   │           └── chat/page.tsx
│   ├── components/
│   │   ├── ui/                    # shadcn/ui
│   │   ├── itinerary/
│   │   ├── map/
│   │   └── chat/
│   ├── lib/
│   │   ├── api.ts                 # typed API client
│   │   └── store.ts               # Zustand stores
│   └── public/
├── infra/
│   ├── docker-compose.yml         # local: postgres, redis, qdrant, backend
│   ├── docker-compose.prod.yml    # EC2: redis, qdrant, backend (postgres = RDS)
│   ├── Dockerfile.backend
│   └── nginx/nginx.conf
├── evaluations/
│   ├── eval_itinerary.py
│   ├── eval_personalization.py
│   └── eval_replanning.py
├── docs/
│   ├── PRD.md
│   ├── spec.md                    # ← THIS FILE
│   ├── DATABASE_SCHEMA.md
│   ├── API_DOCUMENTATION.md
│   ├── STYLE_GUIDE.md
│   ├── CURRENT_STATE.md
│   └── GUARDRAILS.md
├── .editorconfig
├── .env.example
├── .gitignore
├── pyproject.toml
├── package.json
└── README.md
```

---

## 5. Commands Reference

### Local Development Setup
```bash
# 1. Clone
git clone https://github.com/Mohak-0014/travel-os.git
cd travel-os

# 2. Start infra (postgres, redis, qdrant)
docker compose -f infra/docker-compose.yml up -d

# 3. Backend
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 4. Migrate DB
alembic upgrade head

# 5. Run API
uvicorn api.main:app --reload --port 8000

# 6. Celery worker (separate terminal)
celery -A workflows.celery_tasks worker --loglevel=info
celery -A workflows.celery_tasks beat --loglevel=info   # scheduler for weather polling

# 7. Frontend (separate terminal)
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

### Testing
```bash
cd backend
pytest tests/ -v                                  # all tests
pytest tests/ --cov=. --cov-report=term-missing   # with coverage
pytest tests/unit/ -v                             # unit only
pytest tests/integration/ -v                      # integration (needs infra up)
pytest tests/unit/test_agents/test_supervisor.py -v   # single file

cd frontend
npm run test
npm run type-check
```

### Database (Alembic)
```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
alembic downgrade -1
alembic history
```

### Lint & Format
```bash
# Backend
ruff check .
ruff format .
mypy .

# Frontend
npm run lint
npm run format
```

### Build & Deploy
```bash
# Build backend image
docker build -f infra/Dockerfile.backend -t travelos-backend:latest .

# Deploy on EC2 (after SSH)
docker compose -f infra/docker-compose.prod.yml up -d

# Frontend → AWS Amplify (connect repo, auto-build) or:
cd frontend && npm run build
```

### Evaluations
```bash
cd evaluations
python eval_itinerary.py
python eval_personalization.py
python eval_replanning.py
```

---

## 6. Environment Variables

See `.env.example` for the full list. Required for local dev:
```
# LLM
ANTHROPIC_API_KEY=

# Database / cache / vectors
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/travelos
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Hotel APIs
LITEAPI_KEY=
HOTELSNL_API_KEY=

# Other free APIs
OPENTRIPMAP_API_KEY=
FOURSQUARE_API_KEY=
# Open-Meteo + Nominatim + OSM tiles need NO key

# Auth
JWT_SECRET_KEY=                      # openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# App
ENVIRONMENT=development              # development | staging | production
LOG_LEVEL=INFO
```

---

## 7. Agent Architecture (MVP — 6 Agents)

| Agent | Model | Trigger | Output |
|---|---|---|---|
| **Supervisor** | Sonnet | Every graph entry | Routing decisions, state transitions, retries, approval coordination |
| **Travel Style** | Sonnet | Trip creation, preference update | Updated preference profile + embeddings |
| **Itinerary Planner** | Sonnet | Trip creation, replan | Day-by-day itinerary JSON |
| **Hotel** | Haiku | Itinerary generation | Ranked hotel list (LiteAPI/Hotels.nl, normalized) |
| **Weather Adaptation** | Haiku | Celery schedule (every 6h) | Replan proposal for approval gate |
| **Concierge Chat** | Sonnet | User chat message | Natural-language response grounded in trip state |

**Future agents (documented, not built):** Restaurant, Budget Optimization, Local Events, Transport, Visa, Group Coordination.

---

## 8. Graph Workflow

```
User Input
  → Supervisor (route)
  → Travel Style (load/update prefs)
  → Itinerary Planner (generate)
  → [Hotel] (enrich with real lodging)
  → Validation (grounding, coherence checks)
  → Conflict Detection
  → Replanning Loop (if triggered)
  → Human Review (approval gate, if consequential)
  → Checkpoint Save (LangGraph checkpointer → Postgres)
  → Response
```

---

## 9. Graph State Schema (Source of Truth)

Defined in `backend/graphs/state.py`. Passed between all agents:
```python
from typing import TypedDict, Optional
from langchain_core.messages import BaseMessage

class TravelOSState(TypedDict):
    trip_id: str
    user_id: str
    traveler_profiles: list["TravelerProfile"]
    itinerary: "Itinerary"                  # current itinerary object
    weather_state: "WeatherState"           # latest weather per destination
    budget_state: "BudgetState"             # planned vs actual (basic in MVP)
    hotel_state: "HotelState"               # selected + candidate hotels
    memory_context: "MemoryContext"         # retrieved long-term memory
    approval_queue: list["ApprovalRequest"] # pending human approvals
    agent_messages: list[BaseMessage]       # LangGraph message history
    current_step: str                       # current graph node
    error_state: Optional["ErrorState"]     # last error, if any
    checkpoint_id: Optional[str]            # last saved checkpoint
```

---

*Last updated: June 2025. Maintain this file whenever stack versions, structure, APIs, or agent roster change.*
