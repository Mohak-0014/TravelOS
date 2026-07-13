# TravelOS — Pre-Deployment Checklist

Project-specific go-live checklist. Work top to bottom; **🔴 = hard blocker**, **🟡 = should-fix**,
**🟢 = plan for / monitor**. Tailored to this stack: FastAPI + LangGraph + Celery + Postgres +
Redis + Qdrant backend, Next.js frontend.

---

## 1. Secrets & configuration 🔴

- [x] `.env` populated for prod from `.env.example`; **never committed** (confirmed git-ignored).
- [ ] Prefer a secrets manager (AWS SSM / Secrets Manager) over a plaintext `.env` on the host.
- [x] `JWT_SECRET_KEY` is a strong value (`openssl rand -hex 32`). The prod validator in
      `core/config.py` **refuses to boot** with a weak/default secret when `ENVIRONMENT=production`.
- [ ] **`ENVIRONMENT=production`** set in prod `.env` — gates docs-disable, JWT enforcement, Sentry.
- [ ] **`CORS_ORIGINS`** set to the real frontend origin(s), e.g. `["https://yourdomain.com"]` —
      **never `*`**, never the localhost default.
- [x] `RATE_LIMIT_ENABLED=true` and `RESILIENCE_ENABLED=true` — both in config + `.env.example`.
- [ ] All provider keys present and on **production** tiers: `GROQ_API_KEY`, `LITEAPI_KEY`,
      `HOTELSNL_API_KEY`, `DUFFEL_API_KEY`, `UNSPLASH_ACCESS_KEY`, `FOURSQUARE_API_KEY`,
      `TICKETMASTER_API_KEY` / `EVENTBRITE_TOKEN`.
- [x] `QDRANT_API_KEY` supported in config; set it and match `QDRANT__SERVICE__API_KEY` in
      `docker-compose.prod.yml`.
- [ ] `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `QDRANT_HOST/PORT`
      point at prod infra (not localhost / dev ports like `5433`).
- [ ] `POSTGRES_PASSWORD` and `REDIS_PASSWORD` set — required by `docker-compose.prod.yml`.

## 2. Database & migrations 🔴

- [ ] **Run `alembic upgrade head` on deploy** — the `migrate` init service in
      `docker-compose.prod.yml` does this automatically before the API starts. Verify it passes.
- [x] Migration chain is single-head: `c7d8e9f0a1b2_add_outbox_events_table` off `f3f5215ec0b8`.
      Run `alembic heads` locally to confirm one head.
- [ ] Use managed Postgres (RDS / Cloud SQL / Supabase) with automated backups + PITR. **Do not**
      ship the dev compose Postgres (`POSTGRES_HOST_AUTH_METHOD: trust`, password `postgres`) to prod.
- [ ] Strong DB credentials + `scram-sha-256` auth; DB not publicly reachable (VPC/private subnet).
- [x] Connection pool sized for load (`pool_size=10, max_overflow=20` in `db/base.py`).

## 3. Infrastructure & orchestration 🔴

- [x] **`infra/docker-compose.prod.yml` created.** Differs from dev:
  - [x] No `--reload`; no `../backend` bind-mount (code baked into image via `target: prod`).
  - [x] `gunicorn + UvicornWorker` with 2 workers sized to CPU.
  - [x] `Dockerfile.backend` `prod` stage installs `.` only (no pytest/ruff/mypy bloat).
- [x] Image tags pinned (`postgres:16-alpine`, `redis:7-alpine`, `qdrant/qdrant:v1.9.0`).
- [x] Restart policies (`restart: unless-stopped`) on api / worker / beat.
- [x] Resource limits per service — Celery worker budgeted 1.5 GB for the embedding model.

## 4. Networking, TLS & proxy 🔴

- [ ] Reverse proxy / load balancer (nginx / ALB / Caddy) terminating **TLS** in front of port 8000.
- [ ] **Rate limiting behind a proxy:** slowapi keys on `get_remote_address` (socket peer IP). Behind
      an LB that IP is the proxy — all users share one bucket. Run uvicorn with
      `--proxy-headers --forwarded-allow-ips="<lb-cidr>"` and ensure the LB sets `X-Forwarded-For`.
      **Verify** the limiter sees real client IPs after deploy (smoke test item 9).
- [ ] Security headers at the proxy: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
      `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
- [ ] Only the proxy is public; Postgres / Redis / Qdrant on a private network (no public IPs).

## 5. Security hardening 🟡

- [x] Prod hardening in code: API docs disabled in prod, `allow_credentials=False` in CORS, PyJWT
      replaces python-jose, auth rate limiting (slowapi), input validation on all schemas.
- [ ] **Set `REDIS_PASSWORD`** — `docker-compose.prod.yml` passes it via `--requirepass`; rate
      limiter and Celery broker both need it. Without it Redis is unauthenticated.
- [x] Qdrant requires the API key (`QDRANT__SERVICE__API_KEY`) and is not public.
- [x] Booking guardrail holds: search/read endpoints only — no paid provider calls.
- [ ] Logs never emit full secrets — redact to last 4 chars. Run a sample trip generation and grep
      logs for API key patterns.
- [ ] Dependency scan: `pip-audit` on backend, `npm audit` on frontend. Fix any critical findings.

## 6. Background workers — Celery 🟡

- [x] Both `celery_worker` and `celery_beat` services in `docker-compose.prod.yml`.
- [x] Beat schedule: `drain-outbox-every-10s` + `check-weather-every-6h`. Without beat,
      **feedback embeddings never dispatch**.
- [x] Linux prefork pool; `--concurrency=2` in prod compose (Windows dev uses `--pool=solo`).
- [x] Redis AOF persistence enabled (`--appendonly yes --appendfsync everysec` in prod compose).
- [x] Outbox drain marks rows `failed` after 5 attempts — monitor for stuck/failed rows.
- [x] `task_time_limit=600` / `soft_time_limit=540` set.

## 7. External APIs & grounding 🟢

- [ ] **Nominatim** public endpoint will throttle at production geocoding volume. Plan a paid
      geocoder (Google Maps, Mapbox) or self-hosted Nominatim before launch. Resilience layer
      degrades to empty coords — trips still create, but without lat/lng.
- [ ] Unsplash: demo tier = 50 req/hr — cover photos silently omitted past quota. Upgrade to
      production access at unsplash.com/oauth/applications.
- [ ] Duffel / LiteAPI / Hotels.nl: verify live (not sandbox) keys are active.
- [ ] Confirm `RESILIENCE_ENABLED=true` so retry + circuit breaker wrap every provider call.
- [ ] Redis cache reachable — geocode/Unsplash/hotels/flights degrade to uncached direct calls
      if Redis is down, but quota exhaustion is faster without caching.

## 8. Observability & monitoring 🟡

- [x] Sentry wired — `sentry_sdk.init()` called in `main.py` when `SENTRY_DSN` is set.
- [ ] **Set `SENTRY_DSN`** in prod `.env` — no error tracking until this is populated.
- [ ] Ship structured logs (`core/logging.py` emits JSON in non-dev) to CloudWatch / Loki /
      Datadog. Set `LOG_LEVEL=INFO` in prod.
- [x] `/health` covers DB + Redis + Qdrant. Container `healthcheck` on api service in prod compose.
- [ ] Dashboards/alerts: API 5xx rate, p95 latency (`X-Process-Time` header), Celery queue depth,
      Redis memory, provider circuit-open events, `outbox_events` stuck rows.

## 9. Performance & scaling 🟢

- [ ] **Embedding model cold-start:** `all-MiniLM-L6-v2` (~80 MB) downloads on the worker's first
      task. Bake it into the image (`RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"` in the prod Dockerfile stage) or mount a pre-populated volume. Budget ≥ 500 MB RAM — already allocated 1.5 GB.
- [ ] LangGraph uses in-memory `MemorySaver` (per-process, ephemeral). Fine for current design
      (approvals via DB), but cross-process resume needs a persistent checkpointer if you scale
      to multiple workers.
- [ ] Load-test: `POST /trips/{id}/itinerary/generate` (full multi-agent graph) and concierge chat.
      Confirm 2 Celery workers + 2 gunicorn workers hold under concurrent load.
- [ ] (Optional) Idempotency key on `POST /trips` and `/generate` to prevent double-submit.

## 10. CI/CD & quality gates 🟡

- [x] Geocode mocked in tests — `conftest.py` `autouse` fixture patches `backend.tools.geocode.geocode`.
      Suite is now fast and deterministic (no more 18-min Nominatim calls).
- [ ] Relax/address the **~81 pre-existing mypy errors** so a `mypy .` gate can be green in CI.
- [ ] CI pipeline (GitHub Actions / GitLab CI) running on Linux:
      - Backend: `ruff format --check`, `ruff check`, `mypy`, `pytest`
      - Frontend: `npm run lint`, `npm run type-check`, `npm run build`
- [ ] Migration check in CI: spin up a throwaway Postgres, run `alembic upgrade head`, assert
      `alembic check` finds no pending autogenerate diff.

## 11. Frontend 🟡

- [ ] `npm run build` + `type-check` pass on Linux (OneDrive `.next` lock is local-dev-only — clear
      `.next` before CI build).
- [ ] `NEXT_PUBLIC_API_URL` set to the prod backend URL in the build environment. The code already
      reads it from env (`lib/api.ts` line 1) — just needs the value at build time.
- [x] `react-globe.gl` in `package.json` and installed.
- [ ] Serve via Next.js production server or deploy to Vercel / CloudFront. Set caching headers on
      static assets (`/_next/static/` → immutable, long TTL).
- [x] No secrets in `NEXT_PUBLIC_*` vars — only `NEXT_PUBLIC_API_URL` exists, which is not a secret.

## 12. Data, backups & DR 🟢

- [ ] Postgres: automated daily snapshots + tested point-in-time restore. RDS does this by default.
- [x] Qdrant storage volume persisted (`qdrant_storage`) in prod compose.
- [x] Redis AOF durability enabled in prod compose (`--appendonly yes`). Losing Redis only loses
      in-flight Celery tasks not yet in the outbox — outbox-staged ones are safe in Postgres.
- [x] Rollback path: re-deploy previous image tag + `alembic downgrade -1`. Outbox migration
      `c7d8e9f0a1b2` has a working `downgrade()`.

## 13. Go-live smoke tests

Run these against the **deployed environment** immediately after migrations complete:

1. [ ] `GET /health` → `{"status":"ok","db":"connected","redis":"connected","qdrant":"connected"}`.
2. [ ] Register → login → `GET /me` — confirms auth + JWT round-trip.
3. [ ] Create a trip — exercises geocode (Nominatim), Unsplash cover photo, Redis cache.
4. [ ] `POST /trips/{id}/itinerary/generate` → reaches `planned` or `awaiting_approval` —
       confirms full multi-agent graph + Celery worker running.
5. [ ] Concierge chat returns a grounded answer — confirms LLM + Qdrant path.
6. [ ] `GET /trips/{id}/hotels`, `/flights`, `/weather` return real data — confirms provider keys.
7. [ ] Create share link → open `/share/{token}` unauthenticated — confirms public route.
8. [ ] Resolve an approval → a row in `outbox_events` is drained to `dispatched` within ~10s —
       confirms Celery beat + drain_outbox running.
9. [ ] Hammer `POST /auth/login` > 10 times/min from one IP → `429` — confirms rate limiting
       **and** that the rate limiter sees the real client IP (not the proxy IP).

## 14. Post-deploy monitoring (first hour)

- [ ] Watch Sentry for any error bursts; verify first event arrives.
- [ ] Confirm Celery beat ticks: `drain-outbox-every-10s` and `check-weather-every-6h` in worker logs.
- [ ] `SELECT status, COUNT(*) FROM outbox_events GROUP BY status;` — no accumulating `pending` backlog.
- [ ] Check provider quotas: Nominatim and Unsplash are the tightest. Watch for 429s in logs.
- [ ] Review `X-Process-Time` distribution on `/trips/{id}/itinerary/generate` — p95 should be
      under the 600s task hard limit.
