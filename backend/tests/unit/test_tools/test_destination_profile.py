"""City-archetype tests for destination profiling.

Each archetype mirrors the OSM candidate composition of a real kind of destination:
a Goa-like beach state, a Jaipur-like heritage city, a Manali-like hill station, and
a generic mixed metro. The classifier must key the itinerary toward what each place
is actually famous for.
"""

from backend.tools.destination_profile import DestinationProfile, compute_destination_profile
from backend.tools.places import Attraction


def _attr(name: str, category: str, kinds: str | None = None) -> Attraction:
    ref = f"way/{abs(hash(name)) & 0xFFFFFF}"
    return Attraction(
        osm_id=ref,
        name=name,
        lat=15.5,
        lng=73.8,
        kinds=kinds or category,
        category=category,
        source_ref=ref,
    )


def _pool(**counts: int) -> list[Attraction]:
    out: list[Attraction] = []
    for category, n in counts.items():
        out += [_attr(f"{category.title()} {i}", category) for i in range(n)]
    return out


# ── Goa-like beach destination ────────────────────────────────────────────────


def test_goa_like_pool_classified_as_beach() -> None:
    # Coastal pool: plenty of churches/forts too, but beaches + water sports dominate
    pool = _pool(
        beach=8, water_sport=5, religious=6, heritage_monument=6, museum_gallery=3, nature=2
    )
    profile = compute_destination_profile(pool)
    assert profile.type == "beach"
    assert "beach" in profile.signature_categories
    assert "water_sport" in profile.signature_categories


def test_beach_signature_kept_even_when_churches_dominate() -> None:
    # 60% churches/forts but a real coast — the traveler still came for the sea
    pool = _pool(religious=10, heritage_monument=8, beach=3, water_sport=1, museum_gallery=8)
    profile = compute_destination_profile(pool)
    assert profile.type == "beach"  # (3+1)/30 ≥ 0.10
    assert "beach" in profile.signature_categories


def test_region_scale_beach_by_absolute_count() -> None:
    # A widened state-level pool (Goa at ~60 km): hundreds of inland churches dilute the
    # beach SHARE below threshold, but 2 real beaches in range decide the type.
    pool = _pool(religious=14, heritage_monument=8, museum_gallery=6, beach=2)
    assert compute_destination_profile(pool).type == "heritage"  # share rule alone
    profile = compute_destination_profile(pool, region_scale=True)
    assert profile.type == "beach"
    assert profile.signature_categories[0] == "beach"


def test_region_scale_single_beach_not_enough() -> None:
    pool = _pool(religious=14, heritage_monument=9, museum_gallery=6, beach=1)
    assert compute_destination_profile(pool, region_scale=True).type == "heritage"


def test_region_scale_nature_by_absolute_count() -> None:
    pool = _pool(religious=12, heritage_monument=8, museum_gallery=5, nature=3, adventure=2)
    profile = compute_destination_profile(pool, region_scale=True)
    assert profile.type == "nature"


# ── Jaipur/Delhi-like heritage city ───────────────────────────────────────────


def test_jaipur_like_pool_classified_as_heritage() -> None:
    pool = _pool(heritage_monument=15, religious=6, museum_gallery=5, nature=2, other=2)
    profile = compute_destination_profile(pool)
    assert profile.type == "heritage"
    assert "heritage_monument" in profile.signature_categories


def test_delhi_like_pool_signature_includes_monuments_and_temples() -> None:
    pool = _pool(heritage_monument=10, religious=8, museum_gallery=6, nature=4, other=2)
    profile = compute_destination_profile(pool)
    assert profile.type == "heritage"
    assert "heritage_monument" in profile.signature_categories
    assert "religious" in profile.signature_categories


# ── Manali-like hill station ──────────────────────────────────────────────────


def test_manali_like_pool_classified_as_nature() -> None:
    pool = _pool(nature=12, adventure=5, religious=4, other=3)
    profile = compute_destination_profile(pool)
    assert profile.type == "nature"
    assert "nature" in profile.signature_categories
    assert "adventure" in profile.signature_categories


# ── Mixed metro / degenerate cases ────────────────────────────────────────────


def test_mixed_metro_pool_classified_as_mixed() -> None:
    # No single character dominates: heritage share < 0.55, no coast, little nature
    pool = _pool(museum_gallery=8, heritage_monument=6, religious=2, entertainment=5, other=9)
    profile = compute_destination_profile(pool)
    assert profile.type == "mixed"


def test_empty_pool_returns_neutral_profile() -> None:
    profile = compute_destination_profile([])
    assert profile == DestinationProfile()
    assert profile.type == "mixed"
    assert profile.signature_categories == []


def test_signature_excludes_other_and_caps_length() -> None:
    pool = _pool(other=10, beach=5, water_sport=5, nature=5, religious=5, heritage_monument=5)
    profile = compute_destination_profile(pool)
    assert "other" not in profile.signature_categories
    assert len(profile.signature_categories) <= 6  # 4 by share + forced beach/water extras
