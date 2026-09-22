"""End-of-day ticker prices from Tiingo.

Only this provider knows Tiingo's wire format. Callers receive normalized
Decimal prices and market dates, and an upstream failure never fabricates a
zero price.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx


@dataclass(frozen=True, slots=True)
class MarketPrice:
    symbol: str
    price: Decimal
    as_of: date


@dataclass(frozen=True, slots=True)
class MarketPriceBatch:
    prices: dict[str, MarketPrice]
    errors: dict[str, str]


class TiingoMarketDataProvider:
    base_url = "https://api.tiingo.com/tiingo/daily"

    def __init__(self, api_key: str | None, client: httpx.AsyncClient | None = None):
        self.api_key = api_key
        self._client = client
        self._cache: dict[str, MarketPrice] = {}
        self._error_cache: dict[str, str] = {}

    async def latest_prices(self, symbols: set[str]) -> MarketPriceBatch:
        normalized = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
        prices = {symbol: self._cache[symbol] for symbol in normalized if symbol in self._cache}
        errors = {symbol: self._error_cache[symbol] for symbol in normalized if symbol in self._error_cache}
        missing = sorted(normalized - prices.keys() - errors.keys())
        if not missing:
            return MarketPriceBatch(prices=prices, errors=errors)
        if not self.api_key:
            return MarketPriceBatch(
                prices=prices,
                errors={symbol: "Automatic ticker pricing is not configured." for symbol in missing},
            )

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=15)
        try:
            for symbol in missing:
                if not re.fullmatch(r"[A-Z0-9.^_-]{1,20}", symbol):
                    errors[symbol] = "Ticker contains unsupported characters."
                    self._error_cache[symbol] = errors[symbol]
                    continue
                try:
                    market_price = await self._latest_price(client, symbol)
                    prices[symbol] = market_price
                    self._cache[symbol] = market_price
                except (httpx.HTTPError, KeyError, ValueError, InvalidOperation):
                    errors[symbol] = "No current market price was available."
                    self._error_cache[symbol] = errors[symbol]
        finally:
            if owns_client:
                await client.aclose()
        return MarketPriceBatch(prices=prices, errors=errors)

    async def _latest_price(self, client: httpx.AsyncClient, symbol: str) -> MarketPrice:
        today = date.today()
        response = await client.get(
            f"{self.base_url}/{quote(symbol, safe='')}/prices",
            params={"startDate": (today - timedelta(days=14)).isoformat(), "endDate": today.isoformat()},
            headers={"Authorization": f"Token {self.api_key}"},
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise ValueError("empty market-price response")
        latest = max(rows, key=lambda row: row["date"])
        price = Decimal(str(latest["close"]))
        if price <= 0:
            raise ValueError("non-positive market price")
        return MarketPrice(symbol=symbol, price=price, as_of=date.fromisoformat(latest["date"][:10]))
