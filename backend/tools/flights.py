"""Flights tool — round-trip prices via the Amadeus Flight Offers API (free sandbox)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel

from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_SANDBOX_BASE = "https://test.api.amadeus.com"
_TOKEN_URL = f"{_SANDBOX_BASE}/v1/security/oauth2/token"
_SEARCH_URL = f"{_SANDBOX_BASE}/v2/shopping/flight-offers"
_LOCATION_URL = f"{_SANDBOX_BASE}/v1/reference-data/locations"

_TOKEN_TTL = 1700  # just under the 30-min token lifetime
_OFFERS_TTL = 3600  # 1-hour cache for price results


class FlightOffer(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    airline: str  # IATA carrier code e.g. "AI", "AF"
    price_total: float
    price_currency: str
    cabin: str  # "ECONOMY" | "BUSINESS" | "FIRST"
    duration_outbound: str  # ISO 8601 e.g. "PT7H30M"
    duration_return: str | None = None
    stops_outbound: int = 0
    stops_return: int | None = None
    source: str = "amadeus"


# ── Amadeus auth ──────────────────────────────────────────────────────────────


async def _get_token(
    client_id: str,
    client_secret: str,
    cache: Any = None,
) -> str | None:
    cache_key = f"amadeus:token:{client_id[:8]}"
    if cache:
        cached = await redis_get_cached(cache, cache_key)
        if cached and isinstance(cached, dict):
            val = cached.get("token")
            return str(val) if val else None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            r.raise_for_status()
            token = r.json().get("access_token")
            if token and cache:
                await redis_set_cached(cache, cache_key, {"token": token}, ttl=_TOKEN_TTL)
            return str(token) if token else None
    except Exception as exc:
        logger.warning("amadeus_token_error", error=str(exc))
        return None


# ── IATA code resolution ──────────────────────────────────────────────────────


async def resolve_iata(
    city: str,
    token: str,
    cache: Any = None,
) -> str | None:
    """Return the primary airport IATA code for a city name. Cached."""
    key = f"amadeus:iata:{city.lower().replace(' ', '_')}"
    if cache:
        cached = await redis_get_cached(cache, key)
        if cached and isinstance(cached, dict):
            val = cached.get("iata")
            return str(val) if val else None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                _LOCATION_URL,
                params={
                    "keyword": city,
                    "subType": "CITY,AIRPORT",
                    "view": "LIGHT",
                    "page[limit]": 5,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            data = r.json().get("data", [])
            # Prefer type=CITY then AIRPORT
            for sub_type in ("CITY", "AIRPORT"):
                for item in data:
                    if item.get("subType") == sub_type:
                        iata = item.get("iataCode")
                        if iata:
                            if cache:
                                await redis_set_cached(cache, key, {"iata": iata}, ttl=86400)
                            return str(iata)
    except Exception as exc:
        logger.warning("amadeus_iata_resolve_error", city=city, error=str(exc))
    return None


# ── ISO 8601 duration helper ──────────────────────────────────────────────────


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


# ── Flight search ─────────────────────────────────────────────────────────────


def _parse_offer(raw: dict, origin: str, destination: str, currency: str) -> FlightOffer | None:  # type: ignore[type-arg]
    try:
        price_total = float(raw["price"]["grandTotal"])
        price_currency = raw["price"].get("currency", currency)
        itineraries = raw.get("itineraries", [])
        if not itineraries:
            return None

        out_it = itineraries[0]
        out_segments = out_it.get("segments", [])
        if not out_segments:
            return None
        airline = out_segments[0].get("carrierCode", "?")
        dur_out = _fmt_duration(out_it.get("duration", "PT0H"))
        stops_out = len(out_segments) - 1

        dur_ret: str | None = None
        stops_ret: int | None = None
        if len(itineraries) > 1:
            ret_it = itineraries[1]
            ret_segs = ret_it.get("segments", [])
            dur_ret = _fmt_duration(ret_it.get("duration", "PT0H"))
            stops_ret = len(ret_segs) - 1

        cabin = "ECONOMY"
        for it in itineraries:
            for seg in it.get("segments", []):
                cabin = seg.get("cabin", cabin)

        dep_date = out_segments[0]["departure"]["at"][:10] if out_segments else ""
        ret_date = ""
        if len(itineraries) > 1:
            ret_segs = itineraries[1].get("segments", [])
            if ret_segs:
                ret_date = ret_segs[0]["departure"]["at"][:10]

        return FlightOffer(
            origin=origin,
            destination=destination,
            departure_date=dep_date,
            return_date=ret_date or None,
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
        logger.debug("amadeus_offer_parse_error", error=str(exc))
        return None


async def search_flights(
    origin_iata: str,
    destination_city: str,
    departure_date: date,
    return_date: date | None,
    num_travelers: int = 1,
    currency: str = "USD",
    client_id: str = "",
    client_secret: str = "",
    cache: Any = None,
    max_results: int = 5,
) -> list[FlightOffer]:
    """
    Search round-trip flight offers via Amadeus.
    Returns [] gracefully when credentials are absent or the API errors.
    """
    if not client_id or not client_secret:
        logger.info("amadeus_no_credentials")
        return []

    cache_key = (
        f"amadeus:flights:{origin_iata}:{destination_city}:"
        f"{departure_date}:{return_date}:{num_travelers}:{currency}"
    )
    if cache:
        cached = await redis_get_cached(cache, cache_key)
        if cached and isinstance(cached, list):
            return [FlightOffer(**o) for o in cached if isinstance(o, dict)]

    token = await _get_token(client_id, client_secret, cache)
    if not token:
        return []

    dest_iata = await resolve_iata(destination_city, token, cache)
    if not dest_iata:
        logger.warning("amadeus_no_iata", city=destination_city)
        return []

    params: dict[str, str | int] = {
        "originLocationCode": origin_iata.upper(),
        "destinationLocationCode": dest_iata,
        "departureDate": departure_date.isoformat(),
        "adults": num_travelers,
        "currencyCode": currency,
        "max": max_results,
    }
    if return_date:
        params["returnDate"] = return_date.isoformat()

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                _SEARCH_URL,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            raw_offers = r.json().get("data", [])
    except Exception as exc:
        logger.warning("amadeus_search_error", error=str(exc))
        return []

    results: list[FlightOffer] = []
    for raw in raw_offers:
        offer = _parse_offer(raw, origin_iata.upper(), dest_iata, currency)
        if offer:
            results.append(offer)

    if results and cache:
        await redis_set_cached(
            cache,
            cache_key,
            [o.model_dump() for o in results],
            ttl=_OFFERS_TTL,
        )

    logger.info("amadeus_flights_found", count=len(results), origin=origin_iata, dest=dest_iata)
    return results
