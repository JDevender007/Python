from __future__ import annotations

import re

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def clean_text(
    value: str | None,
) -> str:

    if not value:

        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def clean_price(
    value: str | None,
) -> float:

    if not value:

        return 0.0

    cleaned = re.sub(
        r"[^\d.]",
        "",
        value,
    )

    try:

        return float(cleaned)

    except ValueError:

        return 0.0


def format_price(
    value: float,
    symbol: str = "₹",
) -> str:

    return f"{symbol}" f"{value:,.2f}"


def format_date(
    value: datetime,
    date_format: str,
) -> str:

    return value.strftime(date_format)


def is_valid_url(
    url: str,
) -> bool:

    try:

        parsed = urlparse(url)

        return parsed.scheme in {
            "http",
            "https",
        } and bool(parsed.netloc)

    except ValueError:

        return False


def create_directory(
    path: Path,
) -> None:

    path.mkdir(
        parents=True,
        exist_ok=True,
    )


def calculate_percentage_change(
    old_price: float,
    new_price: float,
) -> float:

    if old_price <= 0:

        return 0.0

    return ((new_price - old_price) / old_price) * 100


def generate_timestamp() -> str:

    return datetime.now().isoformat(timespec="seconds")
