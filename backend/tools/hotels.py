import hashlib
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
_LITEAPI_RATES_URL = "https://api.liteapi.travel/v3.0/hotels/rates"
# LiteAPI rates require the guest's nationality as an ISO-3166-1 alpha-2 code (India
# is "IN", not "IND") — it affects availability and pricing. Defaulted to India; could
# be derived from the user's profile in future.
_GUEST_NATIONALITY = "IN"

# Common destination → ISO-2 country code (expand as needed)
_COUNTRY_CODES: dict[str, str] = {
    "japan": "JP",
    "india": "IN",
    "usa": "US",
    "united states": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "france": "FR",
    "germany": "DE",
    "italy": "IT",
    "spain": "ES",
    "thailand": "TH",
    "indonesia": "ID",
    "australia": "AU",
    "canada": "CA",
    "brazil": "BR",
    "mexico": "MX",
    "china": "CN",
    "south korea": "KR",
    "korea": "KR",
    "singapore": "SG",
    "malaysia": "MY",
    "vietnam": "VN",
    "cambodia": "KH",
    "nepal": "NP",
    "turkey": "TR",
    "greece": "GR",
    "portugal": "PT",
    "netherlands": "NL",
    "switzerland": "CH",
    "austria": "AT",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "egypt": "EG",
    "morocco": "MA",
    "south africa": "ZA",
    "kenya": "KE",
    "uae": "AE",
    "united arab emirates": "AE",
    "dubai": "AE",
    "qatar": "QA",
    "argentina": "AR",
    "peru": "PE",
    "colombia": "CO",
    "new zealand": "NZ",
    "philippines": "PH",
    "sri lanka": "LK",
    "myanmar": "MM",
    "laos": "LA",
    "taiwan": "TW",
    "hong kong": "HK",
    "macao": "MO",
    "russia": "RU",
    "poland": "PL",
    "czech republic": "CZ",
    "czechia": "CZ",
    "hungary": "HU",
    "croatia": "HR",
    "romania": "RO",
}

# City → ISO-2 fallback (for trips without a country)
_CITY_COUNTRY: dict[str, str] = {
    "tokyo": "JP",
    "osaka": "JP",
    "kyoto": "JP",
    "delhi": "IN",
    "mumbai": "IN",
    "bangalore": "IN",
    "kolkata": "IN",
    "assam": "IN",
    "paris": "FR",
    "london": "GB",
    "new york": "US",
    "los angeles": "US",
    "rome": "IT",
    "milan": "IT",
    "barcelona": "ES",
    "madrid": "ES",
    "berlin": "DE",
    "amsterdam": "NL",
    "bangkok": "TH",
    "bali": "ID",
    "singapore": "SG",
    "sydney": "AU",
    "melbourne": "AU",
    "toronto": "CA",
    "dubai": "AE",
    "istanbul": "TR",
    "athens": "GR",
    "lisbon": "PT",
    "prague": "CZ",
    "budapest": "HU",
    "vienna": "AT",
    "zurich": "CH",
    "stockholm": "SE",
    "oslo": "NO",
    "copenhagen": "DK",
    "cairo": "EG",
    "cape town": "ZA",
    "nairobi": "KE",
    "seoul": "KR",
    "beijing": "CN",
    "shanghai": "CN",
    "taipei": "TW",
    "kuala lumpur": "MY",
    "ho chi minh city": "VN",
    "hanoi": "VN",
    "phnom penh": "KH",
    "kathmandu": "NP",
    "colombo": "LK",
    "manila": "PH",
    "jakarta": "ID",
    "mexico city": "MX",
    "buenos aires": "AR",
    "lima": "PE",
    "rio de janeiro": "BR",
    "sao paulo": "BR",
}


def _country_code(city: str, country: str | None) -> str | None:
    """Return ISO-2 country code from trip country or city name."""
    if country:
        code = _COUNTRY_CODES.get(country.lower().strip())
        if code:
            return code
        if len(country) == 2:
            return country.upper()
    return _CITY_COUNTRY.get(city.lower().strip())


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


def _cache_key(
    destination: str, check_in: date, check_out: date, guests: int, currency: str
) -> str:
    raw = f"{destination}|{check_in}|{check_out}|{guests}|{currency}"
    return f"hotels:{hashlib.sha256(raw.encode()).hexdigest()}"


async def _fetch_rates(
    hotel_ids: list[str],
    check_in: date,
    check_out: date,
    guests: int,
    currency: str = "USD",
) -> dict[str, tuple[float | None, float | None, str]]:
    """
    Fetch live rates from LiteAPI /v3.0/hotels/rates.
    Returns {hotel_id: (price_per_night, price_total, currency)}.
    Silently returns {} on any error — callers fall back to null prices.
    """
    if not settings.LITEAPI_KEY or not hotel_ids:
        return {}

    nights = (check_out - check_in).days or 1
    # LiteAPI /v3.0/hotels/rates is a POST with a JSON body — a GET returns an empty 200,
    # which is what was silently failing here. `occupancies` and `guestNationality` are
    # required for the API to return any rates.
    payload = {
        "hotelIds": hotel_ids,
        "occupancies": [{"adults": guests}],
        "currency": currency,
        "guestNationality": _GUEST_NATIONALITY,
        "checkin": check_in.isoformat(),
        "checkout": check_out.isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _LITEAPI_RATES_URL,
                json=payload,
                headers={
                    "X-API-Key": settings.LITEAPI_KEY,
                    "Content-Type": "application/json",
                    "accept": "application/json",
                },
            )
            if resp.status_code != 200:
                logger.warning(
                    "liteapi_rates_non200",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                return {}
            data = resp.json()
    except Exception as exc:
        logger.warning("liteapi_rates_failed", error=str(exc))
        return {}

    result: dict[str, tuple[float | None, float | None, str]] = {}
    for item in data.get("data", []):
        hotel_id = str(item.get("hotelId", ""))
        if not hotel_id:
            continue

        # Walk roomTypes → rates → retailRate.total for the cheapest stay total. The
        # rates response nests prices under "roomTypes" (not "rooms"); fall back to
        # "rooms" defensively in case the schema varies.
        best_total: float | None = None
        best_currency = currency
        for room in item.get("roomTypes") or item.get("rooms") or []:
            for rate in room.get("rates", []):
                totals = rate.get("retailRate", {}).get("total", [])
                if not totals:
                    continue
                amt = totals[0].get("amount")
                if amt is None:
                    continue
                try:
                    val = float(amt)
                except (TypeError, ValueError):
                    continue
                if best_total is None or val < best_total:
                    best_total = val
                    best_currency = totals[0].get("currency") or currency

        if best_total is not None:
            pn = round(best_total / nights, 2)
            result[hotel_id] = (pn, round(best_total, 2), best_currency)

    logger.info("liteapi_rates_ok", fetched=len(result), requested=len(hotel_ids))
    return result


async def _search_liteapi(
    destination: str,
    check_in: date,
    check_out: date,
    guests: int,
    country: str | None = None,
    currency: str = "USD",
) -> list[HotelOffer]:
    if not settings.LITEAPI_KEY:
        logger.warning("liteapi_key_missing")
        return []

    country_code = _country_code(destination, country)
    params: dict[str, str | int] = {
        "cityName": destination,
        "limit": 20,
    }
    if country_code:
        params["countryCode"] = country_code

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _LITEAPI_HOTELS_URL,
                params=params,
                headers={"X-API-Key": settings.LITEAPI_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("liteapi_search_failed", destination=destination, error=str(exc))
        return []

    nights = (check_out - check_in).days or 1
    offers: list[HotelOffer] = []
    for hotel in data.get("data", [])[:20]:
        try:
            offers.append(
                HotelOffer(
                    hotel_id=str(hotel.get("id", "")),
                    name=hotel.get("name", ""),
                    lat=hotel.get("latitude"),
                    lng=hotel.get("longitude"),
                    price_per_night=hotel.get("minRate"),
                    price_total=(hotel["minRate"] * nights) if hotel.get("minRate") else None,
                    price_currency=hotel.get("currency", "USD"),
                    star_rating=hotel.get("stars"),
                    meal_plan=None,
                    refundable=None,
                    booking_ref=None,
                    image_url=hotel.get("main_photo") or hotel.get("thumbnail"),
                    source_provider="liteapi",
                    source_ref=str(hotel.get("id", "")),
                    raw_payload=hotel,
                )
            )
        except Exception:
            continue

    logger.info("liteapi_search_ok", destination=destination, count=len(offers))

    # Enrich with live rates
    hotel_ids = [o.hotel_id for o in offers]
    rates = await _fetch_rates(hotel_ids, check_in, check_out, guests, currency)
    for offer in offers:
        if offer.hotel_id in rates:
            pn, total, currency = rates[offer.hotel_id]
            offer.price_per_night = pn
            offer.price_total = total
            offer.price_currency = currency

    return offers


async def search_hotels(
    destination: str,
    check_in: date,
    check_out: date,
    guests: int = 1,
    country: str | None = None,
    currency: str = "USD",
    cache: Redis | None = None,  # type: ignore[type-arg]
) -> list[HotelOffer]:
    """
    Search hotels via LiteAPI /data/hotels (static metadata + star/location).
    Returns [] on failure — never raises.
    """
    key = _cache_key(destination, check_in, check_out, guests, currency)
    cached = await redis_get_cached(cache, key)
    if cached:
        logger.info("hotels_cache_hit", destination=destination)
        return [HotelOffer(**h) for h in cached]

    offers = await _search_liteapi(destination, check_in, check_out, guests, country, currency)

    if offers:
        payload = [o.model_dump() for o in offers]
        await redis_set_cached(cache, key, payload, _CACHE_TTL)

    return offers
