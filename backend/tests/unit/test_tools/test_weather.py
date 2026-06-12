from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.tools.weather import (
    WeatherDay,
    _shift_year_back,
    fetch_weather,
)


def _make_payload(
    codes: list[int] | None = None,
    dates: list[str] | None = None,
) -> dict:
    codes = codes or [0, 63, 95]
    dates = dates or ["2025-06-01", "2025-06-02", "2025-06-03"]
    n = len(dates)
    return {
        "daily": {
            "time": dates,
            "temperature_2m_max": [25.0] * n,
            "temperature_2m_min": [15.0] * n,
            "precipitation_sum": ([0.0, 8.5, 15.2] + [0.0] * n)[:n],
            "precipitation_probability_max": ([5, 80, 90] + [0] * n)[:n],
            "weathercode": codes,
        }
    }


def _mock_client(payload: dict) -> AsyncMock:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=payload)
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ── happy path (near-future / past dates → forecast path) ─────────────────────


@pytest.mark.asyncio
async def test_fetch_weather_returns_weather_days() -> None:
    with patch("httpx.AsyncClient", return_value=_mock_client(_make_payload())):
        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    assert len(days) == 3
    assert all(isinstance(d, WeatherDay) for d in days)


@pytest.mark.asyncio
async def test_clear_day_not_adverse() -> None:
    payload = _make_payload(codes=[0, 0, 0])
    payload["daily"]["precipitation_probability_max"] = [5, 10, 5]
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    assert all(not d.is_adverse for d in days)


@pytest.mark.asyncio
async def test_thunderstorm_day_is_adverse() -> None:
    payload = _make_payload(codes=[95, 0, 0])
    payload["daily"]["precipitation_probability_max"] = [90, 5, 5]
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    assert days[0].is_adverse is True
    assert days[0].condition_label == "Thunderstorm"


@pytest.mark.asyncio
async def test_high_precip_prob_makes_day_adverse() -> None:
    payload = _make_payload(codes=[2, 0, 0])
    payload["daily"]["precipitation_probability_max"] = [85, 5, 5]
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        days = await fetch_weather(48.85, 2.35, date(2025, 6, 1), date(2025, 6, 3))

    assert days[0].is_adverse is True


# ── failure paths ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_weather_returns_empty_on_http_error() -> None:
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=mock_client):
        days = await fetch_weather(0.0, 0.0, date(2025, 6, 1), date(2025, 6, 3))

    assert days == []


@pytest.mark.asyncio
async def test_fetch_weather_returns_empty_on_empty_payload() -> None:
    payload = {"daily": {"time": []}}
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        days = await fetch_weather(0.0, 0.0, date(2025, 6, 1), date(2025, 6, 1))

    assert days == []


# ── climate-normal routing (far-future dates) ──────────────────────────────────


@pytest.mark.asyncio
async def test_far_future_sets_is_climate_normal() -> None:
    payload = _make_payload(codes=[0, 0, 0], dates=["2029-08-01", "2029-08-02", "2029-08-03"])
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        days = await fetch_weather(48.85, 2.35, date(2030, 8, 1), date(2030, 8, 3))

    assert len(days) == 3
    assert all(d.is_climate_normal for d in days)


@pytest.mark.asyncio
async def test_far_future_dates_restamped_to_trip_dates() -> None:
    payload = _make_payload(codes=[0, 0], dates=["2029-08-01", "2029-08-02"])
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        days = await fetch_weather(48.85, 2.35, date(2030, 8, 1), date(2030, 8, 2))

    assert days[0].date == date(2030, 8, 1)
    assert days[1].date == date(2030, 8, 2)


@pytest.mark.asyncio
async def test_far_future_condition_label_has_typical_prefix() -> None:
    payload = _make_payload(codes=[95, 0], dates=["2029-08-01", "2029-08-02"])
    with patch("httpx.AsyncClient", return_value=_mock_client(payload)):
        days = await fetch_weather(48.85, 2.35, date(2030, 8, 1), date(2030, 8, 2))

    assert days[0].condition_label == "Typical: Thunderstorm"
    assert days[1].condition_label == "Typical: Clear sky"


@pytest.mark.asyncio
async def test_far_future_uses_archive_url() -> None:
    from backend.tools.weather import _OPEN_METEO_ARCHIVE_URL

    payload = _make_payload(codes=[0], dates=["2029-08-01"])
    mock_client = _mock_client(payload)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await fetch_weather(0.0, 0.0, date(2030, 8, 1), date(2030, 8, 1))

    called_url = mock_client.get.call_args[0][0]
    assert called_url == _OPEN_METEO_ARCHIVE_URL


@pytest.mark.asyncio
async def test_near_future_uses_forecast_url() -> None:
    from backend.tools.weather import _OPEN_METEO_FORECAST_URL

    payload = _make_payload()
    mock_client = _mock_client(payload)
    with patch("httpx.AsyncClient", return_value=mock_client):
        await fetch_weather(0.0, 0.0, date(2025, 6, 1), date(2025, 6, 3))

    called_url = mock_client.get.call_args[0][0]
    assert called_url == _OPEN_METEO_FORECAST_URL


# ── mixed range ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mixed_range_returns_combined_days() -> None:
    today = date.today()
    start = today + timedelta(days=5)
    end = today + timedelta(days=20)

    near_day = WeatherDay(
        date=start,
        temp_min_c=10.0,
        temp_max_c=20.0,
        precipitation_mm=0.0,
        precipitation_prob=5,
        condition_code=0,
        condition_label="Clear sky",
        is_adverse=False,
        is_climate_normal=False,
    )
    far_day = WeatherDay(
        date=end,
        temp_min_c=12.0,
        temp_max_c=22.0,
        precipitation_mm=1.0,
        precipitation_prob=30,
        condition_code=2,
        condition_label="Typical: Partly cloudy",
        is_adverse=False,
        is_climate_normal=True,
    )

    with (
        patch("backend.tools.weather._fetch_forecast", AsyncMock(return_value=[near_day])),
        patch("backend.tools.weather._fetch_climate_normals", AsyncMock(return_value=[far_day])),
    ):
        days = await fetch_weather(0.0, 0.0, start, end)

    assert len(days) == 2
    assert days[0].is_climate_normal is False
    assert days[1].is_climate_normal is True


# ── _shift_year_back ───────────────────────────────────────────────────────────


def test_shift_year_back_normal_date() -> None:
    assert _shift_year_back(date(2030, 8, 15)) == date(2029, 8, 15)


def test_shift_year_back_feb29_becomes_feb28() -> None:
    # 2028 is a leap year; 2027 is not
    assert _shift_year_back(date(2028, 2, 29)) == date(2027, 2, 28)
