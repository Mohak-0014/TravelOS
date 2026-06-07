from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from backend.tools.weather import WeatherDay, fetch_weather


def _open_meteo_payload(codes: list[int] | None = None) -> dict:
    codes = codes or [0, 63, 95]
    return {
        "daily": {
            "time": ["2025-06-01", "2025-06-02", "2025-06-03"],
            "temperature_2m_max": [25.0, 18.0, 20.0],
            "temperature_2m_min": [15.0, 12.0, 14.0],
            "precipitation_sum": [0.0, 8.5, 15.2],
            "precipitation_probability_max": [5, 80, 90],
            "weathercode": codes,
        }
    }


# ── happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_weather_returns_weather_days() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=_open_meteo_payload())
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    assert len(days) == 3
    assert all(isinstance(d, WeatherDay) for d in days)


@pytest.mark.asyncio
async def test_clear_day_not_adverse() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        payload = _open_meteo_payload(codes=[0, 0, 0])
        # Set precipitation prob to low
        payload["daily"]["precipitation_probability_max"] = [5, 10, 5]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    assert all(not d.is_adverse for d in days)


@pytest.mark.asyncio
async def test_thunderstorm_day_is_adverse() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        payload = _open_meteo_payload(codes=[95, 0, 0])
        payload["daily"]["precipitation_probability_max"] = [90, 5, 5]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    assert days[0].is_adverse is True
    assert days[0].condition_label == "Thunderstorm"


@pytest.mark.asyncio
async def test_high_precip_prob_makes_day_adverse() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        payload = _open_meteo_payload(codes=[2, 0, 0])  # code 2 = partly cloudy (not adverse)
        payload["daily"]["precipitation_probability_max"] = [85, 5, 5]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=payload)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    # precipitation_prob > 70 makes it adverse even for non-rain code
    assert days[0].is_adverse is True


# ── failure paths ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_weather_returns_empty_on_http_error() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        days = await fetch_weather(0.0, 0.0, date(2025, 6, 1), date(2025, 6, 3))

    assert days == []


@pytest.mark.asyncio
async def test_fetch_weather_returns_empty_on_empty_payload() -> None:
    with patch("httpx.AsyncClient") as mock_cls:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"daily": {"time": []}})
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        days = await fetch_weather(0.0, 0.0, date(2025, 6, 1), date(2025, 6, 1))

    assert days == []
