"""Flights tool — round-trip prices via the Duffel API."""

from __future__ import annotations

import math
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


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


# ── IATA resolution via Duffel airports search ────────────────────────────────


async def resolve_iata(
    city: str,
    api_key: str,
    cache: Any = None,
    near: tuple[float, float] | None = None,
) -> str | None:
    """Return the primary airport IATA code for a city name.

    Duffel's suggestions rank exact IATA-code matches high, so a bare name
    query is a homonym trap: "Goa" returns Genoa, Italy (IATA GOA) and
    "Kochi" returns Kōchi, Japan (KCZ). When ``near`` (the trip's geocoded
    lat/lng) is given, the candidate closest to it wins instead of the first.
    """
    # v2: geographic disambiguation — version the key so ranking changes never
    # keep serving a resolution made by an older algorithm.
    coord_part = f":{near[0]:.1f}:{near[1]:.1f}" if near else ""
    key = f"duffel:iata:v2:{city.lower().replace(' ', '_')}{coord_part}"
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

        iata: str | None = None
        if near is not None:
            # Distance to the trip's real location kills homonyms (Genoa for
            # "Goa" is 6,000 km away). Within 50 km of the nearest candidate,
            # prefer a city-level code (MEL, LON, NYC) over a single airport —
            # metro codes search every airport of the city, so Melbourne must
            # not resolve to Essendon just because it is 3 km closer.
            candidates: list[tuple[float, int, str]] = []
            for item in items:
                code = item.get("iata_code")
                lat, lng = item.get("latitude"), item.get("longitude")
                if not code or lat is None or lng is None:
                    continue
                dist = _haversine_km(near[0], near[1], float(lat), float(lng))
                candidates.append((dist, 0 if item.get("type") == "city" else 1, str(code)))
            if candidates:
                nearest = min(c[0] for c in candidates)
                dist, _, iata = min(
                    (c for c in candidates if c[0] <= nearest + 50.0),
                    key=lambda c: (c[1], c[0]),
                )
                logger.info("duffel_iata_resolved", city=city, iata=iata, km=round(dist, 1))
        if iata is None:
            # No location context — first city-level result, else first airport.
            for wanted in ("city", "airport"):
                for item in items:
                    if item.get("type") == wanted and item.get("iata_code"):
                        iata = str(item["iata_code"])
                        break
                if iata:
                    break

        if iata:
            if cache:
                await redis_set_cached(cache, key, {"iata": iata}, ttl=_IATA_TTL)
            return iata
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
    near: tuple[float, float] | None = None,
) -> list[FlightOffer]:
    """
    Search round-trip flight offers via Duffel.

    ``near`` (the destination's geocoded lat/lng) disambiguates homonym city
    names during IATA resolution — see resolve_iata.
    Returns [] gracefully when api_key is absent or the API errors.
    """
    if not api_key:
        logger.info("duffel_no_api_key")
        return []

    dest_iata = await resolve_iata(destination_city, api_key, cache, near=near)
    if not dest_iata:
        logger.warning("duffel_no_iata", city=destination_city)
        return []

    # Keyed by the RESOLVED airport, not the raw city name — a fixed resolution
    # must never keep serving offers cached under a homonym's airport.
    cache_key = (
        f"duffel:flights:{origin_iata}:{dest_iata}:"
        f"{departure_date}:{return_date}:{num_travelers}:{currency}"
    )
    if cache:
        cached = await redis_get_cached(cache, cache_key)
        if cached and isinstance(cached, list):
            return [FlightOffer(**o) for o in cached if isinstance(o, dict)]

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
