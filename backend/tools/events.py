"""Events tool — fetches and normalises events from Ticketmaster and Eventbrite."""

from __future__ import annotations

import asyncio
from datetime import date, time

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_TM_CACHE_TTL = 3600  # 1 hour
_EB_CACHE_TTL = 7200  # 2 hours

# Eventbrite category IDs that are travel-relevant
_EB_TRAVEL_CATEGORY_IDS = {"103", "102", "101", "105", "113"}
_EB_CATEGORY_NAMES: dict[str, str] = {
    "103": "Music",
    "102": "Sports",
    "101": "Food & Drink",
    "105": "Arts & Theatre",
    "113": "Community",
}


class EventOffer(BaseModel):
    name: str
    event_date: date
    start_time: time | None = None
    venue_name: str
    lat: float | None = None
    lng: float | None = None
    category: str
    price_min: float | None = None
    price_max: float | None = None
    price_currency: str | None = None
    source: str  # "ticketmaster" | "eventbrite"
    url: str
    image_url: str | None = None


# ── Ticketmaster ──────────────────────────────────────────────────────────────


def _parse_tm_event(raw: dict) -> EventOffer | None:  # type: ignore[type-arg]
    try:
        name = raw.get("name", "").strip()
        if not name:
            return None

        start_info = raw.get("dates", {}).get("start", {})
        date_str = start_info.get("localDate")
        if not date_str:
            return None
        event_date = date.fromisoformat(date_str)

        start_time: time | None = None
        time_str = start_info.get("localTime")
        if time_str:
            try:
                start_time = time.fromisoformat(time_str)
            except ValueError:
                pass

        venues = raw.get("_embedded", {}).get("venues", [{}])
        venue = venues[0] if venues else {}
        venue_name = venue.get("name") or "Unknown Venue"
        loc = venue.get("location", {})
        try:
            lat = float(loc["latitude"]) if loc.get("latitude") else None
            lng = float(loc["longitude"]) if loc.get("longitude") else None
        except (ValueError, TypeError):
            lat = lng = None

        classifications = raw.get("classifications") or [{}]
        category = (classifications[0].get("segment") or {}).get("name") or "General"

        price_ranges = raw.get("priceRanges") or []
        price_min = price_ranges[0].get("min") if price_ranges else None
        price_max = price_ranges[0].get("max") if price_ranges else None
        price_currency = price_ranges[0].get("currency") if price_ranges else None

        images = raw.get("images") or []
        image_url = next((img["url"] for img in images if img.get("ratio") == "16_9"), None)
        if not image_url and images:
            image_url = images[0].get("url")

        return EventOffer(
            name=name,
            event_date=event_date,
            start_time=start_time,
            venue_name=venue_name,
            lat=lat,
            lng=lng,
            category=category,
            price_min=price_min,
            price_max=price_max,
            price_currency=price_currency,
            source="ticketmaster",
            url=raw.get("url") or "",
            image_url=image_url,
        )
    except Exception as exc:
        logger.debug("tm_event_parse_failed", error=str(exc))
        return None


async def fetch_ticketmaster(
    city: str,
    country: str | None,
    start_date: date,
    end_date: date,
    api_key: str,
    cache: Redis | None = None,
) -> list[EventOffer]:
    """Fetch events from Ticketmaster Discovery API. Returns [] on any failure."""
    if not api_key:
        logger.info("ticketmaster_skipped", reason="no_api_key")
        return []

    cache_key = f"events:tm:{city.lower()}:{start_date.isoformat()}:{end_date.isoformat()}"
    cached = await redis_get_cached(cache, cache_key)
    if cached:
        logger.info("ticketmaster_cache_hit", city=city)
        return [EventOffer(**e) for e in cached]

    params: dict[str, str] = {
        "apikey": api_key,
        "city": city,
        "startDateTime": f"{start_date.isoformat()}T00:00:00Z",
        "endDateTime": f"{end_date.isoformat()}T23:59:59Z",
        "size": "50",
    }
    if country:
        params["countryCode"] = country[:2].upper()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params=params,
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.warning("ticketmaster_fetch_failed", city=city, error=str(exc))
        return []

    raw_events: list[dict] = payload.get("_embedded", {}).get("events", [])  # type: ignore[type-arg]
    events: list[EventOffer] = []
    for raw in raw_events:
        offer = _parse_tm_event(raw)
        if offer:
            events.append(offer)

    if events:
        await redis_set_cached(
            cache, cache_key, [e.model_dump(mode="json") for e in events], _TM_CACHE_TTL
        )

    logger.info("ticketmaster_fetch_ok", city=city, count=len(events))
    return events


# ── Eventbrite ────────────────────────────────────────────────────────────────


def _parse_eb_event(raw: dict) -> EventOffer | None:  # type: ignore[type-arg]
    try:
        name = (raw.get("name") or {}).get("text", "").strip()
        if not name:
            return None

        category_id = str(raw.get("category_id") or "")
        if category_id not in _EB_TRAVEL_CATEGORY_IDS:
            return None

        utc_str = (raw.get("start") or {}).get("utc", "")
        if not utc_str:
            return None
        event_date = date.fromisoformat(utc_str[:10])
        try:
            start_time: time | None = time.fromisoformat(utc_str[11:19])
        except ValueError:
            start_time = None

        venue = raw.get("venue") or {}
        venue_name = venue.get("name") or "Unknown Venue"
        address = venue.get("address") or {}
        try:
            lat = float(address["latitude"]) if address.get("latitude") else None
            lng = float(address["longitude"]) if address.get("longitude") else None
        except (ValueError, TypeError):
            lat = lng = None

        logo = raw.get("logo") or {}
        image_url = (logo.get("original") or {}).get("url")

        return EventOffer(
            name=name,
            event_date=event_date,
            start_time=start_time,
            venue_name=venue_name,
            lat=lat,
            lng=lng,
            category=_EB_CATEGORY_NAMES.get(category_id, "General"),
            source="eventbrite",
            url=raw.get("url") or "",
            image_url=image_url,
        )
    except Exception as exc:
        logger.debug("eb_event_parse_failed", error=str(exc))
        return None


async def fetch_eventbrite(
    city: str,
    start_date: date,
    end_date: date,
    token: str,
    cache: Redis | None = None,
) -> list[EventOffer]:
    """Fetch events from Eventbrite API. Returns [] on any failure."""
    if not token:
        logger.info("eventbrite_skipped", reason="no_token")
        return []

    cache_key = f"events:eb:{city.lower()}:{start_date.isoformat()}:{end_date.isoformat()}"
    cached = await redis_get_cached(cache, cache_key)
    if cached:
        logger.info("eventbrite_cache_hit", city=city)
        return [EventOffer(**e) for e in cached]

    params: dict[str, str] = {
        "token": token,
        "location.address": city,
        "start_date.gte": f"{start_date.isoformat()}T00:00:00",
        "start_date.lte": f"{end_date.isoformat()}T23:59:59",
        "expand": "venue",
        "page_size": "50",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://www.eventbriteapi.com/v3/events/search/",
                params=params,
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.warning("eventbrite_fetch_failed", city=city, error=str(exc))
        return []

    raw_events: list[dict] = payload.get("events", [])  # type: ignore[type-arg]
    events: list[EventOffer] = []
    for raw in raw_events:
        offer = _parse_eb_event(raw)
        if offer:
            events.append(offer)

    if events:
        await redis_set_cached(
            cache, cache_key, [e.model_dump(mode="json") for e in events], _EB_CACHE_TTL
        )

    logger.info("eventbrite_fetch_ok", city=city, count=len(events))
    return events


# ── Merge ─────────────────────────────────────────────────────────────────────


async def fetch_events(
    city: str,
    country: str | None,
    start_date: date,
    end_date: date,
    ticketmaster_key: str,
    eventbrite_token: str,
    cache: Redis | None = None,
) -> list[EventOffer]:
    """
    Fetch from both APIs in parallel, deduplicate by (venue_name, event_date),
    and return sorted by date. Ticketmaster record wins on collision.
    Degrades gracefully if one source fails.
    """
    tm_result, eb_result = await asyncio.gather(
        fetch_ticketmaster(city, country, start_date, end_date, ticketmaster_key, cache),
        fetch_eventbrite(city, start_date, end_date, eventbrite_token, cache),
        return_exceptions=True,
    )

    tm_events: list[EventOffer] = tm_result if isinstance(tm_result, list) else []
    eb_events: list[EventOffer] = eb_result if isinstance(eb_result, list) else []

    seen: dict[tuple[str, date], EventOffer] = {}
    for event in tm_events:
        seen[(event.venue_name.lower(), event.event_date)] = event
    for event in eb_events:
        key = (event.venue_name.lower(), event.event_date)
        if key not in seen:
            seen[key] = event

    merged = sorted(seen.values(), key=lambda e: e.event_date)
    logger.info("events_merged", total=len(merged), tm=len(tm_events), eb=len(eb_events))
    return merged
