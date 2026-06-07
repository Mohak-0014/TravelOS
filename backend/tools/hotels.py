import hashlib
import json
from datetime import date

import httpx
from pydantic import BaseModel
from redis.asyncio import Redis

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.tools import redis_get_cached, redis_set_cached

logger = get_logger(__name__)

_CACHE_TTL = 60 * 60  # 1 hour
_LITEAPI_HOTELS_URL = "https://api.liteapi.travel/v3.0/data/hotels"
_HOTELSNL_URL = "https://engine.hotellook.com/api/v2/cache.json"


class HotelOffer(BaseModel):
    hotel_id: str
    name: str
    lat: float | None
    lng: float | None
    price_per_night: float | None
    price_total: float | None
    price_currency: str
    star_rating: float | None
    meal_plan: str | None
    refundable: bool | None
    booking_ref: str | None
    image_url: str | None
    source_provider: str  # "liteapi" | "hotelsnl"
    source_ref: str
    raw_payload: dict


def _cache_key(destination: str, check_in: date, check_out: date, guests: int) -> str:
    raw = f"{destination}|{check_in}|{check_out}|{guests}"
    return f"hotels:{hashlib.sha256(raw.encode()).hexdigest()}"


async def _search_liteapi(
    destination: str, check_in: date, check_out: date, guests: int
) -> list[HotelOffer]:
    if not settings.LITEAPI_KEY:
        logger.warning("liteapi_key_missing")
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _LITEAPI_HOTELS_URL,
                params={
                    "cityName": destination,
                    "checkIn": check_in.isoformat(),
                    "checkOut": check_out.isoformat(),
                    "adults": guests,
                    "currency": "USD",
                },
                headers={"X-API-Key": settings.LITEAPI_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("liteapi_search_failed", destination=destination, error=str(exc))
        return []

    offers: list[HotelOffer] = []
    for hotel in data.get("data", [])[:20]:
        try:
            offers.append(
                HotelOffer(
                    hotel_id=str(hotel.get("hotelId", "")),
                    name=hotel.get("name", ""),
                    lat=hotel.get("latitude"),
                    lng=hotel.get("longitude"),
                    price_per_night=hotel.get("minRate"),
                    price_total=None,
                    price_currency=hotel.get("currency", "USD"),
                    star_rating=hotel.get("starRating"),
                    meal_plan=None,
                    refundable=None,
                    booking_ref=None,
                    image_url=hotel.get("mainPhoto"),
                    source_provider="liteapi",
                    source_ref=str(hotel.get("hotelId", "")),
                    raw_payload=hotel,
                )
            )
        except Exception:
            continue

    logger.info("liteapi_search_ok", destination=destination, count=len(offers))
    return offers


async def _search_hotelsnl(
    destination: str, check_in: date, check_out: date, guests: int
) -> list[HotelOffer]:
    if not settings.HOTELSNL_API_KEY:
        logger.warning("hotelsnl_key_missing")
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _HOTELSNL_URL,
                params={
                    "destination": destination,
                    "checkIn": check_in.isoformat(),
                    "checkOut": check_out.isoformat(),
                    "adults": guests,
                    "token": settings.HOTELSNL_API_KEY,
                    "currency": "USD",
                    "limit": 20,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("hotelsnl_search_failed", destination=destination, error=str(exc))
        return []

    nights = (check_out - check_in).days or 1
    offers: list[HotelOffer] = []
    for hotel in (data if isinstance(data, list) else [])[:20]:
        try:
            price_night = hotel.get("priceFrom")
            offers.append(
                HotelOffer(
                    hotel_id=str(hotel.get("id", "")),
                    name=hotel.get("hotelName", ""),
                    lat=hotel.get("location", {}).get("lat"),
                    lng=hotel.get("location", {}).get("lon"),
                    price_per_night=price_night,
                    price_total=price_night * nights if price_night else None,
                    price_currency="USD",
                    star_rating=hotel.get("stars"),
                    meal_plan=None,
                    refundable=None,
                    booking_ref=None,
                    image_url=hotel.get("photoUrl"),
                    source_provider="hotelsnl",
                    source_ref=str(hotel.get("id", "")),
                    raw_payload=hotel,
                )
            )
        except Exception:
            continue

    logger.info("hotelsnl_search_ok", destination=destination, count=len(offers))
    return offers


async def search_hotels(
    destination: str,
    check_in: date,
    check_out: date,
    guests: int = 1,
    cache: Redis | None = None,  # type: ignore[type-arg]
) -> list[HotelOffer]:
    """
    Search hotels via LiteAPI (primary) → Hotels.nl (fallback).
    Caches results for 1 hour. Returns [] on total failure — never raises.
    """
    key = _cache_key(destination, check_in, check_out, guests)
    cached = await redis_get_cached(cache, key)
    if cached:
        logger.info("hotels_cache_hit", destination=destination)
        return [HotelOffer(**h) for h in cached]

    offers = await _search_liteapi(destination, check_in, check_out, guests)

    if not offers:
        logger.info("hotels_liteapi_empty_trying_fallback", destination=destination)
        offers = await _search_hotelsnl(destination, check_in, check_out, guests)

    if offers:
        payload = [o.model_dump() for o in offers]
        await redis_set_cached(cache, key, payload, _CACHE_TTL)

    return offers
