import asyncio
import bisect
import hashlib
import re
from collections import Counter

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_CACHE_TTL = 60 * 60 * 6  # 6 hours
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OVERPASS_ATTEMPTS = 2  # public instance 504s routinely — retry once before degrading
_OVERPASS_RETRY_DELAY_S = 3.0
_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_USER_AGENT = "TravelOS/1.0 rj.mohaknahata@gmail.com"

# OSM tag filters for interesting tourist places
_TOURISM_TAGS = "attraction|museum|gallery|viewpoint|artwork|zoo|theme_park|aquarium"
# `district`/`old_town`/`fort`/`palace`/`citadel` matter for heritage quarters that are a
# single OSM area rather than a monument node — Stone Town (Zanzibar) is historic=district
# and matched nothing before.
_HISTORIC_TAGS = (
    "monument|memorial|ruins|castle|archaeological_site"
    "|fort|palace|citadel|district|old_town|city_gate"
)
# Leisure venues: water parks, marinas, beach resorts. `sports_centre` is deliberately
# absent — it matches every gym and football club; genuinely touristic sports venues are
# caught by the sport=* block instead.
_LEISURE_TAGS = "water_park|marina|beach_resort|swimming_area"
# Water/adventure sports — common in coastal/tropical destinations (Bali, Phuket, etc.)
_SPORT_TAGS = (
    "surfing|diving|scuba_diving|snorkeling|swimming|water_skiing|kitesurfing"
    "|windsurfing|rafting|canoeing|kayaking|paragliding|climbing|bungee_jumping"
    "|canyoning|cycling|horse_riding|sailing"
)
# Natural features tourists actually travel for — beaches, peaks, waterfalls, etc.
# These are what make Goa "Goa" or Manali "Manali", and OSM tags them under
# natural=*/waterway=*, which the tourism/historic blocks never match.
_NATURAL_TAGS = "beach|peak|waterfall|hot_spring|cape|dune|cliff|bay|glacier"

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
_ACTIVITY_CAP = 60  # sport/leisure/adventure venues (surf spots, dive centres, etc.)
_NATURE_CAP = 150  # natural features (beaches, peaks, waterfalls, reserves, parks)

# Separate out-blocks per geometry so a flood of Wikidata-tagged nodes can't starve the
# landmark ways/relations. `place_of_worship` is included (Lotus Temple, Jama Masjid),
# Wikidata-gated so it stays to notable ones, not every neighbourhood shrine.
_OVERPASS_QUERY = """
[out:json][timeout:30];
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
  nwr["heritage"~"^(1|2)$"](around:{radius},{lat},{lng});
)->.general;
.general out center {general_cap};
(
  nwr["sport"~"^({sport})$"](around:{radius},{lat},{lng});
  nwr["leisure"~"^({leisure})$"](around:{radius},{lat},{lng});
  nwr["amenity"="dive_centre"](around:{radius},{lat},{lng});
  nwr["amenity"="surf_school"](around:{radius},{lat},{lng});
)->.activities;
.activities out center {activity_cap};
(
  nwr["natural"~"^({natural})$"](around:{radius},{lat},{lng});
  nwr["waterway"="waterfall"](around:{radius},{lat},{lng});
  nwr["leisure"="nature_reserve"](around:{radius},{lat},{lng});
  nwr["leisure"~"^(park|garden)$"]["wikidata"](around:{radius},{lat},{lng});
  relation["boundary"="national_park"](around:{radius},{lat},{lng});
)->.nature;
.nature out center {nature_cap};
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

# A resort is a place to stay, not a sight — rank it below any real beach so it can't
# fill a beach slot (Zanzibar's "Manolo Beach Resort" outranked actual beaches).
_RESORT_PENALTY = 0.15

# Lodging/infrastructure kinds (resorts, marinas) with NO quality signal at all — no
# Wikidata/Wikipedia link, no website, no opening hours — are places to stay or moor,
# not sights. Genuine activity venues (surf schools, dive centres) stay ungated: they
# rarely carry any of these tags yet ARE what a traveler comes for.
_INFRA_KINDS = frozenset({"beach_resort", "marina"})

# ── Experience categories ─────────────────────────────────────────────────────
# Normalized buckets every downstream consumer (destination profiling, travel-DNA
# boosting, per-day quotas) keys on. Kept coarse on purpose: fine-grained OSM values
# stay available in `kinds`.
CATEGORIES = frozenset(
    {
        "beach",
        "water_sport",
        "adventure",
        "nature",
        "viewpoint",
        "museum_gallery",
        "religious",
        "heritage_monument",
        "entertainment",
        "other",
    }
)

_WATER_SPORT_VALUES = frozenset(
    {
        "surfing",
        "diving",
        "scuba_diving",
        "snorkeling",
        "swimming",
        "water_skiing",
        "kitesurfing",
        "windsurfing",
        "rafting",
        "canoeing",
        "kayaking",
        "sailing",
    }
)
_ADVENTURE_VALUES = frozenset(
    {
        "climbing",
        "bungee_jumping",
        "canyoning",
        "paragliding",
        "cycling",
        "horse_riding",
    }
)
_NATURE_VALUES = frozenset(
    {
        "peak",
        "waterfall",
        "hot_spring",
        "cape",
        "dune",
        "cliff",
        "bay",
        "glacier",
    }
)


def _categorize(tags: dict) -> str:  # type: ignore[type-arg]
    """Map raw OSM tags to one normalized experience category.

    Checked most-specific-first: a beach with a leisure tag is still a beach, and a
    monument that is also tourism=attraction (India Gate) is heritage, not "other".
    """
    natural = tags.get("natural", "")
    sport = tags.get("sport", "")
    leisure = tags.get("leisure", "")
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")

    if natural == "beach" or leisure == "beach_resort":
        return "beach"
    if (
        sport in _WATER_SPORT_VALUES
        or leisure in {"water_park", "swimming_area", "marina"}
        or amenity in {"dive_centre", "surf_school"}
    ):
        return "water_sport"
    if sport in _ADVENTURE_VALUES:
        return "adventure"
    if (
        natural in _NATURE_VALUES
        or tags.get("waterway") == "waterfall"
        or leisure in {"nature_reserve", "park", "garden"}
        or tags.get("boundary") == "national_park"
    ):
        return "nature"
    if tourism == "viewpoint":
        return "viewpoint"
    if tourism in {"museum", "gallery"}:
        return "museum_gallery"
    if amenity == "place_of_worship":
        return "religious"
    if tags.get("historic") or tags.get("heritage"):
        return "heritage_monument"
    if tourism in {"zoo", "theme_park", "aquarium"}:
        return "entertainment"
    return "other"


class Attraction(BaseModel):
    osm_id: str  # e.g. "node/12345678" or "way/87654321"
    name: str
    lat: float
    lng: float
    kinds: str  # derived from OSM tag value (tourism=museum → "museum")
    category: str = "other"  # normalized experience bucket (see CATEGORIES)
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
    # v3: heritage-district fetch, sports_centre removal and the man-made quality gate
    # changed the result composition — never serve older cache entries to this pipeline.
    raw = f"v3|{lat:.3f}|{lng:.3f}|{radius_m}|{limit}"
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

    # Derive category label from most specific tag; sport/leisure take priority so
    # "surfing" or "diving" appears in the prompt rather than a generic fallback.
    kinds = (
        tags.get("sport")
        or tags.get("leisure")
        or tags.get("tourism")
        or tags.get("historic")
        or tags.get("natural")
        or tags.get("waterway")
        or tags.get("amenity")
        or ("national_park" if tags.get("boundary") == "national_park" else None)
        or ("heritage_site" if tags.get("heritage") else None)
        or "place_of_interest"
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
        category=_categorize(tags),
        description=tags.get("description"),
        website=tags.get("website") or tags.get("contact:website"),
        opening_hours=tags.get("opening_hours"),
        is_major=is_major,
        wikidata_id=wikidata_id,
        is_tourism=is_tourism,
        is_heritage=is_heritage,
        source_ref=osm_id,
    )


_GENERIC_NAME_WORDS = frozenset({"spot", "point", "area", "site", "place", "zone", "location"})


def _is_low_quality(a: Attraction) -> bool:
    """True for infrastructure / generic activity markers with no tourist signal.

    "No signal" means no Wikidata/Wikipedia link, no website and no opening hours.
    Natural features (beaches, peaks…) and real activity venues are never dropped here
    — they legitimately carry none of those tags.
    """
    has_signal = a.is_major or bool(a.website) or bool(a.opening_hours)
    if has_signal:
        return False
    if a.kinds in _INFRA_KINDS:
        return True
    # Generic activity markers ("Paragliding Spot", "Diving Point") — a mapped launch/
    # entry point, not a venue anyone travels for. Only sport-venue categories, and only
    # when the name contains an explicit marker word, so a quirky-but-real venue name
    # never matches.
    if a.category not in {"water_sport", "adventure"}:
        return False
    name_tokens = {t for t in re.split(r"[^a-z]+", a.name.lower()) if t}
    kind_tokens = {t for t in re.split(r"[^a-z]+", a.kinds.lower()) if t}
    return bool(name_tokens & _GENERIC_NAME_WORDS) and name_tokens <= (
        _GENERIC_NAME_WORDS | kind_tokens
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


# Categories below this pool share get no reserved slots (they still compete globally).
_MIN_QUOTA_SHARE = 0.08


def _select_diverse(ranked: list[Attraction], limit: int) -> list[Attraction]:
    """Truncate to ``limit`` while keeping the pool's category mix.

    Pure top-N by fame starves category types that rarely carry Wikidata tags (beaches,
    water sports) in any city with 30+ tagged museums/monuments. Instead, each category
    holding ≥ _MIN_QUOTA_SHARE of the pool gets slots proportional to its share (filled
    with its best-scored venues); leftover slots go to the globally best remaining.
    """
    if len(ranked) <= limit:
        return ranked

    total = len(ranked)
    counts = Counter(a.category for a in ranked)
    by_cat: dict[str, list[Attraction]] = {}
    for a in ranked:
        by_cat.setdefault(a.category, []).append(a)

    quotas = {
        cat: min(n, max(1, round(n / total * limit)))
        for cat, n in counts.items()
        if cat != "other" and n / total >= _MIN_QUOTA_SHARE
    }

    picked: dict[str, Attraction] = {}
    for cat, quota in sorted(quotas.items(), key=lambda kv: -kv[1]):
        take = min(quota, limit - len(picked))
        for a in by_cat[cat][:take]:
            picked[a.osm_id] = a
        if len(picked) >= limit:
            break
    for a in ranked:
        if len(picked) >= limit:
            break
        picked.setdefault(a.osm_id, a)

    order = {a.osm_id: i for i, a in enumerate(ranked)}
    return sorted(picked.values(), key=lambda a: order[a.osm_id])


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
        sport=_SPORT_TAGS,
        leisure=_LEISURE_TAGS,
        natural=_NATURAL_TAGS,
        radius=radius_m,
        lat=lat,
        lng=lng,
        area_cap=_AREA_CAP,
        point_cap=_POINT_CAP,
        general_cap=_GENERAL_CAP,
        activity_cap=_ACTIVITY_CAP,
        nature_cap=_NATURE_CAP,
    )

    # The public Overpass instance 504s routinely under load — one failure must not
    # silently degrade a trip (a lost wide-radius fetch costs Goa its beaches), so
    # retry once with a short backoff before giving up.
    payload = None
    for attempt in range(_OVERPASS_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    _OVERPASS_URL,
                    data={"data": query},
                    headers={"User-Agent": _USER_AGENT},
                )
                resp.raise_for_status()
                payload = resp.json()
            break
        except Exception as exc:
            logger.warning(
                "overpass_query_failed", lat=lat, lng=lng, attempt=attempt + 1, error=str(exc)
            )
            if attempt + 1 < _OVERPASS_ATTEMPTS:
                await asyncio.sleep(_OVERPASS_RETRY_DELAY_S)
    if payload is None:
        return []

    # The two `out` blocks can emit the same element twice — dedupe by osm_id.
    by_id: dict[str, Attraction] = {}
    for element in payload.get("elements", []):
        attraction = _element_to_attraction(element)
        if (
            attraction is not None
            and attraction.osm_id not in by_id
            and not _is_low_quality(attraction)
        ):
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
        if a.kinds == "beach_resort":
            a.score -= _RESORT_PENALTY

    # Rank by composite prominence (is_major only breaks score ties, so venue types that
    # rarely carry Wikidata tags — beaches, surf schools — aren't hard-sorted below every
    # museum), then diversify: slots are allocated across experience categories in
    # proportion to the pool, so a beach town's list can't be 30 museums.
    ranked = sorted(
        candidates,
        key=lambda a: (-a.score, not a.is_major, (a.lat - lat) ** 2 + (a.lng - lng) ** 2),
    )
    attractions = _select_diverse(ranked, limit)

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
