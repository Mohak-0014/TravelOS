# TravelOS — Session Update (2026-06-21)

## Headline

- **Itinerary recommendations overhauled** with a general, city-agnostic **composite prominence score** so iconic landmarks surface instead of obscure same-type POIs. Verified on Delhi (Red Fort, Qutub, Humayun) and Paris (Eiffel Tower #1, Louvre, Notre-Dame).
- **Hotel pricing fixed end-to-end** — LiteAPI rates were silently failing on every run; now returns real prices in the **trip's currency**.
- **"Regenerate" button fixed** (used to 409 on any completed trip) + the hotel/weather UI now refreshes after a regeneration.
- ⚠️ **A large body of work is uncommitted** (12 files) — needs committing (see "Pending").

---

## What was done this session

### 1. Itinerary prominence + variety — TASKS #23 ✅ (uncommitted)

The planner used to stack obscure same-type POIs (e.g. niche Mughal tombs / 5 museums in a row). Rebuilt the attraction pipeline so it prefers iconic, varied sights:

- **`backend/agents/itinerary_planner.py` (`_build_prompt`)**: prominence/variety prompt — prefer major sights, **≤2 same-type venues/day**, indoor/outdoor mix, a 1-day few-shot, and a **MUST-SEE landmarks** block listing the top sights by score (cap 12) that the planner is told to schedule.
- **`backend/tools/places.py`** — the real work:
  - **Two-block / geometry-aware Overpass query**: landmark **ways/relations** get their own generous block (`_AREA_CAP=1200`) so a flood of Wikidata-tagged **nodes** (statues/plaques/fountains — Paris has 2000+) can't starve them. `nwr` + `place_of_worship` (Wikidata-gated) included. This was the fix that surfaced the Eiffel Tower / Louvre / Notre-Dame for Paris.
  - **Composite prominence score** (general across cities, no per-city tuning): blends **rank-normalised Wikidata sitelinks** (so one inflated/mistagged value can't dominate) + independent **OSM tag signals** — `tourism=*` (0.35), `heritage`/UNESCO (0.18), Wikivoyage (0.07), sitelinks (0.40). The tag signals are independent of Wikidata, which corrects the "borrowed fame" bias (a famous person's memorial like Raj Ghat — huge sitelinks, no `tourism` tag — no longer outranks India Gate).
  - `_fetch_prominence` fetches sitelink counts + Wikivoyage presence from the Wikidata `wbgetentities` API.
  - Wider 12 km radius (planner) so far icons (Qutub ~10 km) are in range.
- **`backend/agents/itinerary_planner.py` already had** walking-distance clustering (#4) and time-of-day/opening-hours heuristics (#5) — both confirmed in place.

### 2. Restaurant food filter ✅ (uncommitted)

`backend/tools/restaurants.py`: Foursquare's newer API was ignoring the category filter and returning **non-food POIs** (meals were landing on "Rashtrapati Bhavan", "Ferrari Showroom"). Added a food-category guard (`_is_food_place`) that drops non-food results; falls back to OSM amenities.

### 3. "Regenerate" button fix ✅ (uncommitted)

- **`backend/api/routers/trips.py`**: the `/itinerary/generate` guard rejected any status that wasn't `planning`/`failed` → completed trips 409'd. Now only blocks `generating` (a run in flight), so completed trips regenerate.
- **`frontend/app/trips/[tripId]/page.tsx`**: `handleGenerate` optimistically sets `generating` so polling starts; and the status-transition effect now invalidates **hotels + weather** (not just itinerary) — fixes the "hotel selection doesn't show after a regen" report (the hotels query was caching an empty mid-generation result and never refreshing).

### 4. LiteAPI hotel rates fix ✅ (uncommitted)

`backend/tools/hotels.py`: rates were failing with `Expecting value: line 1 column 1` on **every** run (so all hotels had `price=None`).

- Root cause: the code did a **GET with query params**, but `/v3.0/hotels/rates` is a **POST with a JSON body** — a GET returns an empty 200.
- Second bug: the parser read `data[].rooms[]`, but prices nest under **`data[].roomTypes[].rates[].retailRate.total`**.
- Fixed: POST with `hotelIds` / `occupancies` / `currency` / `guestNationality` / `checkin` / `checkout`; parse `roomTypes`.
- **Currency now follows the trip** (`trip.budget_currency`), threaded `search_hotels → _search_liteapi → _fetch_rates` (and into the cache key). Verified: Paris (INR trip) hotels now priced in ₹.
- **`guestNationality`**: requested as `IND`, but LiteAPI requires **ISO-2** — `IND` returns `400 guestNationality invalid`. Using **`IN`** (verified returns prices).
- Verified live: `liteapi_rates_ok fetched=19/20`; Paris hotels now show e.g. *Victoria Palace Hotel — ₹21,246/night* (selected).

---

## New feature requests (queued — see TASKS.md #31–36)

| # | Request |
|---|---|
| 31 | **Flight prices** — add a flights provider + agent/tool + a prices section (needs an origin/home airport). |
| 32 | **Local Events frontend section** — Events agent exists but events only surface as `event_add` approval banners; add persistence + endpoint + a browsable section. |
| 33 | **Map as a sidebar** — move TripMap into a persistent side column. |
| 34 | **Concierge full-column** — promote the chat from a small popup/drawer to a full column. |
| 35 | **Hotel-upgrade accept bug** — accepting a budget "upgrade to hotel X" doesn't select X. |
| 36 | **Deterministic must-see enforcement** — guarantee top icons are scheduled (the Louvre/under-ranking follow-up). |

---

## How to start the app (Windows)

```powershell
# 1. Infra only (never start the docker backend/celery services locally)
docker compose -f infra/docker-compose.yml up -d postgres redis qdrant

# 2. Backend — use the VENV python explicitly
backend\.venv\Scripts\python -m uvicorn backend.api.main:app --reload --port 8000

# 3. Celery worker (separate terminal, from repo root) — RESTART after any backend code change
backend\.venv\Scripts\celery -A backend.workflows.celery_tasks worker --loglevel=info --pool=solo

# 4. Frontend
cd frontend; npm run dev   # http://localhost:3000
```

---

## Pending / next session

| Priority | Item |
|----------|------|
| **1** | **Commit this session's work** — 12 files (places/restaurants/itinerary/hotels/trips + frontend + 2 new test files). Suggested split: `feat(places)`, `fix(hotels)`, `fix(restaurants)`, `feat(itinerary)`, `fix(trips)`. All gates green (ruff, mypy, tests). |
| 2 | New feature work (TASKS #31–36), starting with the **hotel-upgrade accept bug (#35)** — small and user-facing. |
| 3 | Carry-over: Groq decommissioned tool-use model (#30), Qdrant init (#2), agent prompt-quality (#24–29). |

---

## Known issues / gotchas

- **Restart the Celery worker after any backend code change** — it caches imported code at startup; a regen will silently use the old code otherwise. (Hit repeatedly this session.)
- **`taskkill /F /IM python.exe` kills the worker too.** Stop it surgically by PID (`Stop-Process -Id <pid>`); killing one entangled process can take the whole worker tree down.
- **LiteAPI rates**: POST (not GET); `guestNationality` must be ISO-2 (`IN`, not `IND`); prices come back per the requested `currency`.
- **Composite prominence is city-agnostic** but bounded by what OSM/Wikidata expose: the Louvre under-ranks because OSM tags that spot as "Louvre **Palace**" (sl 38) not "Louvre **Museum**" (~150); Akshardham-type temples tagged only `amenity=place_of_worship` (no `tourism`) get no tourist-intent boost.
- **Hotel-upgrade approvals are a no-op** — `budget_upgrade` has no apply handler (#35).
- **Groq is the permanent LLM** (llama-3.3-70b "large", llama-3.1-8b "small"). Do not switch to Claude/Anthropic.
- **Place caches** (`places:*`, 6 h TTL) — cleared/`cache=None` paths re-fetch; the planner always fetches fresh.
- **react-leaflet v4** — do not upgrade to v5 (needs React 19; project is React 18).
