from datetime import date

import httpx
from pydantic import BaseModel

from backend.core.logging import get_logger

logger = get_logger(__name__)

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

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


class WeatherDay(BaseModel):
    date: date
    temp_min_c: float
    temp_max_c: float
    precipitation_mm: float
    precipitation_prob: int  # 0-100
    condition_code: int
    condition_label: str
    is_adverse: bool


def _parse_day(
    day_date: str,
    temp_min: float,
    temp_max: float,
    precip: float,
    precip_prob: int,
    code: int,
) -> WeatherDay:
    label, code_adverse = _WMO.get(code, ("Unknown", False))
    is_adverse = code_adverse or precip_prob > 70
    return WeatherDay(
        date=date.fromisoformat(day_date),
        temp_min_c=round(temp_min, 1),
        temp_max_c=round(temp_max, 1),
        precipitation_mm=round(precip, 1),
        precipitation_prob=precip_prob,
        condition_code=code,
        condition_label=label,
        is_adverse=is_adverse,
    )


async def fetch_weather(
    lat: float, lng: float, start_date: date, end_date: date
) -> list[WeatherDay]:
    """
    Fetch daily weather forecast from Open-Meteo (free, no key).
    Returns empty list on any failure — callers handle degraded state.
    Open-Meteo is fast enough that we skip Redis caching here.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _OPEN_METEO_URL,
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "daily": ",".join([
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_sum",
                        "precipitation_probability_max",
                        "weathercode",
                    ]),
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "timezone": "auto",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.warning("weather_fetch_failed", lat=lat, lng=lng, error=str(exc))
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
                )
            )
        except Exception as exc:
            logger.warning("weather_day_parse_failed", date=d, error=str(exc))

    logger.info("weather_fetch_ok", lat=lat, lng=lng, days=len(days))
    return days
