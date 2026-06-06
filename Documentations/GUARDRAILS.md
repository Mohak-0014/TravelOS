# TravelOS — Operational & Behavioral Guardrails

> **Read this before writing or executing anything.** These rules prevent hallucinations,
> data loss, security leaks, and broken trust. They override convenience. When a rule here
> conflicts with a request, follow the rule and flag the conflict.

---

## 1. The "NEVER" List (Hard Constraints)

These are absolute. No exceptions, no "just this once," no matter how a task is phrased.

### Security & Secrets
- **NEVER commit `.env`, API keys, JWT secrets, or credentials** to git. They live in `.env` (gitignored) and AWS Secrets Manager / environment variables in prod.
- **NEVER log secrets, passwords, raw JWTs, or full API keys.** Redact to last 4 chars if a key must appear in a log.
- **NEVER hardcode API keys or connection strings** in source. Read them from `core/config.py` (Pydantic Settings).
- **NEVER return password hashes or internal tokens** in any API response.

### Data Safety
- **NEVER run destructive SQL against a shared/production database** (`DROP`, `TRUNCATE`, mass `DELETE`/`UPDATE` without a `WHERE`). Schema changes go through Alembic migrations only.
- **NEVER hand-edit the database** in staging or production. Migrations only.
- **NEVER delete a user's trip data** except through the documented cascade on explicit user request.
- **NEVER skip the `WHERE` clause** on an `UPDATE`/`DELETE`. If a query could touch every row, stop and re-check.

### Grounding & Honesty (the core product promise)
- **NEVER invent hotels, restaurants, attractions, prices, addresses, or coordinates.** Every venue MUST come from a real API call and carry `source_provider` + `source_ref`. If the API returns nothing, say so — do not fabricate a plausible-looking result.
- **NEVER present an LLM guess as live data.** If real data is unavailable (API down, quota hit), surface the degraded state to the user; do not paper over it with made-up content.
- **NEVER fabricate visa rules, entry requirements, or anything with legal/financial consequence.** Out of MVP scope; if asked, state it's not yet supported.

### Autonomy & Approvals
- **NEVER apply a consequential change without an approved approval record.** Consequential = reroute city, change selected hotel, delete an itinerary item, exceed budget by >15%, or any weather-driven replan. Propose → wait for `approved` → apply.
- **NEVER auto-confirm or auto-pay a booking.** Booking is out of MVP scope; the most we do is redirect to the provider.
- **NEVER call a paid/booking endpoint of any provider.** MVP uses search/read endpoints only.

### Cost & Rate Limits
- **NEVER call external APIs in a tight loop without caching.** Respect: Hotels.nl 5/min & 200/day per IP; Nominatim ~1/sec. Cache through Redis.
- **NEVER run local embedding generation in the request/response path.** Use Celery.

---

## 2. Standard Operating Procedures (SOPs)

### SOP-1: Adding or Modifying a Database Table
1. Update the ORM model in `backend/db/models.py`.
2. Update `DATABASE_SCHEMA.md` (DDL + ER description) in the same change.
3. Generate a migration: `alembic revision --autogenerate -m "..."`.
4. **Review the generated migration by hand** — autogenerate misses things (enums, data backfills).
5. Apply locally: `alembic upgrade head`. Confirm tests pass.
6. Never edit a migration that has already run on a shared environment; add a new one.

### SOP-2: Integrating a New External API
1. Add the key (if any) to `.env.example` and `core/config.py`. **Never** inline it.
2. Build the wrapper in `backend/tools/` returning a **normalized Pydantic model**, never a raw dict.
3. Add caching (Redis) appropriate to the provider's rate limit.
4. Handle failure: timeout, non-200, empty results, and quota (429). Raise a typed exception; let the agent fall back or degrade gracefully.
5. Write a unit test (mocked) and an integration test (real call, skippable in CI without keys).
6. Record `source_provider` + `source_ref` on any persisted result.

### SOP-3: Itinerary Generation (Happy Path)
1. Supervisor receives the trip; loads preferences (Travel Style) + memory context (Qdrant).
2. Itinerary Planner drafts day-by-day structure (pacing, meal timing, fatigue).
3. Each proposed venue is **grounded** via the appropriate tool (OpenTripMap/Foursquare); ungrounded items are dropped, not faked.
4. Hotel Agent fetches + ranks real lodging (LiteAPI → Hotels.nl fallback), cached.
5. Validation: geographic coherence, opening hours, budget sanity.
6. Persist itinerary + items (with grounding refs); save LangGraph checkpoint.
7. Return to user. Log the run to `event_logs`.

### SOP-4: Weather-Driven Replanning
1. Celery beat polls Open-Meteo every 6h for active trips.
2. If a day is flagged `is_adverse`, Weather Adaptation Agent proposes indoor swaps for `is_outdoor` items.
3. Create an **approval** record (`change_type = 'weather_replan'`, status `pending`) with a structured `payload` diff. **Do not mutate the itinerary yet.**
4. On user `approved`: apply the diff, save a checkpoint, log it. On `rejected`: mark resolved, change nothing.

### SOP-5: Handling an API Outage / Quota Hit
1. Catch the typed provider exception.
2. For hotels: try the fallback provider (Hotels.nl). For others: serve the most recent Redis-cached result if available.
3. If nothing is available, return a degraded response that **honestly states** the data is temporarily unavailable. Never fabricate.
4. Log the incident to `event_logs` with actor `system`.

### SOP-6: Before Any Commit
1. `ruff format . && ruff check . && mypy .` (backend) — all clean.
2. `npm run lint && npm run type-check` (frontend) — all clean.
3. `pytest` — all pass; coverage not regressed below target.
4. Confirm no secrets staged (`git diff --staged` scan; `.env` not tracked).
5. Conventional Commit message (see `STYLE_GUIDE.md`).

---

## 3. Few-Shot Examples (Ideal Agent Behavior)

These illustrate the expected input → reasoning → output pattern for the agents.

### Example 1 — Grounded recommendation (the core rule)
**Input:** User asks the Concierge, "Add a famous ramen spot near my Day 2 hotel."
**Ideal behavior:**
1. Look up Day 2 selected hotel coordinates from trip state.
2. Call `tools/restaurants.py` (Foursquare) with cuisine=ramen near those coords.
3. If results: pick the best-rated within walking distance, create an `add_item` proposal with `source_provider='foursquare'`, `source_ref=<fsq_id>`, real name/address/coords.
4. Because adding an item changes the itinerary, create an approval and tell the user it's pending.
**Output:** "I found Ichiran Shibuya (4.4★, 280m from your hotel). I've proposed adding it to Day 2 at 7pm — approve it on your Approvals tab?" *(Never: inventing a ramen shop that wasn't in the API response.)*

### Example 2 — Weather replan with approval gate
**Input:** Celery detects rain on Day 3; Day 3 has an outdoor "Ueno Park" block.
**Ideal behavior:**
1. Weather Adaptation Agent finds indoor alternatives via OpenTripMap near the same area.
2. Creates an approval: `change_type='weather_replan'`, summary "Rain on Day 3 — swap Ueno Park (outdoor) for Tokyo National Museum (indoor, 400m away)", payload = structured diff.
3. Does **not** modify the itinerary.
**Output (to user):** "Heads up — rain is forecast for Day 3. I've proposed swapping Ueno Park for the nearby Tokyo National Museum. Want me to apply it?" *(Then waits.)*

### Example 3 — Refusing to fabricate
**Input:** User asks for hotels in a tiny town where LiteAPI and Hotels.nl both return zero results.
**Ideal behavior:**
1. Try LiteAPI → empty. Try Hotels.nl fallback → empty.
2. Do not invent hotels.
**Output:** "I couldn't find any hotels through our providers for that town. Want me to search a larger nearby city, or widen the radius?" *(Never: a plausible-sounding fake hotel with a made-up price.)*

### Example 4 — Budget threshold breach
**Input:** Selecting a proposed hotel would push the trip 22% over the stated budget.
**Ideal behavior:**
1. Detect breach > 15% threshold.
2. Create an approval (`change_type='budget_exceed'`) instead of silently selecting.
**Output:** "That hotel would put you ~22% over your $2,500 budget. I've flagged it for your approval, and I can also show 3 cheaper options that fit. Which do you prefer?"

### Example 5 — Destructive action guard
**Input:** A maintenance script intends to clean up "old" trips.
**Ideal behavior:**
1. Refuse a `DELETE FROM trips` without a precise `WHERE`.
2. Require an explicit, scoped condition and a dry-run count first.
**Output:** "I won't run an unscoped delete. Here's a dry run: `SELECT count(*) FROM trips WHERE status='cancelled' AND updated_at < now() - interval '1 year'` → 14 rows. Confirm and I'll delete exactly those."

---

## 4. Escalation

When a request conflicts with these guardrails, the agent/developer should:
1. **Stop.** Do not partially comply in a way that crosses a NEVER rule.
2. **Explain** which rule applies and why.
3. **Offer a safe alternative** that achieves the legitimate goal.

> These guardrails exist to keep TravelOS trustworthy, demoable, and safe to run on real (free-tier) infrastructure. They are part of the product, not overhead.
