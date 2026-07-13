from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.tools.places import (
    Attraction,
    _element_to_attraction,
    _fetch_prominence,
    search_attractions,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _node(osm_id: int = 111, name: str = "Louvre Museum", tag: str = "museum") -> dict:
    return {
        "type": "node",
        "id": osm_id,
        "lat": 48.8606,
        "lon": 2.3376,
        "tags": {"name": name, "tourism": tag},
    }


def _way(osm_id: int = 222, name: str = "Eiffel Tower", tag: str = "attraction") -> dict:
    return {
        "type": "way",
        "id": osm_id,
        "center": {"lat": 48.8584, "lon": 2.2945},
        "tags": {"name": name, "tourism": tag},
    }


def _overpass_payload(elements: list[dict]) -> dict:
    return {"elements": elements}


def _mock_client(payload: dict):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=payload)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ── _element_to_attraction unit tests ────────────────────────────────────────


def test_node_element_parsed_correctly() -> None:
    result = _element_to_attraction(_node())
    assert result is not None
    assert result.name == "Louvre Museum"
    assert result.osm_id == "node/111"
    assert result.lat == 48.8606
    assert result.lng == 2.3376
    assert result.kinds == "museum"
    assert result.source_provider == "overpass"
    assert result.source_ref == "node/111"


def test_way_element_uses_center_coordinates() -> None:
    result = _element_to_attraction(_way())
    assert result is not None
    assert result.lat == 48.8584
    assert result.lng == 2.2945
    assert result.osm_id == "way/222"


def test_element_without_name_returns_none() -> None:
    el = {"type": "node", "id": 999, "lat": 0.0, "lon": 0.0, "tags": {"tourism": "museum"}}
    assert _element_to_attraction(el) is None


def test_element_without_coordinates_returns_none() -> None:
    el = {"type": "node", "id": 999, "tags": {"name": "Ghost Place", "tourism": "museum"}}
    assert _element_to_attraction(el) is None


def test_historic_tag_used_when_tourism_absent() -> None:
    el = {
        "type": "node",
        "id": 1,
        "lat": 48.0,
        "lon": 2.0,
        "tags": {"name": "Roman Ruins", "historic": "ruins"},
    }
    result = _element_to_attraction(el)
    assert result is not None
    assert result.kinds == "ruins"


def test_website_tag_extracted() -> None:
    el = {
        "type": "node",
        "id": 1,
        "lat": 48.0,
        "lon": 2.0,
        "tags": {"name": "Museum", "tourism": "museum", "website": "https://example.com"},
    }
    result = _element_to_attraction(el)
    assert result is not None
    assert result.website == "https://example.com"


def test_wikidata_tag_marks_attraction_major() -> None:
    el = {
        "type": "node",
        "id": 1,
        "lat": 48.0,
        "lon": 2.0,
        "tags": {"name": "Eiffel Tower", "tourism": "attraction", "wikidata": "Q243"},
    }
    result = _element_to_attraction(el)
    assert result is not None
    assert result.is_major is True


def test_wikipedia_tag_marks_attraction_major() -> None:
    el = {
        "type": "node",
        "id": 1,
        "lat": 48.0,
        "lon": 2.0,
        "tags": {"name": "Louvre", "tourism": "museum", "wikipedia": "en:Louvre"},
    }
    result = _element_to_attraction(el)
    assert result is not None
    assert result.is_major is True


def test_attraction_without_wiki_tags_not_major() -> None:
    result = _element_to_attraction(_node())
    assert result is not None
    assert result.is_major is False


# ── search_attractions integration (mocked HTTP) ─────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_attractions_from_overpass() -> None:
    payload = _overpass_payload([_node(), _way()])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 2
    assert all(isinstance(r, Attraction) for r in results)


@pytest.mark.asyncio
async def test_search_returns_cached_value() -> None:
    cached_data = [_node()]
    cached_attractions = [_element_to_attraction(cached_data[0]).model_dump()]

    with patch("backend.tools.places.redis_get_cached", return_value=cached_attractions):
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 1
    assert results[0].name == "Louvre Museum"


@pytest.mark.asyncio
async def test_search_writes_results_to_cache() -> None:
    set_mock = AsyncMock()
    payload = _overpass_payload([_node()])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", set_mock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        await search_attractions(48.85, 2.35, cache=None)

    set_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error() -> None:
    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.asyncio.sleep", new=AsyncMock()),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        results = await search_attractions(0.0, 0.0, cache=None)

    assert results == []


@pytest.mark.asyncio
async def test_search_retries_once_after_transient_overpass_failure() -> None:
    # Public Overpass 504s routinely; a single transient failure must not degrade the
    # trip — the second attempt's payload is used.
    ok_resp = MagicMock()
    ok_resp.raise_for_status = MagicMock()
    ok_resp.json = MagicMock(return_value=_overpass_payload([_node()]))

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[httpx.ConnectError("504-ish flake"), ok_resp])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("backend.tools.places.asyncio.sleep", new=AsyncMock()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 1
    assert mock_client.post.await_count == 2


@pytest.mark.asyncio
async def test_search_skips_unnamed_elements() -> None:
    unnamed = {"type": "node", "id": 1, "lat": 48.0, "lon": 2.0, "tags": {"tourism": "museum"}}
    payload = _overpass_payload([unnamed, _node(osm_id=2, name="Named Place")])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 1
    assert results[0].name == "Named Place"


@pytest.mark.asyncio
async def test_search_respects_limit() -> None:
    elements = [_node(osm_id=i, name=f"Place {i}") for i in range(30)]
    payload = _overpass_payload(elements)

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, limit=10, cache=None)

    assert len(results) == 10


@pytest.mark.asyncio
async def test_search_ranks_major_before_nearer_minor() -> None:
    # Minor venue is closer to the search point; major (Wikidata-tagged) is farther.
    minor = {
        "type": "node",
        "id": 1,
        "lat": 48.851,
        "lon": 2.351,
        "tags": {"name": "Minor Spot", "tourism": "attraction"},
    }
    major = {
        "type": "node",
        "id": 2,
        "lat": 48.870,
        "lon": 2.370,
        "tags": {"name": "Famous Landmark", "tourism": "attraction", "wikidata": "Q1"},
    }
    payload = _overpass_payload([minor, major])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    # Prominent sight ranks first despite being farther away.
    assert [r.name for r in results] == ["Famous Landmark", "Minor Spot"]
    assert results[0].is_major is True


@pytest.mark.asyncio
async def test_search_dedupes_repeated_elements() -> None:
    # The prominent + general `out` blocks can emit the same element twice.
    el = _node(osm_id=7, name="Twice Place")
    payload = _overpass_payload([el, el])

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    assert len(results) == 1
    assert results[0].name == "Twice Place"


# ── fame-scoring (Wikidata sitelinks) ─────────────────────────────────────────


def test_wikidata_id_captured() -> None:
    el = {
        "type": "node",
        "id": 1,
        "lat": 48.0,
        "lon": 2.0,
        "tags": {"name": "X", "tourism": "attraction", "wikidata": "Q243"},
    }
    a = _element_to_attraction(el)
    assert a is not None
    assert a.wikidata_id == "Q243"


@pytest.mark.asyncio
async def test_fetch_prominence_counts_sitelinks_and_wikivoyage() -> None:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(
        return_value={
            "entities": {
                "Q243": {"sitelinks": {"enwiki": {}, "frwiki": {}, "enwikivoyage": {}}},
                "Q1": {"sitelinks": {"enwiki": {}}},
            }
        }
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=client):
        info = await _fetch_prominence(["Q243", "Q1", None])
    # (sitelink_count, has_wikivoyage) — Q243 has an enwikivoyage article.
    assert info == {"Q243": (3, True), "Q1": (1, False)}


@pytest.mark.asyncio
async def test_fetch_prominence_empty_input() -> None:
    assert await _fetch_prominence([]) == {}
    assert await _fetch_prominence([None]) == {}


@pytest.mark.asyncio
async def test_search_ranks_by_fame_over_distance() -> None:
    # Near minor (closer) vs far famous (more sitelinks) — fame must win over distance.
    near = {
        "type": "node",
        "id": 1,
        "lat": 48.851,
        "lon": 2.351,
        "tags": {"name": "Near Minor", "tourism": "attraction", "wikidata": "Q1"},
    }
    far = {
        "type": "node",
        "id": 2,
        "lat": 48.885,
        "lon": 2.385,
        "tags": {"name": "Far Famous", "tourism": "attraction", "wikidata": "Q243"},
    }
    payload = _overpass_payload([near, far])
    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch(
            "backend.tools.places._fetch_prominence",
            new=AsyncMock(return_value={"Q1": (2, False), "Q243": (90, False)}),
        ),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    assert [r.name for r in results] == ["Far Famous", "Near Minor"]
    assert results[0].prominence == 90


def test_tourism_and_heritage_tags_parsed() -> None:
    el = {
        "type": "node",
        "id": 1,
        "lat": 48.0,
        "lon": 2.0,
        "tags": {"name": "X", "historic": "castle", "heritage": "1", "wikidata": "Q1"},
    }
    a = _element_to_attraction(el)
    assert a is not None
    assert a.is_tourism is False  # historic-only, no tourism tag
    assert a.is_heritage is True
    # A tourism tag sets is_tourism.
    b = _element_to_attraction(_node())  # tourism=museum
    assert b is not None
    assert b.is_tourism is True


# ── experience categories ─────────────────────────────────────────────────────


def _tagged(osm_id: int, name: str, tags: dict) -> dict:
    return {
        "type": "node",
        "id": osm_id,
        "lat": 15.55,
        "lon": 73.75,
        "tags": {"name": name, **tags},
    }


def test_beach_categorized_and_kinds_from_natural_tag() -> None:
    a = _element_to_attraction(_tagged(1, "Baga Beach", {"natural": "beach"}))
    assert a is not None
    assert a.category == "beach"
    assert a.kinds == "beach"


def test_surf_school_and_dive_centre_are_water_sport() -> None:
    surf = _element_to_attraction(_tagged(1, "Surf School", {"amenity": "surf_school"}))
    dive = _element_to_attraction(_tagged(2, "Dive Centre", {"amenity": "dive_centre"}))
    scuba = _element_to_attraction(_tagged(3, "Scuba Point", {"sport": "scuba_diving"}))
    assert surf is not None and surf.category == "water_sport"
    assert dive is not None and dive.category == "water_sport"
    assert scuba is not None and scuba.category == "water_sport"


def test_peak_waterfall_and_reserve_are_nature() -> None:
    peak = _element_to_attraction(_tagged(1, "Hilltop", {"natural": "peak"}))
    falls = _element_to_attraction(_tagged(2, "Dudhsagar Falls", {"waterway": "waterfall"}))
    reserve = _element_to_attraction(_tagged(3, "Reserve", {"leisure": "nature_reserve"}))
    assert peak is not None and peak.category == "nature"
    assert falls is not None and falls.category == "nature"
    assert reserve is not None and reserve.category == "nature"


def test_monument_with_tourism_tag_is_heritage_not_other() -> None:
    # India Gate pattern: historic=memorial + tourism=attraction
    a = _element_to_attraction(
        _tagged(1, "India Gate", {"historic": "memorial", "tourism": "attraction"})
    )
    assert a is not None
    assert a.category == "heritage_monument"


def test_worship_museum_viewpoint_categories() -> None:
    temple = _element_to_attraction(_tagged(1, "Temple", {"amenity": "place_of_worship"}))
    museum = _element_to_attraction(_tagged(2, "Museum", {"tourism": "museum"}))
    view = _element_to_attraction(_tagged(3, "Viewpoint", {"tourism": "viewpoint"}))
    assert temple is not None and temple.category == "religious"
    assert museum is not None and museum.category == "museum_gallery"
    assert view is not None and view.category == "viewpoint"


def test_overpass_query_fetches_natural_features() -> None:
    from backend.tools.places import _OVERPASS_QUERY

    assert '"natural"' in _OVERPASS_QUERY
    assert "nature_reserve" in _OVERPASS_QUERY
    assert "national_park" in _OVERPASS_QUERY


@pytest.mark.asyncio
async def test_search_diversifies_beach_town_results() -> None:
    # Beach-town trap: 40 Wikidata-tagged museums vs 6 beaches + 4 surf schools with no
    # Wikidata tags. Pure fame ranking would return 30 museums; the diverse selection
    # must keep the coast represented.
    museums = [
        _tagged(i, f"Museum {i}", {"tourism": "museum", "wikidata": f"Q{i}"}) for i in range(40)
    ]
    beaches = [_tagged(100 + i, f"Beach {i}", {"natural": "beach"}) for i in range(6)]
    surf = [_tagged(200 + i, f"Surf {i}", {"amenity": "surf_school"}) for i in range(4)]
    payload = _overpass_payload(museums + beaches + surf)
    fame = {f"Q{i}": (50 + i, False) for i in range(40)}

    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch("backend.tools.places._fetch_prominence", new=AsyncMock(return_value=fame)),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(15.55, 73.75, limit=30, cache=None)

    assert len(results) == 30
    categories = [r.category for r in results]
    assert categories.count("beach") >= 4
    assert categories.count("water_sport") >= 2
    # The most famous museum still leads — diversity must not bury true icons.
    assert results[0].name == "Museum 39"


@pytest.mark.asyncio
async def test_search_tourism_tag_beats_higher_sitelinks_without_tourism() -> None:
    # The memorial case, generalised: a non-tourism site with MORE sitelinks (borrowed
    # fame) must NOT outrank a tourism-tagged landmark — the OSM tag, independent of
    # Wikidata, corrects the bias. Holds for any city, not just one.
    memorial = {  # huge sitelinks, but historic-only (no tourist intent)
        "type": "node",
        "id": 1,
        "lat": 48.860,
        "lon": 2.336,
        "tags": {"name": "Famous Person Memorial", "historic": "monument", "wikidata": "Q9"},
    }
    landmark = {  # fewer sitelinks, but a tourist attraction
        "type": "node",
        "id": 2,
        "lat": 48.861,
        "lon": 2.337,
        "tags": {"name": "Iconic Landmark", "tourism": "attraction", "wikidata": "Q5"},
    }
    filler_a = {
        "type": "node",
        "id": 3,
        "lat": 48.862,
        "lon": 2.338,
        "tags": {"name": "Filler A", "historic": "monument", "wikidata": "Q3"},
    }
    filler_b = {
        "type": "node",
        "id": 4,
        "lat": 48.863,
        "lon": 2.339,
        "tags": {"name": "Filler B", "historic": "monument", "wikidata": "Q4"},
    }
    payload = _overpass_payload([memorial, landmark, filler_a, filler_b])
    with (
        patch("backend.tools.places.redis_get_cached", return_value=None),
        patch("backend.tools.places.redis_set_cached", new_callable=AsyncMock),
        patch(
            "backend.tools.places._fetch_prominence",
            new=AsyncMock(
                return_value={
                    "Q9": (200, False),
                    "Q5": (100, False),
                    "Q3": (50, False),
                    "Q4": (10, False),
                }
            ),
        ),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_cls.return_value = _mock_client(payload)
        results = await search_attractions(48.85, 2.35, cache=None)

    assert results[0].name == "Iconic Landmark"


# ── Category-mapping fixes + low-quality gate ─────────────────────────────────


def test_sports_centre_is_not_adventure() -> None:
    # leisure=sports_centre matches every gym and football club — it must not become
    # an "adventure" venue (SC Neuhaus, a football club, made an alpine itinerary).
    a = _element_to_attraction(_tagged(1, "SC Neuhaus", {"leisure": "sports_centre"}))
    assert a is not None
    assert a.category == "other"


def test_heritage_tag_categorizes_as_heritage_monument() -> None:
    # Stone Town is a UNESCO district: heritage=1 on a relation, often no historic tag.
    a = _element_to_attraction(_tagged(2, "Stone Town", {"heritage": "1", "wikidata": "Q212423"}))
    assert a is not None
    assert a.category == "heritage_monument"
    assert a.kinds == "heritage_site"
    assert a.is_heritage is True


def test_low_quality_gate_drops_unsignalled_resort_keeps_real_beach() -> None:
    from backend.tools.places import _is_low_quality

    resort = _element_to_attraction(_tagged(3, "Manolo Beach Resort", {"leisure": "beach_resort"}))
    beach = _element_to_attraction(_tagged(4, "Sunny beach", {"natural": "beach"}))
    assert resort is not None and _is_low_quality(resort) is True
    assert beach is not None and _is_low_quality(beach) is False
    # A resort WITH a quality signal (website) survives — it is at least a real venue
    with_site = _element_to_attraction(
        _tagged(5, "Zuri Zanzibar", {"leisure": "beach_resort", "website": "https://zuri.example"})
    )
    assert with_site is not None and _is_low_quality(with_site) is False


def test_low_quality_gate_drops_generic_activity_markers() -> None:
    from backend.tools.places import _is_low_quality

    spot = _element_to_attraction(_tagged(6, "Paragliding Spot", {"sport": "paragliding"}))
    named = _element_to_attraction(_tagged(7, "Coronet Peak Launch", {"sport": "paragliding"}))
    school = _element_to_attraction(_tagged(8, "Surf Betty's", {"amenity": "surf_school"}))
    assert spot is not None and _is_low_quality(spot) is True
    assert named is not None and _is_low_quality(named) is False  # real proper-noun name
    assert school is not None and _is_low_quality(school) is False  # activity venue, ungated
