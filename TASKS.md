# TravelOS — Next Steps Task List

Last updated: 2026-06-13

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
| 3 | **Build Approval UI (approve/reject pending changes)** | `frontend/app/trips/[tripId]/page.tsx` | Fetch `GET /trips/{id}/approvals`, render a banner per pending approval with Approve/Reject buttons wired to existing `POST /trips/{id}/approvals/{id}/approve` and `/reject` endpoints. Completes the approval gate loop. |

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
| 10 | **Local Events agent** | `backend/agents/events.py` (new), `backend/graphs/trip_graph.py` | Fetch events for city + date range from Ticketmaster API (free tier) or Eventbrite after `itinerary_planner`. Create approval proposals for notable events ("Jazz Festival on Day 2 — add evening performance?"). Flag venue closures on event days. |
| 11 | **Budget Optimizer agent** | `backend/agents/budget_optimizer.py` (new), `backend/graphs/trip_graph.py` | After `hotel_agent`: compute estimated spend per category (lodging/activities/meals/transport), compare to `budget_total`. If >15% over → propose specific swaps (replace paid attraction with free one, downgrade hotel tier). If well under → suggest upgrades. All changes through approval gate. |

### Long-Term / Learning

| # | Task | File(s) | Notes |
|---|---|---|---|
| 12 | **Rejection feedback learning loop** | `backend/db/models.py`, `backend/agents/travel_style.py`, Alembic migration | Add `user_feedback` table (trip_id, change_type, context_tags, accepted bool). Write on approve/reject. Inject top 3 recent rejections into Travel Style prompt ("User previously rejected museum suggestions for rain days — they prefer cafes"). |

### Testing

| # | Task | File(s) | Notes |
|---|---|---|---|
| ~~9~~ | ~~Boost API router test coverage to >80%~~ | ~~`backend/tests/`~~ | ~~Done: 71 router tests, 100% coverage across all 5 routers (284 stmts). 453 total unit tests passing.~~ |

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
