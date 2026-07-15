"""Static currency conversion utility.

Rates are approximate mid-market values relative to INR.
Update periodically — these don't need to be exact, they're used for budget
comparison (not financial transactions).
"""

from __future__ import annotations

# Approximate units of each currency per 1 INR
# i.e., 1 INR = _RATE_TO_INR[X] units of X
# Equivalently: 1 unit of X = (1 / _RATE_TO_INR[X]) INR
_RATE_TO_INR: dict[str, float] = {
    "INR": 1.0,
    "USD": 0.01190,  # ~₹84/USD
    "EUR": 0.01099,  # ~₹91/EUR
    "GBP": 0.00943,  # ~₹106/GBP
    "JPY": 1.851,  # ~₹0.54/JPY
    "AUD": 0.01852,  # ~₹54/AUD
    "NZD": 0.02000,  # ~₹50/NZD
    "CAD": 0.01639,  # ~₹61/CAD
    "CHF": 0.01053,  # ~₹95/CHF
    "SEK": 0.12500,  # ~₹8/SEK
    "NOK": 0.11111,  # ~₹9/NOK
    "DKK": 0.08197,  # ~₹12.2/DKK
    "SGD": 0.01587,  # ~₹63/SGD
    "HKD": 0.09346,  # ~₹10.7/HKD
    "MYR": 0.05263,  # ~₹19/MYR
    "THB": 0.41667,  # ~₹2.4/THB
    "IDR": 192.31,  # ~₹0.0052/IDR
    "PHP": 0.68027,  # ~₹1.47/PHP
    "VND": 303.03,  # ~₹0.0033/VND
    "KRW": 16.667,  # ~₹0.060/KRW
    "CNY": 0.08696,  # ~₹11.5/CNY
    "TWD": 0.38462,  # ~₹2.6/TWD
    "NPR": 1.6,  # ~₹0.625/NPR
    "LKR": 3.175,  # ~₹0.315/LKR
    "MMK": 25.0,  # ~₹0.04/MMK
    "LAK": 25.0,  # ~₹0.04/LAK
    "MXN": 0.23810,  # ~₹4.2/MXN
    "BRL": 0.06667,  # ~₹15/BRL
    "ARS": 11.111,  # ~₹0.09/ARS
    "PEN": 0.04444,  # ~₹22.5/PEN
    "COP": 47.62,  # ~₹0.021/COP
    "AED": 0.04386,  # ~₹22.8/AED
    "QAR": 0.04329,  # ~₹23.1/QAR
    "EGP": 0.57143,  # ~₹1.75/EGP
    "MAD": 0.11111,  # ~₹9/MAD
    "ZAR": 0.22222,  # ~₹4.5/ZAR
    "KES": 1.53846,  # ~₹0.65/KES
    "TRY": 0.41667,  # ~₹2.4/TRY
    "RUB": 1.07527,  # ~₹0.93/RUB
    "CZK": 0.23810,  # ~₹4.2/CZK
    "HUF": 3.07692,  # ~₹0.325/HUF
    "PLN": 0.04167,  # ~₹24/PLN
    "RON": 0.05000,  # ~₹20/RON
    "HRK": 0.14286,  # ~₹7/HRK
    "GEL": 0.03226,  # ~₹31/GEL
}


# Destination city/country → ISO-4217 local currency.
# Lives here so both the itinerary planner (first-pass enforcement) and the budget
# optimizer (second-pass correction on whatever the DB contains) can share it.
_LOCAL_CURRENCY: dict[str, str] = {
    "indonesia": "IDR",
    "bali": "IDR",
    "lombok": "IDR",
    "java": "IDR",
    "japan": "JPY",
    "tokyo": "JPY",
    "osaka": "JPY",
    "kyoto": "JPY",
    "india": "INR",
    "delhi": "INR",
    "mumbai": "INR",
    "bangalore": "INR",
    "goa": "INR",
    "jaipur": "INR",
    "agra": "INR",
    "chennai": "INR",
    "thailand": "THB",
    "bangkok": "THB",
    "phuket": "THB",
    "chiang mai": "THB",
    "vietnam": "VND",
    "hanoi": "VND",
    "ho chi minh city": "VND",
    "cambodia": "USD",
    "malaysia": "MYR",
    "kuala lumpur": "MYR",
    "singapore": "SGD",
    "philippines": "PHP",
    "manila": "PHP",
    "south korea": "KRW",
    "korea": "KRW",
    "seoul": "KRW",
    "china": "CNY",
    "beijing": "CNY",
    "shanghai": "CNY",
    "taiwan": "TWD",
    "taipei": "TWD",
    "hong kong": "HKD",
    "nepal": "NPR",
    "kathmandu": "NPR",
    "sri lanka": "LKR",
    "colombo": "LKR",
    "myanmar": "MMK",
    "laos": "LAK",
    "australia": "AUD",
    "sydney": "AUD",
    "melbourne": "AUD",
    "new zealand": "NZD",
    "usa": "USD",
    "united states": "USD",
    "new york": "USD",
    "los angeles": "USD",
    "chicago": "USD",
    "san francisco": "USD",
    "miami": "USD",
    "las vegas": "USD",
    "boston": "USD",
    "seattle": "USD",
    "canada": "CAD",
    "toronto": "CAD",
    "vancouver": "CAD",
    "montreal": "CAD",
    "mexico": "MXN",
    "mexico city": "MXN",
    "brazil": "BRL",
    "rio de janeiro": "BRL",
    "sao paulo": "BRL",
    "argentina": "ARS",
    "buenos aires": "ARS",
    "peru": "PEN",
    "lima": "PEN",
    "colombia": "COP",
    "uk": "GBP",
    "united kingdom": "GBP",
    "london": "GBP",
    "france": "EUR",
    "paris": "EUR",
    "germany": "EUR",
    "berlin": "EUR",
    "italy": "EUR",
    "rome": "EUR",
    "milan": "EUR",
    "spain": "EUR",
    "barcelona": "EUR",
    "madrid": "EUR",
    "portugal": "EUR",
    "lisbon": "EUR",
    "netherlands": "EUR",
    "amsterdam": "EUR",
    "greece": "EUR",
    "athens": "EUR",
    "santorini": "EUR",
    "austria": "EUR",
    "vienna": "EUR",
    "belgium": "EUR",
    "brussels": "EUR",
    "ireland": "EUR",
    "dublin": "EUR",
    "finland": "EUR",
    "helsinki": "EUR",
    "munich": "EUR",
    "frankfurt": "EUR",
    "venice": "EUR",
    "florence": "EUR",
    "naples": "EUR",
    "nice": "EUR",
    "lyon": "EUR",
    "switzerland": "CHF",
    "zurich": "CHF",
    "sweden": "SEK",
    "stockholm": "SEK",
    "norway": "NOK",
    "oslo": "NOK",
    "denmark": "DKK",
    "copenhagen": "DKK",
    "uae": "AED",
    "dubai": "AED",
    "qatar": "QAR",
    "egypt": "EGP",
    "cairo": "EGP",
    "morocco": "MAD",
    "south africa": "ZAR",
    "cape town": "ZAR",
    "kenya": "KES",
    "nairobi": "KES",
    "turkey": "TRY",
    "turkiye": "TRY",
    "türkiye": "TRY",
    "istanbul": "TRY",
    "ankara": "TRY",
    "izmir": "TRY",
    "antalya": "TRY",
    "cappadocia": "TRY",
    "russia": "RUB",
    "czech republic": "CZK",
    "czechia": "CZK",
    "prague": "CZK",
    "hungary": "HUF",
    "budapest": "HUF",
    "poland": "PLN",
    "croatia": "EUR",
    "romania": "RON",
}


def destination_currency(city: str, country: str | None = None) -> str:
    """Return the ISO-4217 local currency for a destination, falling back to USD."""
    for key in (city.lower().strip(), (country or "").lower().strip()):
        if key and key in _LOCAL_CURRENCY:
            return _LOCAL_CURRENCY[key]
    return "USD"


def is_known_currency(code: str | None) -> bool:
    """True when the ISO code has a conversion rate in this module's table."""
    return bool(code) and str(code).upper().strip() in _RATE_TO_INR


def typical_amount(usd_amount: float, currency: str) -> float:
    """A nicely-rounded local-currency equivalent of a USD amount.

    Used to build realistic prompt examples for the itinerary LLM — an example
    figure at the wrong order of magnitude anchors the model to garbage prices
    (a hardcoded 50000 reads as pocket change in IDR but as a luxury weekend in INR).
    Rounds to two significant figures so examples read naturally (1260 → 1300).
    """
    value = convert(usd_amount, "USD", currency)
    if value <= 0:
        return usd_amount
    import math

    magnitude = 10 ** math.floor(math.log10(value))
    return round((value / magnitude) * 10) / 10 * magnitude


def to_inr(amount: float, from_currency: str) -> float:
    """Convert an amount from any currency to INR."""
    fc = from_currency.upper().strip()
    if fc == "INR":
        return amount
    rate = _RATE_TO_INR.get(fc)
    if rate is None:
        return amount  # unknown currency — return as-is (safer than zero)
    # 1 unit of fc = (1/rate) INR
    return amount / rate


def convert(amount: float, from_currency: str, to_currency: str) -> float:
    """Convert an amount between any two currencies (via INR as pivot)."""
    fc = from_currency.upper().strip()
    tc = to_currency.upper().strip()
    if fc == tc:
        return amount
    inr_amount = to_inr(amount, fc)
    if tc == "INR":
        return inr_amount
    tc_rate = _RATE_TO_INR.get(tc)
    if tc_rate is None:
        return inr_amount  # unknown target — return INR amount
    return inr_amount * tc_rate
