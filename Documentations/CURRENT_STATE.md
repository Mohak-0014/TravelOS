# TravelOS — Current State Snapshot

> **Updated:** June 2025 · **Phase:** Ideation → Phase 1 (not yet started)
> Keep this file current. It is the first thing any agent or contributor should read to know
> where the project actually stands versus what's merely planned.

---

## 1. One-Line Status

The project is at the **ideation/specification stage**. The full SRS blueprint and the core document set (PRD, spec, schema, API, style guide, guardrails) are complete. **No code has been written yet.** Next step is scaffolding the repository and Phase 1.

---

## 2. What Works ✅

- **Documentation set complete:** `PRD.md`, `spec.md`, `DATABASE_SCHEMA.md`, `API_DOCUMENTATION.md`, `STYLE_GUIDE.md`, `.editorconfig`, `GUARDRAILS.md`, and this snapshot.
- **All major technical decisions locked:**
  - LLM: Claude (Sonnet for heavy agents, Haiku for fast ones).
  - Embeddings: local `sentence-transformers` (no paid embedding API).
  - Hotels: **LiteAPI primary**, **Hotels.nl fallback** (both free-tier, real live data).
  - Weather: Open-Meteo (no key). Geocoding: Nominatim. Tiles: OSM/Leaflet. Attractions: OpenTripMap. Restaurants: Foursquare.
  - Deploy: AWS free tier (EC2 t3.micro for backend+Redis+Qdrant in Docker; RDS free-tier Postgres; Amplify/Vercel for frontend).
- **MVP scope fixed at 6 agents:** Supervisor, Travel Style, Itinerary Planner, Hotel, Weather Adaptation, Concierge.

---

## 3. What's Broken / Not Yet Built ❌

Everything implementation-related. Specifically, none of these exist yet:
- Repository scaffold (`backend/`, `frontend/`, `infra/`).
- Database (no migrations, no tables created).
- Any agent, tool wrapper, graph, or API route.
- Frontend (no Next.js app).
- Tests (target > 80% coverage — currently 0%).
- Deployment (no AWS resources provisioned).

---

## 4. Known Risks & Open Items

| Item | Status | Note |
|---|---|---|
| LiteAPI booking | ⚠️ Boundary | Free tier returns **real rates**; actual *booking* needs going live. MVP does search+rank+display only; "book" redirects to provider. Document this in the demo. |
| Hotels.nl rate limit | ⚠️ Constraint | 5 req/min, 200/day per IP. **Must cache via Redis.** Used only as fallback. |
| Nominatim usage policy | ⚠️ Constraint | Max ~1 req/sec; cache geocoding results aggressively. |
| AWS free-tier limits | ⚠️ Watch | t3.micro is small for Postgres+Redis+Qdrant+backend together — Postgres offloaded to RDS to ease memory; monitor Qdrant memory footprint. |
| Local embeddings on t3.micro | ⚠️ Watch | `all-MiniLM-L6-v2` is light but CPU-only; embedding generation should run via Celery, not in the request path. |
| Free API quota under demo load | ⏳ Untested | Verify quotas hold during live demos; pre-warm Redis cache before interviews. |

---

## 5. Immediate Next Steps (in order)

1. **Scaffold the repo** per the structure in `spec.md` (backend, frontend, infra, docs, evaluations).
2. **Initialize backend:** `pyproject.toml`, `core/config.py` (Pydantic Settings), `core/logging.py`, FastAPI `main.py` health check.
3. **Stand up infra locally:** `infra/docker-compose.yml` for Postgres + Redis + Qdrant; confirm all three start.
4. **Implement DB layer:** SQLAlchemy models from `DATABASE_SCHEMA.md`, first Alembic migration, `alembic upgrade head`.
5. **Build auth (FR-1):** register/login, JWT, `get_current_user` dependency.
6. **Build trip CRUD (FR-2):** with Nominatim geocoding in `tools/geocode.py`.
7. **First tool + test:** `tools/weather.py` (Open-Meteo, no key) as the simplest real-API integration; write its unit + integration tests to establish the testing pattern.

> After step 7, begin Phase 2 (LangGraph Supervisor + first agents). Do **not** start multiple agents in parallel before the graph skeleton and one end-to-end vertical slice work.

---

## 6. Environment Setup Checklist (before coding)

- [ ] Python 3.11 installed, venv created.
- [ ] Node 20 LTS installed.
- [ ] Docker + Compose working.
- [ ] API keys obtained: Anthropic, LiteAPI, Hotels.nl, OpenTripMap, Foursquare. (Open-Meteo/Nominatim/OSM need none.)
- [ ] `.env` created from `.env.example` and filled (never commit it — see `GUARDRAILS.md`).
- [ ] `JWT_SECRET_KEY` generated via `openssl rand -hex 32`.
