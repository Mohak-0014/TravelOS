from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.tools.hotels import _fetch_rates


def _mock_post_client(payload: dict, status: int = 200) -> AsyncMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = ""
    resp.json = MagicMock(return_value=payload)
    client = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


_RATES_PAYLOAD = {
    "data": [
        {
            "hotelId": "lp1",
            "roomTypes": [
                {"rates": [{"retailRate": {"total": [{"amount": 900.0, "currency": "USD"}]}}]},
                {"rates": [{"retailRate": {"total": [{"amount": 600.0, "currency": "USD"}]}}]},
            ],
        },
        {"hotelId": "lp2", "roomTypes": []},  # no rates → omitted from result
    ]
}


@pytest.mark.asyncio
async def test_fetch_rates_parses_cheapest_total_from_room_types() -> None:
    client = _mock_post_client(_RATES_PAYLOAD)
    with (
        patch("backend.tools.hotels.settings") as mock_settings,
        patch("httpx.AsyncClient", return_value=client),
    ):
        mock_settings.LITEAPI_KEY = "key"
        rates = await _fetch_rates(["lp1", "lp2"], date(2026, 9, 15), date(2026, 9, 18), 2)

    # 3 nights; cheapest lp1 total is 600 → 200/night. lp2 has no rates → absent.
    assert rates == {"lp1": (200.0, 600.0, "USD")}


@pytest.mark.asyncio
async def test_fetch_rates_posts_required_json_body() -> None:
    client = _mock_post_client({"data": []})
    with (
        patch("backend.tools.hotels.settings") as mock_settings,
        patch("httpx.AsyncClient", return_value=client),
    ):
        mock_settings.LITEAPI_KEY = "key"
        await _fetch_rates(["lp1"], date(2026, 9, 15), date(2026, 9, 18), 2, currency="INR")

    # Must be a POST with the body the API requires (occupancies + guestNationality),
    # not the old GET with flat `adults` query params; currency is threaded through.
    client.post.assert_awaited_once()
    body = client.post.call_args.kwargs["json"]
    assert body["hotelIds"] == ["lp1"]
    assert body["occupancies"] == [{"adults": 2}]
    assert body["guestNationality"] == "IN"
    assert body["currency"] == "INR"
    assert body["checkin"] == "2026-09-15"
    assert body["checkout"] == "2026-09-18"


@pytest.mark.asyncio
async def test_fetch_rates_returns_empty_without_key() -> None:
    with patch("backend.tools.hotels.settings") as mock_settings:
        mock_settings.LITEAPI_KEY = ""
        assert await _fetch_rates(["lp1"], date(2026, 9, 15), date(2026, 9, 18), 2) == {}
