from datetime import date, timedelta

from pydantic import BaseModel

from backend.core.logging import get_logger
from backend.tools.resilience import resilient_request

logger = get_logger(__name__)

_OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo forecast is reliable up to 14 days; beyond that use climate normals
_FORECAST_HORIZON_DAYS = 14

# WMO weather interpretation codes → human-readable label + adverse flag
_WMO: dict[int, tuple[str, bool]] = {
    0: ("Clear sky", False),
    1: ("Mainly clear", False),
    2: ("Partly cloudy", False),
    3: ("Overcast", False),
    45: ("Fog", False),
    48: ("Rime fog", False),
    51: ("Light drizzle", True),
    53: ("Moderate drizzle", True),
    55: ("Dense drizzle", True),
    61: ("Slight rain", True),
    63: ("Moderate rain", True),
    65: ("Heavy rain", True),
    71: ("Slight snow", True),
    73: ("Moderate snow", True),
    75: ("Heavy snow", True),
    77: ("Snow grains", True),
    80: ("Slight showers", True),
    81: ("Moderate showers", True),
    82: ("Violent showers", True),
    85: ("Slight snow showers", True),
    86: ("Heavy snow showers", True),
    95: ("Thunderstorm", True),
    96: ("Thunderstorm + hail", True),
    99: ("Thunderstorm + heavy hail", True),
}

_DAILY_FIELDS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "weathercode",
]


class WeatherDay(BaseModel):
    date: date
    temp_min_c: float
    temp_max_c: float
    precipitation_mm: float
    precipitation_prob: int  # 0-100
    condition_code: int
    condition_label: str
    is_adverse: bool
    is_climate_normal: bool = False  # True when sourced from archive (not a real forecast)


def _shift_year_back(d: date) -> date:
    """Move a date back one year; handles Feb-29 in leap years."""
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        return d.replace(year=d.year - 1, day=28)


def _parse_day(
    day_date: str,
    temp_min: float,
    temp_max: float,
    precip: float,
    precip_prob: int,
    code: int,
    is_climate_normal: bool = False,
) -> WeatherDay:
    label, code_adverse = _WMO.get(code, ("Unknown", False))
    is_adverse = code_adverse or precip_prob > 70
    condition_label = f"Typical: {label}" if is_climate_normal else label
    return WeatherDay(
        date=date.fromisoformat(day_date),
        temp_min_c=round(temp_min, 1),
        temp_max_c=round(temp_max, 1),
        precipitation_mm=round(precip, 1),
        precipitation_prob=precip_prob,
        condition_code=code,
        condition_label=condition_label,
        is_adverse=is_adverse,
        is_climate_normal=is_climate_normal,
    )


async def _fetch_from_url(
    url: str,
    lat: float,
    lng: float,
    start_date: date,
    end_date: date,
    is_climate_normal: bool = False,
) -> list[WeatherDay]:
    """Shared fetch + parse logic for both forecast and archive endpoints."""
    try:
        resp = await resilient_request(
            "open-meteo",
            "GET",
            url,
            params={
                "latitude": lat,
                "longitude": lng,
                "daily": ",".join(_DAILY_FIELDS),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timezone": "auto",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        logger.warning("weather_fetch_failed", url=url, lat=lat, lng=lng, error=str(exc))
        return []

    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    if not dates:
        return []

    days: list[WeatherDay] = []
    for i, d in enumerate(dates):
        try:
            days.append(
                _parse_day(
                    day_date=d,
                    temp_min=daily["temperature_2m_min"][i] or 0.0,
                    temp_max=daily["temperature_2m_max"][i] or 0.0,
                    precip=daily["precipitation_sum"][i] or 0.0,
                    precip_prob=daily["precipitation_probability_max"][i] or 0,
                    code=daily["weathercode"][i] or 0,
                    is_climate_normal=is_climate_normal,
                )
            )
        except Exception as exc:
            logger.warning("weather_day_parse_failed", date=d, error=str(exc))

    logger.info(
        "weather_fetch_ok",
        url=url,
        lat=lat,
        lng=lng,
        days=len(days),
        climate_normal=is_climate_normal,
    )
    return days


async def _fetch_forecast(
    lat: float, lng: float, start_date: date, end_date: date
) -> list[WeatherDay]:
    return await _fetch_from_url(_OPEN_METEO_FORECAST_URL, lat, lng, start_date, end_date)


async def _fetch_climate_normals(
    lat: float, lng: float, start_date: date, end_date: date
) -> list[WeatherDay]:
    """
    Query the Open-Meteo archive for the same calendar window one year prior.
    Returns WeatherDay objects with is_climate_normal=True and condition_label
    prefixed with "Typical: " so callers can surface a disclaimer to the user.
    """
    archive_start = _shift_year_back(start_date)
    archive_end = _shift_year_back(end_date)

    archive_days = await _fetch_from_url(
        _OPEN_METEO_ARCHIVE_URL, lat, lng, archive_start, archive_end, is_climate_normal=True
    )

    # Re-stamp each day with the actual trip date (archive dates are 1 year behind)
    trip_days: list[WeatherDay] = []
    for i, day in enumerate(archive_days):
        trip_date = start_date + timedelta(days=i)
        trip_days.append(day.model_copy(update={"date": trip_date}))

    return trip_days


async def fetch_weather(
    lat: float, lng: float, start_date: date, end_date: date
) -> list[WeatherDay]:
    """
    Fetch daily weather for a date range.

    Routing:
    - All dates within 14 days  → Open-Meteo forecast (precise)
    - All dates beyond 14 days  → Open-Meteo archive 1yr prior (climate normals)
    - Mixed range               → forecast for near portion, normals for far portion

    Returns empty list on any failure — callers handle degraded state.
    """
    today = date.today()
    cutoff = today + timedelta(days=_FORECAST_HORIZON_DAYS)

    if end_date <= cutoff:
        return await _fetch_forecast(lat, lng, start_date, end_date)

    if start_date > cutoff:
        return await _fetch_climate_normals(lat, lng, start_date, end_date)

    # Mixed: forecast up to cutoff, climate normals for the rest
    forecast_days = await _fetch_forecast(lat, lng, start_date, cutoff)
    climate_days = await _fetch_climate_normals(lat, lng, cutoff + timedelta(days=1), end_date)
    return forecast_days + climate_days
