"""
Historical USD price lookups via the CoinGecko free API.
"""

import time
from datetime import datetime

import requests

from config import COINGECKO_API_URL

# In-memory cache: (coingecko_id, date_str) -> price_usd
_cache: dict[tuple[str, str], float | None] = {}

# Simple rate-limit: minimum seconds between requests
_RATE_LIMIT = 1.5
_last_request_time: float = 0.0


def _rate_limit() -> None:
    global _last_request_time
    now = time.time()
    wait = _RATE_LIMIT - (now - _last_request_time)
    if wait > 0:
        time.sleep(wait)
    _last_request_time = time.time()


def get_historical_price(
    coingecko_id: str,
    timestamp: int | float,
) -> float | None:
    """Return the USD price of *coingecko_id* at the given UNIX *timestamp*.

    Returns ``None`` when the price cannot be determined (API error, missing
    data, etc.).
    """
    dt = datetime.utcfromtimestamp(float(timestamp))
    date_str = dt.strftime("%d-%m-%Y")

    cache_key = (coingecko_id, date_str)
    if cache_key in _cache:
        return _cache[cache_key]

    _rate_limit()

    url = f"{COINGECKO_API_URL}/coins/{coingecko_id}/history"
    params = {"date": date_str, "localization": "false"}
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        price = data.get("market_data", {}).get("current_price", {}).get("usd")
    except Exception:
        price = None

    _cache[cache_key] = price
    return price


def get_current_price(coingecko_id: str) -> float | None:
    """Return the current USD price of *coingecko_id*."""
    _rate_limit()
    url = f"{COINGECKO_API_URL}/simple/price"
    params = {"ids": coingecko_id, "vs_currencies": "usd"}
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get(coingecko_id, {}).get("usd")
    except Exception:
        return None
