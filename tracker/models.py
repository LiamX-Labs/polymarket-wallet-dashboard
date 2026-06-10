from dataclasses import dataclass
from datetime import datetime


@dataclass
class Market:
    __slots__ = ['market_id', 'slug', 'title', 'timeframe', 'start_time', 'end_time', 'numeric_id']
    market_id: str  # conditionId (for CLOB)
    slug: str
    title: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    numeric_id: str  # Numeric market ID (for Data API)

    @property
    def duration_seconds(self) -> float:
        return max(1.0, (self.end_time - self.start_time).total_seconds())


@dataclass
class PositionSnapshot:
    __slots__ = ['wallet', 'side', 'entry_price', 'size', 'value', 'first_seen_ts']
    wallet: str
    side: str
    entry_price: float
    size: float
    value: float
    first_seen_ts: int

