"""Flights tool — round-trip prices via the Duffel API."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import BaseModel

from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached
from backend.tools.resilience import resilient_request

logger = get_logger(__name__)

_BASE = "https://api.duffel.com"
_OFFER_REQUESTS_URL = f"{_BASE}/air/offer_requests"
_PLACES_URL = f"{_BASE}/places/suggestions"
_VERSION = "v2"

_IATA_TTL = 86400  # 24h cache for airport lookups
_OFFERS_TTL = 3600  # 1h cache for price results


class FlightOffer(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    airline: str  # IATA carrier code e.g. "BA", "AI"
    price_total: float
    price_currency: str
    cabin: str  # "ECONOMY" | "BUSINESS" | "FIRST"
    duration_outbound: str  # human-readable e.g. "7h 30m"
    duration_return: str | None = None
    stops_outbound: int = 0
    stops_return: int | None = None
    source: str = "duffel"


# ── helpers ───────────────────────────────────────────────────────────────────


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Duffel-Version": _VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _fmt_duration(iso: str) -> str:
    """Convert PT7H30M → '7h 30m'."""
    h = re.search(r"(\d+)H", iso)
    m = re.search(r"(\d+)M", iso)
    parts = []
    if h:
        parts.append(f"{h.group(1)}h")
    if m:
        parts.append(f"{m.group(1)}m")
    return " ".join(parts) if parts else iso


# ── IATA resolution via Duffel airports search ────────────────────────────────


async def resolve_iata(
    city: str,
    api_key: str,
    cache: Any = None,
) -> str | None:
    """Return the primary airport IATA code for a city name."""
    key = f"duffel:iata:{city.lower().replace(' ', '_')}"
    if cache:
        cached = await redis_get_cached(cache, key)
        if cached and isinstance(cached, dict):
            val = cached.get("iata")
            return str(val) if val else None
    try:
        r = await resilient_request(
            "duffel-places",
            "GET",
            _PLACES_URL,
            params={"query": city, "limit": 10},
            headers=_headers(api_key),
            timeout=10.0,
        )
        r.raise_for_status()
        items = r.json().get("data", [])
        # Prefer city-level IATA (e.g. LON, PAR, NYC) — covers all metro airports
        for item in items:
            if item.get("type") == "city":
                iata = item.get("iata_code")
                if iata:
                    if cache:
                        await redis_set_cached(cache, key, {"iata": iata}, ttl=_IATA_TTL)
                    return str(iata)
        # Fall back to first airport result
        for item in items:
            if item.get("type") == "airport":
                iata = item.get("iata_code")
                if iata:
                    if cache:
                        await redis_set_cached(cache, key, {"iata": iata}, ttl=_IATA_TTL)
                    return str(iata)
    except Exception as exc:
        logger.warning("duffel_iata_resolve_error", city=city, error=str(exc))
    return None


# ── offer parsing ─────────────────────────────────────────────────────────────


def _parse_offer(raw: dict[str, Any], origin: str, destination: str) -> FlightOffer | None:
    try:
        price_total = float(raw["total_amount"])
        price_currency = raw.get("total_currency", "USD")
        slices = raw.get("slices", [])
        if not slices:
            return None

        out_slice = slices[0]
        out_segments = out_slice.get("segments", [])
        if not out_segments:
            return None

        airline = out_segments[0].get("marketing_carrier", {}).get("iata_code", "?")
        dur_out = _fmt_duration(out_slice.get("duration", "PT0H"))
        stops_out = len(out_segments) - 1
        dep_date = out_segments[0].get("departing_at", "")[:10]

        cabin = raw.get("cabin_class", "economy").upper()

        dur_ret: str | None = None
        stops_ret: int | None = None
        ret_date: str | None = None
        if len(slices) > 1:
            ret_slice = slices[1]
            ret_segs = ret_slice.get("segments", [])
            dur_ret = _fmt_duration(ret_slice.get("duration", "PT0H"))
            stops_ret = len(ret_segs) - 1
            if ret_segs:
                ret_date = ret_segs[0].get("departing_at", "")[:10] or None

        return FlightOffer(
            origin=origin,
            destination=destination,
            departure_date=dep_date,
            return_date=ret_date,
            airline=airline,
            price_total=price_total,
            price_currency=price_currency,
            cabin=cabin,
            duration_outbound=dur_out,
            duration_return=dur_ret,
            stops_outbound=stops_out,
            stops_return=stops_ret,
        )
    except Exception as exc:
        logger.debug("duffel_offer_parse_error", error=str(exc))
        return None


# ── flight search ─────────────────────────────────────────────────────────────


async def search_flights(
    origin_iata: str,
    destination_city: str,
    departure_date: date,
    return_date: date | None,
    num_travelers: int = 1,
    currency: str = "USD",
    api_key: str = "",
    cache: Any = None,
    max_results: int = 5,
) -> list[FlightOffer]:
    """
    Search round-trip flight offers via Duffel.
    Returns [] gracefully when api_key is absent or the API errors.
    """
    if not api_key:
        logger.info("duffel_no_api_key")
        return []

    cache_key = (
        f"duffel:flights:{origin_iata}:{destination_city}:"
        f"{departure_date}:{return_date}:{num_travelers}:{currency}"
    )
    if cache:
        cached = await redis_get_cached(cache, cache_key)
        if cached and isinstance(cached, list):
            return [FlightOffer(**o) for o in cached if isinstance(o, dict)]

    dest_iata = await resolve_iata(destination_city, api_key, cache)
    if not dest_iata:
        logger.warning("duffel_no_iata", city=destination_city)
        return []

    slices: list[dict[str, str]] = [
        {
            "origin": origin_iata.upper(),
            "destination": dest_iata,
            "departure_date": departure_date.isoformat(),
        },
    ]
    if return_date:
        slices.append(
            {
                "origin": dest_iata,
                "destination": origin_iata.upper(),
                "departure_date": return_date.isoformat(),
            }
        )

    passengers = [{"type": "adult"} for _ in range(max(1, num_travelers))]

    try:
        r = await resilient_request(
            "duffel-offers",
            "POST",
            _OFFER_REQUESTS_URL,
            params={"return_offers": "true"},
            json={"data": {"slices": slices, "passengers": passengers, "cabin_class": "economy"}},
            headers=_headers(api_key),
            timeout=20.0,
        )
        r.raise_for_status()
        raw_offers: list[dict[str, Any]] = r.json().get("data", {}).get("offers", [])
    except Exception as exc:
        logger.warning("duffel_search_error", error=str(exc))
        return []

    results: list[FlightOffer] = []
    for raw in raw_offers[:max_results]:
        offer = _parse_offer(raw, origin_iata.upper(), dest_iata)
        if offer:
            results.append(offer)

    if results and cache:
        await redis_set_cached(
            cache,
            cache_key,
            [o.model_dump() for o in results],
            ttl=_OFFERS_TTL,
        )

    logger.info("duffel_flights_found", count=len(results), origin=origin_iata, dest=dest_iata)
    return results
