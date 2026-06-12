import hashlib

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_CACHE_TTL = 60 * 60 * 3  # 3 hours
_FSQ_URL = "https://api.foursquare.com/v3/places/search"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "TravelOS/1.0 rj.mohaknahata@gmail.com"

# Foursquare category 13065 = Restaurants (general)
_DEFAULT_CATEGORIES = "13065"

# OSM amenity tags that count as dining options
_OSM_AMENITIES = ["restaurant", "cafe", "fast_food", "bar", "food_court", "pub"]


class Restaurant(BaseModel):
    fsq_id: str  # OSM node ID when sourced from Overpass
    name: str
    lat: float
    lng: float
    categories: list[str]
    price_level: int | None  # 1-4; None when sourced from OSM
    address: str | None
    source_provider: str = "foursquare"
    source_ref: str  # same as fsq_id


def _cache_key(lat: float, lng: float, radius_m: int, categories: str) -> str:
    raw = f"{lat:.3f}|{lng:.3f}|{radius_m}|{categories}"
    return f"restaurants:{hashlib.sha256(raw.encode()).hexdigest()}"


async def search_restaurants(
    lat: float,
    lng: float,
    radius_m: int = 1000,
    categories: str = _DEFAULT_CATEGORIES,
    cache: Redis | None = None,  # type: ignore[type-arg]
) -> list[Restaurant]:
    """
    Find restaurants near a point.
    Primary: Foursquare Places API v3 (when FOURSQUARE_API_KEY is set).
    Fallback: Overpass/OpenStreetMap (free, no key required).
    Returns [] only on hard failure — never raises.
    """
    key = _cache_key(lat, lng, radius_m, categories)
    cached = await redis_get_cached(cache, key)
    if cached:
        logger.info("restaurants_cache_hit", lat=lat, lng=lng)
        return [Restaurant(**r) for r in cached]

    if settings.FOURSQUARE_API_KEY:
        results = await _search_foursquare(lat, lng, radius_m, categories)
        if not results:
            # Foursquare returned nothing (auth failure, rate limit, or empty area) — use OSM
            logger.info("foursquare_empty_falling_back_to_osm", lat=lat, lng=lng)
            results = await _search_overpass(lat, lng, radius_m)
    else:
        logger.info("foursquare_key_missing_using_osm", lat=lat, lng=lng)
        results = await _search_overpass(lat, lng, radius_m)

    if results:
        await redis_set_cached(cache, key, [r.model_dump() for r in results], _CACHE_TTL)

    logger.info("restaurants_search_ok", lat=lat, lng=lng, count=len(results), provider=results[0].source_provider if results else "none")  # noqa: E501
    return results


# ── Foursquare ─────────────────────────────────────────────────────────────────


async def _search_foursquare(
    lat: float, lng: float, radius_m: int, categories: str
) -> list[Restaurant]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _FSQ_URL,
                params={
                    "ll": f"{lat},{lng}",
                    "radius": radius_m,
                    "categories": categories,
                    "limit": 20,
                    "fields": "fsq_id,name,geocodes,categories,price,location",
                },
                headers={"Authorization": settings.FOURSQUARE_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("foursquare_search_failed", lat=lat, lng=lng, error=str(exc))
        return []

    results: list[Restaurant] = []
    for place in data.get("results", []):
        try:
            geo = place.get("geocodes", {}).get("main", {})
            location = place.get("location", {})
            addr_parts = [
                location.get("address"),
                location.get("locality"),
                location.get("country"),
            ]
            address = ", ".join(p for p in addr_parts if p) or None
            results.append(
                Restaurant(
                    fsq_id=place["fsq_id"],
                    name=place.get("name", ""),
                    lat=geo.get("latitude", lat),
                    lng=geo.get("longitude", lng),
                    categories=[c.get("name", "") for c in place.get("categories", [])],
                    price_level=place.get("price"),
                    address=address,
                    source_ref=place["fsq_id"],
                )
            )
        except Exception:
            continue

    return results


# ── Overpass fallback ──────────────────────────────────────────────────────────


async def _search_overpass(lat: float, lng: float, radius_m: int) -> list[Restaurant]:
    amenity_filter = "".join(f'node["amenity"="{a}"](around:{radius_m},{lat},{lng});' for a in _OSM_AMENITIES)
    query = f'[out:json][timeout:15];({amenity_filter});out body 25;'

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("overpass_restaurants_failed", lat=lat, lng=lng, error=str(exc))
        return []

    results: list[Restaurant] = []
    for el in data.get("elements", []):
        try:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")
            if not name:
                continue
            osm_id = str(el["id"])
            amenity = tags.get("amenity", "restaurant")
            addr_parts = [
                tags.get("addr:housenumber", ""),
                tags.get("addr:street", ""),
                tags.get("addr:city", ""),
            ]
            address = " ".join(p for p in addr_parts if p).strip() or None
            results.append(
                Restaurant(
                    fsq_id=osm_id,
                    name=name,
                    lat=el.get("lat", lat),
                    lng=el.get("lon", lng),
                    categories=[amenity.replace("_", " ").title()],
                    price_level=None,
                    address=address,
                    source_provider="openstreetmap",
                    source_ref=osm_id,
                )
            )
        except Exception:
            continue

    return results
