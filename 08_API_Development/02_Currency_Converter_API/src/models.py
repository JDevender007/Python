"""
Currency Converter API - Data Models
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime


@dataclass
class ExchangeRate:
    """Single exchange rate."""
    base: str
    target: str
    rate: float
    timestamp: int
    source: str = "unknown"

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp) if self.timestamp > 0 else datetime.now()

    @property
    def formatted_rate(self) -> str:
        if self.rate >= 1:
            return f"{self.rate:.4f}"
        elif self.rate >= 0.01:
            return f"{self.rate:.6f}"
        return f"{self.rate:.8f}"


@dataclass
class ExchangeRatesResponse:
    """Complete exchange rates response."""
    base: str
    rates: Dict[str, float]
    timestamp: int
    date: str
    source: str = "unknown"

    def get_rate(self, target: str) -> Optional[float]:
        """Get rate for target currency."""
        return self.rates.get(target.upper())

    def get_all_currencies(self) -> List[str]:
        """Get list of all available currencies."""
        return sorted(self.rates.keys())

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp) if self.timestamp > 0 else datetime.now()


@dataclass
class ConversionResult:
    """Currency conversion result."""
    from_currency: str
    to_currency: str
    amount: float
    result: float
    rate: float
    timestamp: int
    source: str = "unknown"

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp) if self.timestamp > 0 else datetime.now()


@dataclass
class HistoryEntry:
    """Conversion history entry."""
    timestamp: str
    from_currency: str
    to_currency: str
    amount: float
    result: float
    rate: float

    @property
    def formatted_time(self) -> str:
        try:
            dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return self.timestamp


@dataclass
class CurrencyInfo:
    """Currency information."""
    code: str
    name: str
    symbol: str

    @property
    def display(self) -> str:
        return f"{self.code} - {self.name} ({self.symbol})"


def parse_exchange_rates(data: Dict) -> Optional[ExchangeRatesResponse]:
    """Parse exchange rates from API response."""
    try:
        return ExchangeRatesResponse(
            base=data.get("base", "USD"),
            rates=data.get("rates", {}),
            timestamp=data.get("timestamp", 0),
            date=data.get("date", ""),
            source=data.get("source", "unknown")
        )
    except Exception:
        return None


def parse_pair_rate(data: Dict) -> Optional[ExchangeRate]:
    """Parse pair rate from API response."""
    try:
        return ExchangeRate(
            base=data.get("base", ""),
            target=data.get("target", ""),
            rate=data.get("rate", 0),
            timestamp=data.get("timestamp", 0),
            source=data.get("source", "unknown")
        )
    except Exception:
        return None


def create_conversion_result(
    from_currency: str,
    to_currency: str,
    amount: float,
    rate: float,
    timestamp: int,
    source: str = "unknown"
) -> ConversionResult:
    """Create conversion result."""
    return ConversionResult(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        amount=amount,
        result=round(amount * rate, 2),
        rate=rate,
        timestamp=timestamp,
        source=source
    )