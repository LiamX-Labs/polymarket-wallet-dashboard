import re
import time
from datetime import datetime, timezone
from typing import List

import requests

from bot.config import GAMMA_API_BASE_URL
from .models import Market


TIMEFRAME_PATTERN = re.compile(r"\b(5m|15m|1h|4h)\b", re.IGNORECASE)
# Slug pattern for BTC updown markets: btc-updown-{timeframe}-{timestamp}
SLUG_PATTERN = re.compile(r"(btc|bitcoin).*updown", re.IGNORECASE)


class GammaClient:
    """Fetch and filter BTC Up/Down markets from Gamma API."""

    def __init__(self, base_url: str = GAMMA_API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._cache_ttl_seconds = 60
        self._cached_markets: List[Market] = []
        self._cached_at = 0.0

    def get_market_by_slug(self, slug: str) -> Market | None:
        """
        Directly fetch a market by its slug using the pattern:
        https://gamma-api.polymarket.com/events/slug/{slug}

        Example: btc-updown-15m-1766162100

        The slug pattern is: btc-updown-{timeframe}-{end_epoch}
        where end_epoch is the Unix timestamp when the market ends.
        """
        endpoint = f"{self.base_url}/events/slug/{slug}"
        try:
            response = self.session.get(endpoint, timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            event = response.json()

            title = event.get("question") or event.get("title") or ""
            timeframe = self._extract_timeframe(title, slug)
            if not timeframe:
                return None

            # Parse slug to get actual timing (API startDate/endDate are unreliable)
            # Slug format: btc-updown-{timeframe}-{end_epoch}
            parts = slug.split('-')
            if len(parts) >= 4:
                try:
                    end_epoch = int(parts[-1])
                    # Duration from timeframe
                    duration_map = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}
                    duration = duration_map.get(timeframe, 300)

                    start_epoch = end_epoch - duration
                    start_time = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
                    end_time = datetime.fromtimestamp(end_epoch, tz=timezone.utc)

                    # Check if market has expired
                    if end_time <= datetime.now(timezone.utc):
                        return None
                except (ValueError, IndexError):
                    # Fall back to API dates if slug parsing fails
                    start_time = self._parse_dt(event.get("startDate") or event.get("start_date"))
                    end_time = self._parse_dt(event.get("endDate") or event.get("end_date"))
                    if not start_time or not end_time or end_time <= datetime.now(timezone.utc):
                        return None
            else:
                # Fall back to API dates
                start_time = self._parse_dt(event.get("startDate") or event.get("start_date"))
                end_time = self._parse_dt(event.get("endDate") or event.get("end_date"))
                if not start_time or not end_time or end_time <= datetime.now(timezone.utc):
                    return None

            event_markets = event.get("markets", [])
            if event_markets and len(event_markets) > 0:
                market_id = str(event_markets[0].get("conditionId") or event.get("id") or slug)
                numeric_id = str(event_markets[0].get("id") or "")
            else:
                market_id = str(event.get("id") or slug)
                numeric_id = str(event.get("id") or "")

            return Market(
                market_id=market_id,
                slug=slug,
                title=title,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                numeric_id=numeric_id if numeric_id else None,
            )
        except Exception:
            return None

    def get_active_btc_markets_by_slug(self) -> List[Market]:
        """
        Optimized method: Generate predictable slug patterns and query directly.
        Pattern: btc-updown-{timeframe}-{epoch}

        This is much faster than scanning all events since we can predict
        when markets should exist based on time intervals.
        """
        markets: List[Market] = []
        now = datetime.now(timezone.utc)
        current_epoch = int(now.timestamp())

        # Define timeframes and their intervals in seconds
        timeframes = {
            "5m": 300,    # 5 minutes
            "15m": 900,   # 15 minutes
            "1h": 3600,   # 1 hour
            "4h": 14400,  # 4 hours
        }

        # For each timeframe, generate slugs for upcoming markets
        # Check current + next few time slots
        for tf, interval in timeframes.items():
            # Round current time to nearest interval
            # Check current slot and next 3 slots
            for i in range(-1, 4):  # Check 1 past, current, and 3 future
                aligned_epoch = (current_epoch // interval) * interval + (i * interval)
                slug = f"btc-updown-{tf}-{aligned_epoch}"

                market = self.get_market_by_slug(slug)
                if market:
                    markets.append(market)

        # Remove duplicates
        deduped = []
        seen = set()
        for m in markets:
            if m.market_id in seen:
                continue
            seen.add(m.market_id)
            deduped.append(m)

        return deduped

    def get_active_btc_markets(self) -> List[Market]:
        """
        Fetch active BTC Up/Down markets.

        Uses optimized slug-based direct queries when possible,
        falls back to scanning events endpoint if needed.
        """
        now_ts = time.time()
        if now_ts - self._cached_at < self._cache_ttl_seconds:
            return list(self._cached_markets)

        # Try optimized slug-based approach first
        markets = self.get_active_btc_markets_by_slug()

        # If we found markets via slug approach, use those
        if markets:
            self._cached_markets = markets
            self._cached_at = now_ts
            return list(self._cached_markets)

        # Fallback: scan events endpoint (original approach)
        # This handles edge cases where slug pattern might change
        endpoint = f"{self.base_url}/events"
        markets = []
        page_size = 100
        max_pages = 20

        for page in range(max_pages):
            params = {"active": "true", "closed": "false", "limit": page_size, "offset": page * page_size}
            response = self.session.get(endpoint, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else []
            if not rows:
                break

            for event in rows:
                title = event.get("question") or event.get("title") or ""
                slug = event.get("slug") or ""

                # Fast path: check slug pattern first (e.g., btc-updown-5m-1766162100)
                # This is more efficient than checking title for common patterns
                if SLUG_PATTERN.search(slug):
                    # Slug matches the pattern, continue processing
                    pass
                else:
                    # Fall back to title/slug text search for other formats
                    merged = f"{title} {slug}".lower()
                    # Accept both BTC and Bitcoin naming.
                    if "btc" not in merged and "bitcoin" not in merged:
                        continue
                    # Focus on up/down intraday structure.
                    if "up or down" not in merged and "updown" not in merged:
                        continue

                timeframe = self._extract_timeframe(title, slug)
                if timeframe is None:
                    continue

                start_time = self._parse_dt(event.get("startDate") or event.get("start_date"))
                end_time = self._parse_dt(event.get("endDate") or event.get("end_date"))
                if not start_time or not end_time:
                    continue
                if end_time <= datetime.now(timezone.utc):
                    continue

                # Events contain markets - use the first market's conditionId or event id
                event_markets = event.get("markets", [])
                if event_markets and len(event_markets) > 0:
                    market_id = str(event_markets[0].get("conditionId") or event.get("id") or slug)
                else:
                    market_id = str(event.get("id") or slug)

                markets.append(
                    Market(
                        market_id=market_id,
                        slug=slug,
                        title=title,
                        timeframe=timeframe,
                        start_time=start_time,
                        end_time=end_time,
                    )
                )

        # Remove duplicates by market id while preserving order.
        deduped = []
        seen = set()
        for m in markets:
            if m.market_id in seen:
                continue
            seen.add(m.market_id)
            deduped.append(m)

        self._cached_markets = deduped
        self._cached_at = now_ts
        return list(self._cached_markets)

    @staticmethod
    def _extract_timeframe(title: str, slug: str) -> str | None:
        merged = f"{title} {slug}"
        match = TIMEFRAME_PATTERN.search(merged)
        if not match:
            return None
        return match.group(1).lower()

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        except ValueError:
            return None

