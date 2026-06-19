# TravelOS — Next Steps Task List

Last updated: 2026-06-19

## Priority Order

### Quick Fixes

| # | Task | File(s) | Notes |
|---|---|---|---|
| 2 | **Initialize Qdrant collections on startup** | `backend/api/main.py` | Call `ensure_collections()` in a FastAPI startup event. Without this, `trip_memories` and `user_preferences` don't exist for fresh installs — Travel Style and Concierge degrade silently. |
| 7 | **Inject travel_style_profile into weather adaptation** | `backend/agents/weather.py` lines 318-324 | Read `activity_preference`, `dining_preference`, `budget_priority` from state and inject into the weather adaptation LLM prompt so replacements match user taste (e.g. art gallery not bowling alley). |
| 8 | **Enforce pace item count in validation** | `backend/graphs/validation.py` | Post-parse check: if any day has fewer than `pace_target - 1` items, flag for replan. Conflict detection already checks >8 items; mirror for under-count. Add unit test. |

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
| 17 | **Packing List agent** | `backend/agents/packing.py` (new), `frontend/app/trips/[tripId]/page.tsx` | Generate context-aware packing list from destination climate, trip duration, activities in itinerary. UI: collapsible checklist panel on trip detail with category grouping (clothing, electronics, documents). |
| 18 | **Agent Activity Log drawer** | `frontend/components/ui/ActivityDrawer.tsx` (new), `frontend/app/trips/[tripId]/page.tsx` | Slide-in right drawer showing real-time agent run log (which agents ran, what tools they called, timings). Poll `GET /trips/{id}/run-log` endpoint. Useful for debugging and transparency. |
| 19 | **Share Trip link** | `frontend/app/trips/[tripId]/share/page.tsx` (new), `backend/api/routers/trips.py` | Generate a public read-only share URL (`/trips/{id}/share?token=...`). Backend: create a signed short-lived token. Frontend: public page showing itinerary summary without requiring auth. |

---

## Done (this session)

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
