from dataclasses import dataclass
from datetime import datetime


@dataclass
class Market:
    market_id: str  # conditionId (for CLOB)
    slug: str
    title: str
    timeframe: str
    start_time: datetime
    end_time: datetime
    numeric_id: str = None  # Numeric market ID (for Data API)

    @property
    def duration_seconds(self) -> float:
        return max(1.0, (self.end_time - self.start_time).total_seconds())


@dataclass
class PositionSnapshot:
    wallet: str
    side: str
    entry_price: float
    size: float
    value: float
    first_seen_ts: int

