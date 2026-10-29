"""Small helpers for reading raw cell values.

Tables are loaded as text so that nothing is silently converted. These helpers decide what a raw
value means: missing, a number (possibly written as "$1,200.00"), or an ISO date.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime

MISSING_TOKENS = {"", "na", "n/a", "nan", "null", "none", "-"}

_NUMBER = re.compile(r"^[-+]?\d+(\.\d+)?$")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().lower() in MISSING_TOKENS:
        return True
    try:
        import pandas as pd

        return bool(pd.isna(value)) if not isinstance(value, (list, dict)) else False
    except (TypeError, ValueError):
        return False


def plain_number(value) -> float | None:
    """Parse a value that is already a clean number ("12", "12.5", 12)."""
    if is_missing(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    return float(text) if _NUMBER.match(text) else None


def loose_number(value) -> float | None:
    """Parse a number that may carry a currency sign, thousands separators or spaces."""
    number = plain_number(value)
    if number is not None:
        return number
    if is_missing(value):
        return None
    text = str(value).strip().replace("$", "").replace(",", "").replace(" ", "")
    return float(text) if _NUMBER.match(text) else None


def iso_date(value) -> date | None:
    """Parse a YYYY-MM-DD value; anything else (including impossible dates) returns None."""
    if is_missing(value):
        return None
    match = _ISO_DATE.match(str(value).strip())
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def normalize_label(value) -> str:
    return str(value).strip().lower()


def comparable(value):
    """Representation used to compare two cells: numbers by value, dates as YYYY-MM-DD, else text."""
    if is_missing(value):
        return None
    if isinstance(value, datetime):  # includes pandas.Timestamp
        if (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    number = loose_number(value)
    if number is not None:
        return round(number, 6)
    return str(value)
