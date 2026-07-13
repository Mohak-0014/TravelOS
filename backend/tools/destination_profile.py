"""Destination profiling — classify what a place is famous for from its OSM candidate pool.

The profile is derived from the composition of real Overpass results (no hardcoded city
lists): a place whose pool is rich in beaches/water sports is a beach destination, one
dominated by monuments/temples/museums is a heritage city. The Itinerary Planner uses it
to match the activity mix to the destination — beaches in Goa, forts in Delhi — instead
of defaulting to museums everywhere.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from backend.tools.places import Attraction

# Pool-share thresholds for classifying the destination type. Beach wins first: coastal
# towns also have plenty of churches/forts, but travellers come for the coast.
_BEACH_MIN_SHARE = 0.10  # beach + water_sport
_NATURE_MIN_SHARE = 0.25  # nature + adventure (hill stations, trek bases)
_HERITAGE_MIN_SHARE = 0.55  # heritage_monument + religious + museum_gallery
_SIGNATURE_MIN_SHARE = 0.12  # a category this common defines the destination
_SIGNATURE_MAX = 4

# Absolute-count thresholds used instead of shares when the pool came from a
# region-widened fetch (state/region destinations like "Goa"). A 60 km circle sweeps in
# hundreds of inland churches, diluting the beach SHARE below any sensible threshold —
# but two-plus real named beaches in range of a sparse destination IS the story. Dense
# metros never widen, so a lakeside-beach Berlin can't misclassify through this path.
_BEACH_MIN_COUNT_REGION = 2  # beach + water_sport venues
_NATURE_MIN_COUNT_REGION = 5  # nature + adventure venues


class DestinationProfile(BaseModel):
    type: str = "mixed"  # beach | nature | heritage | mixed
    signature_categories: list[str] = []
    category_shares: dict[str, float] = {}


def compute_destination_profile(
    attractions: list[Attraction], region_scale: bool = False
) -> DestinationProfile:
    """Classify the destination from its attraction pool. Empty pool → neutral "mixed".

    ``region_scale`` marks a pool from a widened (state/region) fetch, where beach and
    nature classification switches from share to absolute count — see the constants.
    """
    if not attractions:
        return DestinationProfile()

    counts = Counter(a.category for a in attractions)
    total = len(attractions)
    shares = {cat: n / total for cat, n in counts.items()}

    beach_share = shares.get("beach", 0.0) + shares.get("water_sport", 0.0)
    beach_count = counts.get("beach", 0) + counts.get("water_sport", 0)
    nature_share = shares.get("nature", 0.0) + shares.get("adventure", 0.0)
    nature_count = counts.get("nature", 0) + counts.get("adventure", 0)
    heritage_share = (
        shares.get("heritage_monument", 0.0)
        + shares.get("religious", 0.0)
        + shares.get("museum_gallery", 0.0)
    )

    is_beach = beach_share >= _BEACH_MIN_SHARE or (
        region_scale and beach_count >= _BEACH_MIN_COUNT_REGION
    )
    is_nature = nature_share >= _NATURE_MIN_SHARE or (
        region_scale and nature_count >= _NATURE_MIN_COUNT_REGION
    )

    if is_beach:
        dest_type = "beach"
    elif is_nature:
        dest_type = "nature"
    elif heritage_share >= _HERITAGE_MIN_SHARE:
        dest_type = "heritage"
    else:
        dest_type = "mixed"

    signature = [
        cat
        for cat, share in sorted(shares.items(), key=lambda kv: -kv[1])
        if cat != "other" and share >= _SIGNATURE_MIN_SHARE
    ][:_SIGNATURE_MAX]

    # The defining categories of a beach/nature destination are signature even below the
    # generic share threshold — a coastal pool can be 60% churches yet the draw is the
    # sea. They also lead the list so prompts read "famous for: beach, …" not "…, beach".
    core = {"beach": ("beach", "water_sport"), "nature": ("nature", "adventure")}.get(dest_type, ())
    lead = [cat for cat in core if counts.get(cat)]
    signature = lead + [cat for cat in signature if cat not in lead]

    return DestinationProfile(
        type=dest_type, signature_categories=signature, category_shares=shares
    )
