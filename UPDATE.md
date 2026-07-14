# TravelOS — Session Update (2026-06-27)

## Headline

- **Landing/UI redesign → "Daylight Voyage"**: the whole app moved from the dark indigo "Twilight" theme to a **bright, light, airy theme** (soft cloud-white surfaces, sky-blue + amber + coral accents). Token-driven, so every page re-themed at once.
- **Moved away from the 7-Wonders focus** → **popular travel cities** (Tokyo, Paris, New York, Bali, Cape Town, Lisbon, Reykjavík, Marrakech) across the hero scroll and the 3D globe; day blue-marble earth instead of night earth.
- **Security hardening pass for deployment** — 7 findings fixed (JWT fail-closed, PyJWT, input validation, login-timing, auth rate limiting, CORS/docs, ICS/header injection) + optional Qdrant auth. Backend gate green (593 tests).
- ⚠️ Two separate bodies of work are committed this session: `feat(ui)` redesign and `fix(security)` hardening.

---

## What was done this session

### 1. Daylight Voyage UI redesign ✅

Re-skinned the app from dark → light without changing component structure or animations:

- **`frontend/tailwind.config.ts`** — flipped the token system: `space-*` surfaces → near-white ramp (950 = white/elevated), `slate-*` text ramp → dark, `ink-*` hairlines → dark low-alpha, `electric-*` accent → **sky-blue**, softened shadows, daytime sky gradients. This single change re-themes every page.
- **`frontend/app/globals.css`** — light glass cards (white translucent + dark hairlines), light scrollbar/inputs/buttons, new brand gradient (sky → indigo → coral), dark-on-light dashed flight paths.
- **Hero swap**: `NightSky.tsx` → new **`DaySky.tsx`** (clear blue sky, warm sun, white clouds, drifting birds, light haze ridge). Login + onboarding backgrounds repointed to it.
- **Destinations**: `WondersScroll.tsx` → **`DestinationsScroll.tsx`** — city posters (brighter daytime gradients) instead of the 7 Wonders.
- **`frontend/components/travel/WorldGlobe.tsx`** — same 8 cities as arcs/labels; `earth-night.jpg` → `earth-blue-marble.jpg`; sky-blue atmosphere.
- Deleted `NightSky.tsx`, `WondersScroll.tsx` (and the older `SkyScene.tsx`).
- **Gate**: `tsc --noEmit` clean, ESLint clean, `/` + `/login` compile and render 200; rendered HTML confirms cities (no Wonders).

### 2. Security hardening for deployment ✅

Full source audit (injection / XSS / IDOR / RLS / secrets / SSRF / CORS / CSRF). Posture was already solid — **no SQLi, no XSS sinks, no SSRF, consistent ownership checks, tenant-isolated vector search**. Fixed the operational gaps:

| Fix | Files |
|---|---|
| JWT secret **fails closed** in production (rejects default / <32 chars) | `backend/core/config.py` |
| Migrated **python-jose → PyJWT 2.9** (drops CVE-2024-33663/33664; same pinned-alg behavior) | `backend/core/security.py`, `pyproject.toml` |
| Input validation: `EmailStr`, password 8–128, `num_travelers` 1–20, `budget_total ≥0`, currency len 3, chat ≤2000, string max-lengths | `backend/db/schemas.py` |
| Typed `PUT /me` (`UserUpdate`) + constant-time bcrypt verify on unknown email (kills login timing oracle) | `backend/api/routers/auth.py` |
| **Auth rate limiting** — slowapi (Redis-backed, fail-open): register 5/min, login 10/min per IP | `backend/api/rate_limit.py` (new), `backend/api/main.py`, `backend/api/routers/auth.py` |
| CORS `allow_credentials=False`; `/docs` `/redoc` `/openapi.json` disabled when `ENVIRONMENT=production` | `backend/api/main.py` |
| ICS / `Content-Disposition` injection — RFC-5545 escape of `LOCATION`/`CALNAME`, sanitized download filename | `backend/api/routers/trips.py` |
| Optional `QDRANT_API_KEY` wired into the client | `backend/core/config.py`, `backend/memory/semantic.py` |

- **`.env.example`** documents the new prod knobs (`QDRANT_API_KEY`, `RATE_LIMIT_ENABLED`, JWT-required note, CORS warning).
- **Gate**: ruff format+check clean · mypy no new errors · pytest **593 passed** (2 short-password test fixtures updated to ≥8 chars; `test_auth.py` 19/19 green).
- New deps installed + pinned: `pyjwt==2.9.*`, `slowapi==0.1.*`.

### 3. Carried fix — Groq tool-use model (TASKS #30) ✅

`backend/agents/_llm.py`: `_TOOL_USE_MODEL` pointed at the **decommissioned** `llama3-groq-70b-8192-tool-use-preview` → repointed to the supported `llama-3.3-70b-versatile`.

---

## Before deploying — set in the production `.env`

1. **`JWT_SECRET_KEY`** — strong 32+ chars (`python -c "import secrets; print(secrets.token_hex(32))"`). App refuses to boot without it.
2. **`ENVIRONMENT=production`** — activates the fail-closed check + hides API docs.
3. **`CORS_ORIGINS`** — your real frontend origin(s), never `*`.
4. **`QDRANT_API_KEY`** — if Qdrant is reachable off-localhost; keep Postgres/Redis/Qdrant off the public internet regardless.
5. **`RATE_LIMIT_ENABLED=true`** with `REDIS_URL` reachable.

---

## How to start the app (Windows)

```powershell
# 1. Infra only (never start the docker backend/celery services locally)
docker compose -f infra/docker-compose.yml up -d postgres redis qdrant

# 2. Backend — use the VENV python explicitly
backend\.venv\Scripts\python -m uvicorn backend.api.main:app --reload --port 8000

# 3. Celery worker (separate terminal, from repo root) — RESTART after any backend code change
backend\.venv\Scripts\celery -A backend.workflows.celery_tasks worker --loglevel=info --pool=solo

# 4. Frontend — must be on port 3000 (CORS), use `npm run dev -- -p 3000`
cd frontend; npm run dev -- -p 3000   # http://localhost:3000
```

---

## Pending / next session

| Priority | Item |
|----------|------|
| 1 | Visual QA of the daylight theme on the denser interior pages (trip detail `trips/[tripId]/page.tsx`, ~2k lines) — token flip themes them, but a hand-tuning pass may be wanted. |
| 2 | Carry-over backend tasks: Qdrant collections init (#2 — now in `main.py` startup), weather taste-aware replans (#7/#26), under-count day validation (#8), agent prompt quality (#24–29), real-time status polling (#21 — already in trip page). |
| 3 | Optional security defense-in-depth: Postgres RLS policies; shorter access-token TTL + refresh/revocation; `pip-audit` in CI; migrate off EOL `passlib`. |

---

## Known issues / gotchas

- **Frontend must run on port 3000** — Next falls back to 3001 if 3000 is taken, which breaks CORS. Use `npm run dev -- -p 3000` so it fails loudly instead of drifting.
- **OneDrive locks `frontend/.next`** → stale Tailwind CSS in dev / EPERM on build. Clear `.next` and restart dev after big token changes.
- **Restart the Celery worker after any backend code change** — it caches imported code at startup.
- **Groq is the permanent LLM** (llama-3.3-70b "large", llama-3.1-8b "small"/"tools"). Do not switch to Claude/Anthropic.
- **react-leaflet v4** — do not upgrade to v5 (needs React 19; project is React 18).
- **passlib 1.7 is EOL** but functional (correctly pinned `bcrypt<4.1`); no drop-in replacement yet.
