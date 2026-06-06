# TravelOS — API Documentation

> **Base URL (local):** `http://localhost:8000`
> **Base path:** `/api/v1`
> **Auth:** Bearer JWT in `Authorization` header (except `/auth/register` and `/auth/login`).
> All request/response bodies are JSON. Timestamps are ISO 8601 UTC.

This documents the **internal TravelOS REST API** (the contract between the Next.js frontend and the FastAPI backend). External provider APIs (LiteAPI, Hotels.nl, Open-Meteo, etc.) are wrapped server-side in `backend/tools/` and are never called from the browser.

---

## Authentication

### `POST /api/v1/auth/register`
Create a new user.

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mohak@example.com",
    "password": "StrongPass123!",
    "full_name": "Mohak"
  }'
```
**201 Response**
```json
{ "id": "uuid", "email": "mohak@example.com", "full_name": "Mohak", "is_active": true }
```

### `POST /api/v1/auth/login`
Exchange credentials for a JWT.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{ "email": "mohak@example.com", "password": "StrongPass123!" }'
```
**200 Response**
```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400 }
```

> Use the token on every subsequent call: `-H "Authorization: Bearer eyJ..."`

---

## Onboarding / Preferences

### `PUT /api/v1/preferences`
Set or update the user's travel-style profile. Also re-embeds preferences into Qdrant.

```bash
curl -X PUT http://localhost:8000/api/v1/preferences \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pace": "moderate",
    "luxury_tier": "mid",
    "walking_tolerance": "high",
    "food_prefs": ["vegetarian"],
    "interests": ["museums", "food", "architecture"],
    "budget_behavior": "balanced"
  }'
```
**200 Response**: the saved preferences object.

### `GET /api/v1/preferences`
Returns the current user's preferences.

---

## Trips

### `POST /api/v1/trips`
Create a trip. Geocodes the destination (Nominatim) server-side.

```bash
curl -X POST http://localhost:8000/api/v1/trips \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Tokyo Spring Break",
    "destination_city": "Tokyo",
    "destination_country": "JP",
    "start_date": "2025-04-10",
    "end_date": "2025-04-15",
    "num_travelers": 2,
    "budget_total": 2500,
    "budget_currency": "USD"
  }'
```
**201 Response**
```json
{
  "id": "trip-uuid",
  "title": "Tokyo Spring Break",
  "destination_city": "Tokyo",
  "latitude": 35.6762,
  "longitude": 139.6503,
  "status": "planning"
}
```

### `GET /api/v1/trips`
List the current user's trips.

### `GET /api/v1/trips/{trip_id}`
Full trip detail including itinerary, hotel candidates, budget, and pending approvals.

### `DELETE /api/v1/trips/{trip_id}`
Delete a trip (cascades to all children).

---

## Itinerary

### `POST /api/v1/trips/{trip_id}/itinerary/generate`
Kick off the LangGraph multi-agent run to generate the itinerary. This is the core endpoint — it invokes Supervisor → Travel Style → Itinerary Planner → Hotel → validation, grounding every item in real API data.

```bash
curl -X POST http://localhost:8000/api/v1/trips/$TRIP_ID/itinerary/generate \
  -H "Authorization: Bearer $TOKEN"
```
**200 Response**
```json
{
  "trip_id": "trip-uuid",
  "days": [
    {
      "day_number": 1,
      "date": "2025-04-10",
      "items": [
        {
          "id": "item-uuid",
          "item_type": "activity",
          "title": "Senso-ji Temple",
          "start_time": "09:00",
          "end_time": "10:30",
          "latitude": 35.7148,
          "longitude": 139.7967,
          "source_provider": "opentripmap",
          "source_ref": "N123456",
          "is_outdoor": true,
          "est_cost": 0
        }
      ]
    }
  ]
}
```

### `GET /api/v1/trips/{trip_id}/itinerary`
Return the current saved itinerary (no regeneration).

### `POST /api/v1/trips/{trip_id}/itinerary/replan`
Manually trigger a replan (weather-driven replans are usually triggered by Celery). Produces an **approval request** rather than mutating the itinerary directly.

```bash
curl -X POST http://localhost:8000/api/v1/trips/$TRIP_ID/itinerary/replan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "reason": "weather", "day_number": 2 }'
```
**202 Response**
```json
{ "approval_id": "approval-uuid", "status": "pending", "summary": "Rain forecast on Day 2 — propose swapping outdoor park for indoor museum." }
```

---

## Hotels

### `GET /api/v1/trips/{trip_id}/hotels`
Return normalized hotel candidates for the trip (fetched & ranked by the Hotel Agent from LiteAPI, with Hotels.nl fallback). Cached in Redis to respect provider rate limits.

```bash
curl -X GET http://localhost:8000/api/v1/trips/$TRIP_ID/hotels \
  -H "Authorization: Bearer $TOKEN"
```
**200 Response**
```json
{
  "trip_id": "trip-uuid",
  "provider_used": "liteapi",
  "hotels": [
    {
      "id": "cand-uuid",
      "provider": "liteapi",
      "provider_hotel_id": "lp19d80",
      "name": "Park Hotel Tokyo",
      "star_rating": 4.0,
      "price_total": 980.00,
      "price_currency": "USD",
      "price_per_night": 196.00,
      "refundable": true,
      "match_score": 0.87,
      "is_selected": false
    }
  ]
}
```

### `POST /api/v1/trips/{trip_id}/hotels/{candidate_id}/select`
Mark a hotel candidate as selected for the trip.

---

## Approvals (Human-in-the-Loop)

### `GET /api/v1/trips/{trip_id}/approvals`
List approval requests (filterable by `?status=pending`).

```bash
curl -X GET "http://localhost:8000/api/v1/trips/$TRIP_ID/approvals?status=pending" \
  -H "Authorization: Bearer $TOKEN"
```

### `POST /api/v1/approvals/{approval_id}`
Resolve an approval. On `approved`, the stored `payload` diff is applied to the itinerary and a checkpoint is saved.

```bash
curl -X POST http://localhost:8000/api/v1/approvals/$APPROVAL_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "decision": "approved" }'
```
**200 Response**
```json
{ "approval_id": "approval-uuid", "status": "approved", "applied": true }
```
Valid `decision` values: `approved`, `rejected`.

---

## Concierge Chat

### `POST /api/v1/trips/{trip_id}/concierge`
Send a natural-language message. The Concierge Agent answers grounded in the live trip state.

```bash
curl -X POST http://localhost:8000/api/v1/trips/$TRIP_ID/concierge \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "message": "Is day 2 too packed? Can we add a coffee break?" }'
```
**200 Response**
```json
{
  "reply": "Day 2 has 5 stops which is on the busier side given your moderate pace...",
  "proposed_changes": [
    { "type": "add_item", "day_number": 2, "summary": "Add a 30-min coffee break at 15:00" }
  ],
  "requires_approval": true,
  "approval_id": "approval-uuid"
}
```

---

## Standard Error Shape

All errors return a consistent envelope:
```json
{
  "error": {
    "code": "TRIP_NOT_FOUND",
    "message": "Trip with id 'xyz' not found for this user.",
    "detail": null
  }
}
```

| HTTP | `code` examples |
|---|---|
| 400 | `VALIDATION_ERROR`, `INVALID_DATE_RANGE` |
| 401 | `NOT_AUTHENTICATED`, `TOKEN_EXPIRED` |
| 403 | `FORBIDDEN` |
| 404 | `TRIP_NOT_FOUND`, `APPROVAL_NOT_FOUND` |
| 429 | `PROVIDER_RATE_LIMITED` (upstream hotel API throttled; served stale cache if available) |
| 502 | `PROVIDER_ERROR` (upstream API failed; fallback attempted) |
| 500 | `INTERNAL_ERROR` |

---

## Interactive Docs

FastAPI auto-generates live docs:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

> Keep this file in sync with the generated OpenAPI spec. When endpoints change, update both the route and this document.
