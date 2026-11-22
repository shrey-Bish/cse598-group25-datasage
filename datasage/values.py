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
_ISO_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?$"
)
_YEAR_FIRST = re.compile(r"^(\d{4})([/.-])(\d{1,2})\2(\d{1,2})$")
_LOCAL_DATE = re.compile(r"^(\d{1,2})([/.-])(\d{1,2})\2(\d{4})$")
_MONTHS = {name: n for n, pair in enumerate((
    ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
    ("may", "may"), ("jun", "june"), ("jul", "july"), ("aug", "august"),
    ("sep", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december"),
), 1) for name in pair}


def date_options(value) -> dict[str, date]:
    """Calendar-valid interpretations of a numeric year-last date; never guess the order."""
    if is_missing(value):
        return {}
    match = _LOCAL_DATE.fullmatch(str(value).strip())
    if not match:
        return {}
    first, second, year = int(match[1]), int(match[3]), int(match[4])
    options = {}
    for order, month, day in (("dmy", second, first), ("mdy", first, second)):
        try:
            options[order] = date(year, month, day)
        except ValueError:
            pass
    return options


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


def iso_date(value, date_order: str | None = None) -> date | None:
    """Read clear dates/timestamps without inference; ambiguous dates need an explicit order.

    Timestamps keep their written calendar date, without a timezone conversion. Numeric year-last
    dates are clear only when exactly one interpretation is valid (or both give the same date).
    """
    if date_order not in (None, "dmy", "mdy"):
        raise ValueError("date_order must be dmy, mdy or None")
    if is_missing(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    match = _ISO_DATE.fullmatch(text)
    try:
        if match:
            return date(int(match[1]), int(match[2]), int(match[3]))
        year_first = _YEAR_FIRST.fullmatch(text)
        if year_first:
            return date(int(year_first[1]), int(year_first[3]), int(year_first[4]))
        if _ISO_TIMESTAMP.fullmatch(text):
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        named = re.fullmatch(r"(\d{1,2})[- ]([A-Za-z]+)[- ](\d{4})", text)
        if named and named[2].lower() in _MONTHS:
            return date(int(named[3]), _MONTHS[named[2].lower()], int(named[1]))
        named = re.fullmatch(r"([A-Za-z]+) (\d{1,2}),? (\d{4})", text)
        if named and named[1].lower() in _MONTHS:
            return date(int(named[3]), _MONTHS[named[1].lower()], int(named[2]))
    except ValueError:
        return None
    options = date_options(value)
    if len(set(options.values())) == 1:
        return next(iter(options.values()))
    return options.get(date_order)


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
