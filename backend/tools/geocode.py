import hashlib
import math

from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached
from backend.tools.resilience import resilient_request

logger = get_logger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days — city coords rarely change
_USER_AGENT = "TravelOS/1.0 rj.mohaknahata@gmail.com"  # required by Nominatim policy


class GeoPoint(BaseModel):
    lat: float
    lng: float
    display_name: str
    # Half-diagonal of the Nominatim bounding box in metres — the place's own extent.
    # A city gives a few km; a state like Goa ~60 km. None for cached pre-bbox entries.
    bbox_radius_m: float | None = None
    # From Nominatim addressdetails — lets trip creation backfill a country the user
    # left blank (hotel/currency/flight lookups all degrade without one).
    country: str | None = None
    country_code: str | None = None  # ISO-3166-1 alpha-2, uppercased


def _bbox_radius_m(bbox: list) -> float | None:  # type: ignore[type-arg]
    """Half-diagonal of a Nominatim boundingbox [south, north, west, east] in metres."""
    try:
        south, north, west, east = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    mid_lat = math.radians((south + north) / 2)
    lat_m = (north - south) * 111_320
    lng_m = (east - west) * 111_320 * math.cos(mid_lat)
    return math.hypot(lat_m, lng_m) / 2


def _cache_key(query: str) -> str:
    # v2: entries carry country/country_code from addressdetails — old cached
    # payloads lack them, so the version bump forces a refetch rather than
    # serving country-less results for another 30 days.
    return f"geo:v2:{hashlib.sha256(query.lower().strip().encode()).hexdigest()}"


async def geocode(query: str, cache: Redis | None = None) -> GeoPoint | None:  # type: ignore[type-arg]
    """
    Resolve a place name to lat/lng using Nominatim (OpenStreetMap).
    Returns None on any failure — callers must handle degraded state.
    Cache TTL: 30 days.
    """
    key = _cache_key(query)

    cached = await redis_get_cached(cache, key)
    if cached:
        logger.info("geocode_cache_hit", query=query)
        return GeoPoint(**cached)

    try:
        resp = await resilient_request(
            "nominatim",
            "GET",
            _NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception as exc:
        logger.warning("geocode_failed", query=query, error=str(exc))
        return None

    if not results:
        logger.warning("geocode_no_results", query=query)
        return None

    first = results[0]
    address = first.get("address") or {}
    country_code = address.get("country_code")
    point = GeoPoint(
        lat=float(first["lat"]),
        lng=float(first["lon"]),
        display_name=first.get("display_name", ""),
        bbox_radius_m=_bbox_radius_m(first.get("boundingbox") or []),
        country=address.get("country"),
        country_code=country_code.upper() if country_code else None,
    )

    await redis_set_cached(cache, key, point.model_dump(), _CACHE_TTL)
    logger.info("geocode_ok", query=query, lat=point.lat, lng=point.lng)
    return point
