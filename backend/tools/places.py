import hashlib

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_CACHE_TTL = 60 * 60 * 6  # 6 hours
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_USER_AGENT = "TravelOS/1.0 rj.mohaknahata@gmail.com"

# OSM tag filters for interesting tourist places
_TOURISM_TAGS = "attraction|museum|gallery|viewpoint|artwork|zoo|theme_park|aquarium"
_HISTORIC_TAGS = "monument|memorial|ruins|castle|archaeological_site"

_OVERPASS_QUERY = """
[out:json][timeout:25];
(
  node["tourism"~"^({tourism})$"](around:{radius},{lat},{lng});
  way["tourism"~"^({tourism})$"](around:{radius},{lat},{lng});
  node["historic"~"^({historic})$"](around:{radius},{lat},{lng});
  way["historic"~"^({historic})$"](around:{radius},{lat},{lng});
);
out center {limit};
""".strip()


class Attraction(BaseModel):
    osm_id: str  # e.g. "node/12345678" or "way/87654321"
    name: str
    lat: float
    lng: float
    kinds: str  # derived from OSM tag value (tourism=museum → "museum")
    description: str | None = None
    website: str | None = None
    source_provider: str = "overpass"
    source_ref: str  # same as osm_id


def _cache_key(lat: float, lng: float, radius_m: int) -> str:
    raw = f"{lat:.3f}|{lng:.3f}|{radius_m}"
    return f"places:{hashlib.sha256(raw.encode()).hexdigest()}"


def _element_to_attraction(el: dict) -> Attraction | None:
    tags = el.get("tags", {})
    name = tags.get("name") or tags.get("name:en")
    if not name:
        return None

    el_type = el.get("type", "node")
    el_id = el.get("id", 0)
    osm_id = f"{el_type}/{el_id}"

    # Coordinates: nodes have lat/lon directly; ways expose a center object
    if el_type == "node":
        lat = el.get("lat")
        lng = el.get("lon")
    else:
        center = el.get("center", {})
        lat = center.get("lat")
        lng = center.get("lon")

    if lat is None or lng is None:
        return None

    # Derive category label from most specific tag
    kinds = (
        tags.get("tourism") or tags.get("historic") or tags.get("amenity") or "place_of_interest"
    )

    return Attraction(
        osm_id=osm_id,
        name=name,
        lat=float(lat),
        lng=float(lng),
        kinds=kinds,
        description=tags.get("description"),
        website=tags.get("website") or tags.get("contact:website"),
        source_ref=osm_id,
    )


async def search_attractions(
    lat: float,
    lng: float,
    radius_m: int = 5000,
    limit: int = 20,
    cache: Redis | None = None,  # type: ignore[type-arg]
) -> list[Attraction]:
    """
    Find attractions near a point using the Overpass API (OpenStreetMap).
    No API key required. Returns [] on any failure — never raises.
    Cache TTL: 6 hours.
    """
    key = _cache_key(lat, lng, radius_m)
    cached = await redis_get_cached(cache, key)
    if cached:
        logger.info("places_cache_hit", lat=lat, lng=lng)
        return [Attraction(**a) for a in cached]

    query = _OVERPASS_QUERY.format(
        tourism=_TOURISM_TAGS,
        historic=_HISTORIC_TAGS,
        radius=radius_m,
        lat=lat,
        lng=lng,
        limit=limit,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _OVERPASS_URL,
                data={"data": query},
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.warning("overpass_query_failed", lat=lat, lng=lng, error=str(exc))
        return []

    attractions: list[Attraction] = []
    for element in payload.get("elements", []):
        attraction = _element_to_attraction(element)
        if attraction:
            attractions.append(attraction)
        if len(attractions) >= limit:
            break

    if attractions:
        await redis_set_cached(cache, key, [a.model_dump() for a in attractions], _CACHE_TTL)

    logger.info("places_search_ok", lat=lat, lng=lng, count=len(attractions))
    return attractions
