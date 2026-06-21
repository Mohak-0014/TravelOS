from backend.tools.restaurants import _is_food_place

# ── _is_food_place — Foursquare category guard ────────────────────────────────


def test_is_food_place_accepts_restaurant() -> None:
    assert _is_food_place(["Indian Restaurant"]) is True


def test_is_food_place_accepts_cafe_and_bar() -> None:
    assert _is_food_place(["Coffee Shop"]) is True
    assert _is_food_place(["Cocktail Bar"]) is True


def test_is_food_place_rejects_non_food_venues() -> None:
    assert _is_food_place(["Monument", "Historic Site"]) is False
    assert _is_food_place(["Auto Dealership"]) is False
    assert _is_food_place(["Museum"]) is False
    assert _is_food_place(["Government Building"]) is False


def test_is_food_place_empty_is_false() -> None:
    assert _is_food_place([]) is False
