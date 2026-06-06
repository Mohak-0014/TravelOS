# TravelOS — Style Guide

> Coding standards for humans and AI agents. Consistency > preference. When generating or editing
> code, follow these rules exactly. Pair with `.editorconfig` (auto-enforced) and `spec.md`.

---

## 1. General Principles

- **Clarity over cleverness.** Readable code beats terse code.
- **Type everything.** Type hints (Python) and strict types (TypeScript) are mandatory.
- **Small functions.** One responsibility each; prefer < 40 lines.
- **No dead code.** Delete it; git remembers.
- **Fail loudly in dev, gracefully in prod.** Validate inputs at boundaries.
- **Ground all external data.** Every venue/hotel must carry `source_provider` + `source_ref`.

---

## 2. Python (Backend)

### Formatting & Linting
- **Formatter & linter:** `ruff` (handles both). Run `ruff format .` and `ruff check .` before commit.
- **Type checker:** `mypy .` must pass with no errors.
- **Line length:** 100 characters.
- **Indentation:** 4 spaces, never tabs.

### Naming
- `snake_case` for variables, functions, modules, and files.
- `PascalCase` for classes and Pydantic models.
- `UPPER_SNAKE_CASE` for module-level constants.
- Private helpers prefixed with a single underscore: `_normalize_offer`.
- Agent files named after the agent: `hotel.py`, `weather.py`.

### Type Hints (mandatory)
```python
# Good
async def rank_hotels(offers: list[HotelOffer], prefs: Preferences) -> list[RankedHotel]:
    ...

# Bad — no hints
def rank_hotels(offers, prefs):
    ...
```

### Pydantic
- All API request/response bodies are Pydantic models (in `db/schemas.py`).
- All normalized external data (hotels, weather, places) are Pydantic models — never raw dicts past the `tools/` boundary.
- Use `model_config = ConfigDict(from_attributes=True)` for ORM-backed response models.

### Async
- All I/O is async: DB (`asyncpg`/SQLAlchemy async), HTTP (`httpx.AsyncClient`), Redis.
- Never call blocking I/O inside an async route. CPU-bound work (e.g. local embeddings) goes through a thread executor or a Celery task.

### Imports (ordered, ruff-enforced)
1. Standard library
2. Third-party
3. First-party (`from agents...`, `from tools...`)

### Docstrings
- Public functions/classes get a one-line summary; add detail only when non-obvious.
- Use Google-style docstrings when arguments need explanation.

### Errors
- Raise typed exceptions (`TripNotFoundError`, `ProviderRateLimitedError`) from a central `core/exceptions.py`.
- Map them to the standard API error envelope in one FastAPI exception handler.

### Logging
- Use the structured logger from `core/logging.py`. **Never** `print()` in backend code.
- Log agent actions to `event_logs` (DB) for the audit trail, and to stdout (structured) for ops.

---

## 3. TypeScript / React (Frontend)

### Formatting & Linting
- **Formatter:** Prettier. **Linter:** ESLint (Next.js config). Run `npm run format` and `npm run lint`.
- **`npm run type-check` must pass** — no `any` without an inline justification comment.
- **Indentation:** 2 spaces.

### Naming
- `camelCase` for variables and functions.
- `PascalCase` for components, types, and interfaces.
- Component files: `PascalCase.tsx` (e.g. `ItineraryTimeline.tsx`).
- Hooks: `useSomething.ts`.

### Components
- Function components only. No class components.
- One component per file (small presentational helpers may co-locate).
- Props typed with an explicit `interface` or `type`; no implicit `any`.
- Server Components by default (App Router); add `"use client"` only when needed (state, effects, browser APIs).

### State & Data
- Server state via **TanStack Query**; client/UI state via **Zustand**.
- Never store server data in `localStorage`/`sessionStorage`.
- All API calls go through the typed client in `lib/api.ts` — no inline `fetch` scattered in components.

### Styling
- **TailwindCSS** utility classes. Avoid inline `style={{}}` except for dynamic values (e.g. map marker positions).
- Use `shadcn/ui` components as the base; don't hand-roll what shadcn provides.

---

## 4. API Conventions

- REST, versioned under `/api/v1`.
- Resource paths are plural nouns: `/trips`, `/approvals`.
- Use proper verbs: `GET` (read), `POST` (create/action), `PUT` (replace), `PATCH` (partial), `DELETE`.
- Async/long-running actions return `202 Accepted` with a resource to poll (e.g. approvals).
- Consistent error envelope (see `API_DOCUMENTATION.md`).

---

## 5. Database Conventions

- Table names: plural `snake_case` (`hotel_candidates`).
- Column names: `snake_case`.
- Primary keys: `id UUID`.
- Timestamps: `TIMESTAMPTZ`, UTC, named `created_at` / `updated_at` / `*_at`.
- Every migration via Alembic with a descriptive message. Never edit the DB by hand in any shared environment.

---

## 6. Git Conventions

### Branches
- `main` — always deployable.
- `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.

### Commits (Conventional Commits)
```
feat(hotel-agent): add LiteAPI provider with Hotels.nl fallback
fix(itinerary): correct day indexing off-by-one
docs(spec): lock hotel provider decision
test(weather): cover adverse-condition replan trigger
chore(deps): bump langgraph to 0.2.x
```
- Imperative mood, lowercase scope, < 72-char subject.
- One logical change per commit.

### PRs
- Must pass: `ruff`, `mypy`, `pytest`, frontend `lint` + `type-check`.
- Include a one-line "why" and any schema/API doc updates in the same PR.

---

## 7. Testing

- **Framework:** `pytest` + `pytest-asyncio` (backend).
- **Coverage target:** > 80% (MVP), > 90% (v1) on agent/tool logic.
- Unit tests mock external APIs; integration tests hit real infra (Postgres/Redis/Qdrant) via docker-compose.
- Name tests `test_<unit>_<scenario>_<expected>`: `test_rank_hotels_over_budget_filtered_out`.
- Every bug fix adds a regression test.

---

## 8. Comments

- Explain **why**, not **what** (the code shows what).
- Mark intentional shortcuts with `# TODO(mohak): ...` or `# NOTE: ...`.
- Remove commented-out code before merging.
