import bisect
import hashlib

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_CACHE_TTL = 60 * 60 * 6  # 6 hours
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_USER_AGENT = "TravelOS/1.0 rj.mohaknahata@gmail.com"

# OSM tag filters for interesting tourist places
_TOURISM_TAGS = "attraction|museum|gallery|viewpoint|artwork|zoo|theme_park|aquarium"
_HISTORIC_TAGS = "monument|memorial|ruins|castle|archaeological_site"

# Candidate caps fetched from Overpass *before* client-side ranking. The key trap in a
# dense city: Overpass emits ALL matching nodes before any way/relation, and a metro can
# have 1000s of Wikidata-tagged *nodes* (statues, plaques, fountains). A single combined
# cap is therefore exhausted by nodes before reaching the landmark ways/relations — the
# Eiffel Tower, the Louvre and Notre-Dame are all ways/relations. So we fetch landmark
# AREAS (way/relation) in their own block with a generous cap and cap point sights
# (nodes) separately; the client-side composite score then orders everything by fame.
_AREA_CAP = 1200  # Wikidata-tagged ways + relations (where the big sights live)
_POINT_CAP = 250  # Wikidata-tagged nodes (the dense, mostly-minor point features)
_GENERAL_CAP = 150  # non-Wikidata fill

# Separate out-blocks per geometry so a flood of Wikidata-tagged nodes can't starve the
# landmark ways/relations. `place_of_worship` is included (Lotus Temple, Jama Masjid),
# Wikidata-gated so it stays to notable ones, not every neighbourhood shrine.
_OVERPASS_QUERY = """
[out:json][timeout:25];
(
  way["tourism"~"^({tourism})$"]["wikidata"](around:{radius},{lat},{lng});
  relation["tourism"~"^({tourism})$"]["wikidata"](around:{radius},{lat},{lng});
  way["historic"~"^({historic})$"]["wikidata"](around:{radius},{lat},{lng});
  relation["historic"~"^({historic})$"]["wikidata"](around:{radius},{lat},{lng});
  way["amenity"="place_of_worship"]["wikidata"](around:{radius},{lat},{lng});
  relation["amenity"="place_of_worship"]["wikidata"](around:{radius},{lat},{lng});
)->.areas;
.areas out center {area_cap};
(
  node["tourism"~"^({tourism})$"]["wikidata"](around:{radius},{lat},{lng});
  node["historic"~"^({historic})$"]["wikidata"](around:{radius},{lat},{lng});
  node["amenity"="place_of_worship"]["wikidata"](around:{radius},{lat},{lng});
)->.points;
.points out center {point_cap};
(
  nwr["tourism"~"^({tourism})$"](around:{radius},{lat},{lng});
  nwr["historic"~"^({historic})$"](around:{radius},{lat},{lng});
)->.general;
.general out center {general_cap};
""".strip()


# ── Composite prominence weights ──────────────────────────────────────────────
# A single Wikidata proxy (sitelink count) ranks *encyclopedic notability of the
# subject*, not *visit-appeal of the place* — so it over-ranks memorials/graves of
# famous people, event sites and civic buildings (in every city, not just one), and
# is fragile to over-broad OSM `wikidata` tags. We blend independent signals so no
# one source dominates: sitelinks are RANK-normalised within the candidate pool (an
# inflated/mistagged value can only ever reach #1, not crush the field by magnitude),
# and the OSM tag signals are independent of Wikidata, correcting borrowed-fame bias
# — a famous person's memorial that isn't a tourist draw carries no tourism/heritage tag.
_W_SITELINKS = 0.40  # multilingual notability (rank-normalised)
_W_TOURISM = 0.35  # OSM tourism=* — curated tourist intent
_W_HERITAGE = 0.18  # heritage / UNESCO World Heritage designation
_W_WIKIVOYAGE = 0.07  # has a Wikivoyage (travel-guide) article


class Attraction(BaseModel):
    osm_id: str  # e.g. "node/12345678" or "way/87654321"
    name: str
    lat: float
    lng: float
    kinds: str  # derived from OSM tag value (tourism=museum → "museum")
    description: str | None = None
    website: str | None = None
    opening_hours: str | None = None  # raw OSM opening_hours tag when present
    is_major: bool = False  # has a Wikidata/Wikipedia tag → a notable, well-known sight
    wikidata_id: str | None = None  # OSM `wikidata` tag, e.g. "Q243" — used for fame lookup
    is_tourism: bool = False  # has any OSM tourism=* tag (curated tourist intent)
    is_heritage: bool = False  # heritage / UNESCO World Heritage designation
    has_wikivoyage: bool = False  # has a Wikivoyage article (set after Wikidata fetch)
    prominence: int = 0  # Wikidata sitelink count (notability floor; set after fetch)
    score: float = 0.0  # composite prominence used for ranking (set after fetch)
    source_provider: str = "overpass"
    source_ref: str  # same as osm_id


def _cache_key(lat: float, lng: float, radius_m: int, limit: int) -> str:
    raw = f"{lat:.3f}|{lng:.3f}|{radius_m}|{limit}"
    return f"places:{hashlib.sha256(raw.encode()).hexdigest()}"


def _element_to_attraction(el: dict) -> Attraction | None:
    tags = el.get("tags", {})
    # Prefer the English / international OSM name so titles are readable for an
    # English-speaking user; fall back to the local-language name only if neither
    # exists. (OSM stores English names under name:en / int_name.)
    name = tags.get("name:en") or tags.get("int_name") or tags.get("name")
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

    # Notability signal: OSM links famous places to a Wikidata/Wikipedia entry.
    # Presence of either is a reliable "well-known sight" marker — and it's grounded
    # (a real tag), not an inferred score. The Wikidata id also enables fame ranking.
    wikidata_id = tags.get("wikidata")
    is_major = bool(wikidata_id or tags.get("wikipedia") or tags.get("wikipedia:en"))
    # Independent-of-Wikidata tourist-intent signals (robust to bad/over-broad wikidata).
    is_tourism = bool(tags.get("tourism"))
    is_heritage = bool(
        tags.get("heritage")
        or tags.get("heritage:operator")
        or any(k.startswith("whc:") for k in tags)
    )

    return Attraction(
        osm_id=osm_id,
        name=name,
        lat=float(lat),
        lng=float(lng),
        kinds=kinds,
        description=tags.get("description"),
        website=tags.get("website") or tags.get("contact:website"),
        opening_hours=tags.get("opening_hours"),
        is_major=is_major,
        wikidata_id=wikidata_id,
        is_tourism=is_tourism,
        is_heritage=is_heritage,
        source_ref=osm_id,
    )


async def _fetch_prominence(wikidata_ids: list[str | None]) -> dict[str, tuple[int, bool]]:
    """Map Wikidata QID → (sitelink count, has-Wikivoyage). Returns {} on any failure.

    Sitelink count — the number of Wikipedia language editions and sister projects
    linking to an entity — is a notability proxy (world landmarks have 50–150, an
    obscure local site 1–3). A Wikivoyage sitelink additionally flags travel-guide
    coverage. Both feed the composite prominence score.
    """
    qids = list(dict.fromkeys(q.split(";")[0].strip() for q in wikidata_ids if q))
    if not qids:
        return {}
    out: dict[str, tuple[int, bool]] = {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for i in range(0, len(qids), 50):
                batch = qids[i : i + 50]
                resp = await client.get(
                    _WIKIDATA_API,
                    params={
                        "action": "wbgetentities",
                        "ids": "|".join(batch),
                        "props": "sitelinks",
                        "format": "json",
                    },
                    headers={"User-Agent": _USER_AGENT},
                )
                resp.raise_for_status()
                entities = resp.json().get("entities", {})
                for qid, ent in entities.items():
                    links = ent.get("sitelinks") or {}
                    has_voyage = any("wikivoyage" in str(k) for k in links)
                    out[qid] = (len(links), has_voyage)
    except Exception as exc:
        logger.warning("wikidata_prominence_failed", error=str(exc))
        return {}
    return out


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

    Results are ranked prominent-first (Wikidata-tagged, well-known sights) and then
    by proximity to the search point before truncating to ``limit`` — so the area's
    iconic landmarks are preferred over obscure same-type venues.
    Cache TTL: 6 hours.
    """
    key = _cache_key(lat, lng, radius_m, limit)
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
        area_cap=_AREA_CAP,
        point_cap=_POINT_CAP,
        general_cap=_GENERAL_CAP,
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

    # The two `out` blocks can emit the same element twice — dedupe by osm_id.
    by_id: dict[str, Attraction] = {}
    for element in payload.get("elements", []):
        attraction = _element_to_attraction(element)
        if attraction is not None and attraction.osm_id not in by_id:
            by_id[attraction.osm_id] = attraction

    # Composite prominence: blend independent signals so no single proxy dominates.
    candidates = list(by_id.values())
    info = await _fetch_prominence([a.wikidata_id for a in candidates])
    for a in candidates:
        sitelinks, has_voyage = info.get(a.wikidata_id or "", (0, False))
        a.prominence = sitelinks
        a.has_wikivoyage = has_voyage

    # Rank-normalise sitelinks within the pool, then blend with the OSM tag signals.
    sorted_counts = sorted(a.prominence for a in candidates)
    denom = max(len(sorted_counts) - 1, 1)
    for a in candidates:
        sitelink_rank = bisect.bisect_left(sorted_counts, a.prominence) / denom
        a.score = (
            _W_SITELINKS * sitelink_rank
            + _W_TOURISM * float(a.is_tourism)
            + _W_HERITAGE * float(a.is_heritage)
            + _W_WIKIVOYAGE * float(a.has_wikivoyage)
        )

    # Rank: Wikidata-tagged first, then by composite prominence, then nearest; truncate.
    attractions = sorted(
        candidates,
        key=lambda a: (not a.is_major, -a.score, (a.lat - lat) ** 2 + (a.lng - lng) ** 2),
    )[:limit]

    if attractions:
        await redis_set_cached(cache, key, [a.model_dump() for a in attractions], _CACHE_TTL)

    logger.info(
        "places_search_ok",
        lat=lat,
        lng=lng,
        count=len(attractions),
        major=sum(1 for a in attractions if a.is_major),
        top=attractions[0].name if attractions else None,
        top_score=round(attractions[0].score, 3) if attractions else 0,
    )
    return attractions
