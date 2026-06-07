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

# Foursquare category 13065 = Restaurants (general)
_DEFAULT_CATEGORIES = "13065"


class Restaurant(BaseModel):
    fsq_id: str
    name: str
    lat: float
    lng: float
    categories: list[str]
    price_level: int | None  # 1-4
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
    Find restaurants near a point using Foursquare Places API v3.
    Returns [] when key is missing or on any failure — never raises.
    Cache TTL: 3 hours.
    """
    if not settings.FOURSQUARE_API_KEY:
        logger.warning("foursquare_key_missing")
        return []

    key = _cache_key(lat, lng, radius_m, categories)
    cached = await redis_get_cached(cache, key)
    if cached:
        logger.info("restaurants_cache_hit", lat=lat, lng=lng)
        return [Restaurant(**r) for r in cached]

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

    if results:
        await redis_set_cached(cache, key, [r.model_dump() for r in results], _CACHE_TTL)

    logger.info("restaurants_search_ok", lat=lat, lng=lng, count=len(results))
    return results
