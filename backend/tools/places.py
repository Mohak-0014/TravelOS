import hashlib

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_CACHE_TTL = 60 * 60 * 6  # 6 hours
_OTM_LIST_URL = "https://api.opentripmap.com/0.1/en/places/radius"
_OTM_DETAIL_URL = "https://api.opentripmap.com/0.1/en/places/xid/{xid}"


class Attraction(BaseModel):
    xid: str
    name: str
    lat: float
    lng: float
    kinds: str
    description: str | None
    image_url: str | None
    source_provider: str = "opentripmap"
    source_ref: str  # same as xid


def _cache_key(lat: float, lng: float, radius_m: int, kinds: str) -> str:
    raw = f"{lat:.3f}|{lng:.3f}|{radius_m}|{kinds}"
    return f"places:{hashlib.sha256(raw.encode()).hexdigest()}"


async def search_attractions(
    lat: float,
    lng: float,
    radius_m: int = 5000,
    kinds: str = "interesting_places",
    cache: Redis | None = None,  # type: ignore[type-arg]
) -> list[Attraction]:
    """
    Find top attractions near a point using OpenTripMap.
    Returns [] when key is missing or on any failure — never raises.
    Cache TTL: 6 hours.
    """
    if not settings.OPENTRIPMAP_API_KEY:
        logger.warning("opentripmap_key_missing")
        return []

    key = _cache_key(lat, lng, radius_m, kinds)
    cached = await redis_get_cached(cache, key)
    if cached:
        logger.info("places_cache_hit", lat=lat, lng=lng)
        return [Attraction(**a) for a in cached]

    # Step 1 — list xids in radius (up to 20)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            list_resp = await client.get(
                _OTM_LIST_URL,
                params={
                    "radius": radius_m,
                    "lon": lng,
                    "lat": lat,
                    "kinds": kinds,
                    "format": "json",
                    "limit": 20,
                    "apikey": settings.OPENTRIPMAP_API_KEY,
                },
            )
            list_resp.raise_for_status()
            items = list_resp.json()
    except Exception as exc:
        logger.warning("opentripmap_list_failed", lat=lat, lng=lng, error=str(exc))
        return []

    # Step 2 — fetch details for each xid (best-effort; skip failures)
    attractions: list[Attraction] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for item in items:
            xid = item.get("xid", "")
            if not xid:
                continue
            try:
                detail_resp = await client.get(
                    _OTM_DETAIL_URL.format(xid=xid),
                    params={"apikey": settings.OPENTRIPMAP_API_KEY},
                )
                detail_resp.raise_for_status()
                d = detail_resp.json()
                name = d.get("name") or item.get("name", "")
                if not name:
                    continue
                point = d.get("point", {})
                attractions.append(
                    Attraction(
                        xid=xid,
                        name=name,
                        lat=point.get("lat", lat),
                        lng=point.get("lon", lng),
                        kinds=d.get("kinds", kinds),
                        description=d.get("wikipedia_extracts", {}).get("text") if d.get("wikipedia_extracts") else None,
                        image_url=d.get("preview", {}).get("source") if d.get("preview") else None,
                        source_ref=xid,
                    )
                )
            except Exception:
                continue

    if attractions:
        await redis_set_cached(cache, key, [a.model_dump() for a in attractions], _CACHE_TTL)

    logger.info("places_search_ok", lat=lat, lng=lng, count=len(attractions))
    return attractions
