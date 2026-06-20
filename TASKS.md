# TravelOS — Next Steps Task List

Last updated: 2026-06-20

## In progress / immediate (2026-06-20)

| # | Task | Notes |
|---|---|---|
| B | **Push + commit pending work** | Push `bdf6f7f` (sharing) to `origin/master`; then commit the Golden Hour redesign and the packing/English-names fixes (3 logical commits). |
| C | **Reset stuck `generating` trip** | One older trip is stuck in `generating` from a previously-killed worker run — reset to `planning`. |

## Priority Order

### Quick Fixes

| # | Task | File(s) | Notes |
|---|---|---|---|
| 2 | **Initialize Qdrant collections on startup** | `backend/api/main.py` | Call `ensure_collections()` in a FastAPI startup event. Without this, `trip_memories` and `user_preferences` don't exist for fresh installs — Travel Style and Concierge degrade silently. |
| 7 | **Inject travel_style_profile into weather adaptation** | `backend/agents/weather.py` lines 318-324 | Read `activity_preference`, `dining_preference`, `budget_priority` from state and inject into the weather adaptation LLM prompt so replacements match user taste (e.g. art gallery not bowling alley). |
| 8 | **Enforce pace item count in validation** | `backend/graphs/validation.py` | Post-parse check: if any day has fewer than `pace_target - 1` items, flag for replan. Conflict detection already checks >8 items; mirror for under-count. Add unit test. |

### Agent Prompt Quality (2026-06-20)

Tune the LLM prompts so agents produce more useful, higher-quality results. Highest-leverage first; the Itinerary Planner is the most visible win.

| # | Task | File(s) | Notes |
|---|---|---|---|
| 23 | **Itinerary Planner — prominence + variety** | `backend/agents/itinerary_planner.py` (`_build_prompt`) | Observed: output stacks obscure, same-type POIs (~5 niche museums in a row in Tokyo) instead of iconic sights. Prompt should (a) strongly prefer well-known / major attractions, (b) cap same-type venues per day (≤2 museums), (c) balance indoor/outdoor + activity variety, (d) include a 1-day few-shot example. Consider passing a prominence signal (OSM `wikidata`/`wikipedia` tag presence) so the model can rank by fame. |
| 24 | **Travel Style — structured persona synthesis** | `backend/agents/travel_style.py` | Tighten the synthesis prompt to emit a consistent persona schema; degrade gracefully for new users with no history; weight the injected recent-rejections more explicitly. |
| 25 | **Packing List — concise, destination-rich prompt** | `backend/agents/packing_list.py` (`_SYSTEM_PROMPT`) | Now truncation-hardened, but tune the prompt so the small model stops over-generating: hard cap ≤6 categories / ≤35 items, richer Destination-Specific items, weather-driven additions tied to `risk_flags`. |
| 26 | **Weather adaptation — taste-aware replacements** | `backend/agents/weather.py` | Supersedes #7. When swapping a rained-out outdoor activity, inject `travel_style_profile` + nearby indoor candidates so replacements match user taste (art gallery, not bowling alley). |
| 27 | **Budget Optimizer — user-facing swap rationale** | `backend/agents/budget_optimizer.py` | Prompt should produce a concrete human reason per proposal ("saves ¥X while keeping your food priority"), not terse numeric deltas. |
| 28 | **Concierge — richer grounded context** | `backend/agents/concierge.py` | Inject full current itinerary + budget summary + weather into the system prompt; add explicit grounding / refusal rules so it never invents places or prices. |
| 29 | **Events — relevance filtering prompt** | `backend/agents/events.py` | Improve the scoring/filter prompt to better match events to user interests + trip dates; drop low-relevance noise that currently slips through. |

### Frontend

| # | Task | File(s) | Notes |
|---|---|---|---|
| ~~3~~ | ~~Build Approval UI (approve/reject pending changes)~~ | ~~`frontend/app/trips/[tripId]/page.tsx`~~ | ~~Done: approval banner with Approve/Reject wired to existing endpoints, dark-space redesign of Trip Detail page.~~ |

### Itinerary Quality Improvements

| # | Task | File(s) | Notes |
|---|---|---|---|
| 4 | **Add walking distance clustering to itinerary planner** | `backend/agents/itinerary_planner.py` `_build_prompt` | Bucket attractions into ~1 km grid cells before calling LLM. Inject cluster labels into prompt ("Group A — northwest near X"). Also inject `walking_tolerance` (low=500 m, medium=2 km, high=5 km) as a hard constraint. |
| 5 | **Add time-of-day heuristics for venue scheduling** | `backend/tools/places.py`, `backend/agents/itinerary_planner.py` | Add `opening_hours` field to `Attraction` model from Overpass tags. Inject heuristic rules into prompt by type: museums 09:00-17:00, lunch 12:00-14:00, dinner 19:00-22:00, nightlife 21:00+. |

### Concierge Enhancements

| # | Task | File(s) | Notes |
|---|---|---|---|
| 6 | **Give Concierge a ProposeItineraryChange tool** | `backend/agents/concierge.py`, `backend/api/routers/concierge.py` | Add a `ProposeItineraryChange(day, item_index, replacement)` tool that creates an `ApprovalRequest` record. User sees an approval banner; on approve the swap is applied. Transforms Concierge from read-only Q&A into a real planning assistant. |

### New Agents

| # | Task | File(s) | Notes |
|---|---|---|---|
| ~~10~~ | ~~Local Events agent~~ | ~~`backend/agents/events.py`~~ | ~~Done: Ticketmaster + Eventbrite dual fetch, embedding scoring, gap detection, conflict warnings, 24 tests, 478 total passing. commit ba05c50~~ |
| ~~11~~ | ~~Budget Optimizer agent~~ | ~~`backend/agents/budget_optimizer.py`~~ | ~~Done: spend-per-category breakdown, >15% over threshold triggers swap proposals via approval gate, injected into trip_graph after hotel_agent.~~ |

### Long-Term / Learning

| # | Task | File(s) | Notes |
|---|---|---|---|
| ~~12~~ | ~~Rejection feedback learning loop~~ | ~~`backend/db/models.py`, `backend/agents/travel_style.py`, Alembic migration~~ | ~~Done: user_feedback table, write on approve/reject, top-3 recent rejections injected into Travel Style prompt. Migration `5845b0bf9c6e`.~~ |

### Testing

| # | Task | File(s) | Notes |
|---|---|---|---|
| ~~9~~ | ~~Boost API router test coverage to >80%~~ | ~~`backend/tests/`~~ | ~~Done: 71 router tests, 100% coverage across all 5 routers (284 stmts). 453 total unit tests passing.~~ |

### Frontend — Next Session

| # | Task | File(s) | Notes |
|---|---|---|---|
| ~~17~~ | ~~Packing List agent~~ | ~~`backend/agents/packing_list.py`, `frontend/app/trips/[tripId]/page.tsx`~~ | ~~Done: Haiku LLM generates categorized checklist (Clothing/Electronics/Documents/Health/Accessories/Destination-Specific), season-aware, packing_state in graph, Trip.packing_list JSON column (migration b1df5cfd3ec3), collapsible checklist UI with per-item checkboxes and progress bar, 11 tests, 528 total. commit 1201158~~ |
| ~~18~~ | ~~Agent Activity Log drawer~~ | ~~`frontend/app/trips/[tripId]/page.tsx`~~ | ~~Done: full-height spring-animated right-edge drawer, groups messages by agent, color-coded per agent, sidebar teaser with 3-event preview. commit 1201158~~ |
| ~~19~~ | ~~**Share Trip link**~~ | ~~`frontend/app/share/[token]/page.tsx`, `backend/api/routers/share.py`, `trips.py`~~ | ~~Done: `POST /trips/{id}/share` (30-day token) + public `GET /api/v1/share/{token}` + read-only share page with cover hero. Also calendar `.ics` export + hotel selection. commit `bdf6f7f`.~~ |
| ~~20~~ | ~~**Onboarding / Travel DNA wizard**~~ | ~~`frontend/app/onboarding/page.tsx`~~ | ~~Done: 4-step post-register wizard (pace / luxury tier / interests / food prefs) → `PUT /api/v1/preferences`; login redirects to `/onboarding` after register. Redesigned to Golden Hour this session.~~ |
| 21 | **Real-time status polling** | `frontend/app/trips/[tripId]/page.tsx` | When trip.status === "generating", poll every 3s via TanStack Query refetchInterval. Currently page shows old state until user manually refreshes. |
| 22 | **Quick-wins: tasks #2, #7, #8** | `backend/api/main.py`, `backend/agents/weather.py`, `backend/graphs/validation.py` | #2: Qdrant collections init on startup. #7: weather agent uses travel_style_profile for activity replacements. #8: validation flags under-count days. All small. |

---

## Done (2026-06-20 session)

- [x] **Golden Hour UI redesign** — dark galaxy → light travel theme across all pages (tokens, globals, Fraunces + Plus Jakarta Sans fonts, new `SkyScene` travel hero, deleted 3D galaxy components). type-check + lint clean, visual QA passed.
- [x] **Task #19 — Trip sharing**: public share token + read-only `/share/[token]` page, calendar `.ics` export, hotel selection endpoint, Unsplash cover photos, Edit/Delete trip modals. commit `bdf6f7f`.
- [x] **Fix — approval resolve endpoint**: frontend now calls `POST /api/v1/approvals/{id}` (Approve / Not-interested buttons were 404ing).
- [x] **Bug fix — packing-list truncation**: hardened `packing_list.py` + `_llm.py` (max_tokens cap, JSON salvage, one retry). +7 tests (18 total). Backfilled Tokyo packing list.
- [x] **Bug fix — English place names**: `places.py` + `restaurants.py` prefer OSM `name:en` / `int_name`; Foursquare `Accept-Language: en`. All future trips render English.
- [x] **Regenerated Tokyo** for English titles — attractions now resolve to OSM `name:en` (Japanese titles 20 → 10; the remainder are Foursquare restaurant names in local script, left as-is).
- [x] **Infra**: resolved port-8000 docker/WinNAT ghost-socket shadowing local uvicorn; restarted Celery worker; purged a duplicate Delhi itinerary task from the queue.

## Done (2026-06-19 session)

- [x] Hotel agent: use `luxury_tier` DB field directly (not text inference)
- [x] Hotel agent: `budget_behavior` → dynamic lodging fraction (frugal=25%, balanced=35%, splurge=45%)
- [x] Travel Style: past trip embeddings injected into LLM synthesis prompt
- [x] Itinerary Planner: pace-driven item count (relaxed=3, moderate=4, packed=6)
- [x] Concierge: `budget_behavior` added to system prompt
- [x] Frontend: hotels endpoint + hotel cards UI
- [x] Schema fix: `destination_country` widened from `varchar(2)` → `varchar(100)` (migration `d5a69b21efbb`)
- [x] GitHub repo: https://github.com/Mohak-0014/TravelOS
- [x] Task #3: Trip Detail Page full redesign (dark-space theme, approval banners, itinerary, hotels, weather)
- [x] Task #11: Budget Optimizer agent wired into graph
- [x] Task #12: Rejection feedback learning loop (user_feedback table + Travel Style injection)
- [x] Task #13: Profile / Travel DNA page (dark-space redesign)
- [x] Task #14: Landing / marketing page (dark-space redesign)
- [x] Task #15: Trips list page redesign (globe panel, status chips, staggered cards)
- [x] Task #16: Trip Creation page redesign (4-step wizard, AnimatePresence, budget tier badge)
