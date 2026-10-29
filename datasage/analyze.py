"""Structured analysis: filter, group by, aggregate. Shared by DataSage, B0 and B1 so that every
system computes answers the same way once the data is clean.

Group keys that are missing are dropped. A group-by entry "Date:month" groups by the YYYY-MM of a
date column.
"""

from __future__ import annotations

import pandas as pd

from .values import iso_date

AGGREGATES = ("sum", "mean", "count", "median", "min", "max")


def _key_column(df: pd.DataFrame, spec: str) -> pd.Series:
    if spec.endswith(":month"):
        column = spec[: -len(":month")]
        if column not in df.columns:
            raise ValueError(f"column '{column}' not found")
        return df[column].map(lambda v: iso_date(v).strftime("%Y-%m") if iso_date(v) else pd.NA)
    if spec not in df.columns:
        raise ValueError(f"column '{spec}' not found; columns are {', '.join(map(str, df.columns))}")
    return df[spec]


def run_analysis(df: pd.DataFrame, group_by: list[str] | None, metric: str | None, agg: str,
                 filters: list[dict] | None = None) -> dict:
    if agg not in AGGREGATES:
        raise ValueError(f"agg must be one of {AGGREGATES}")
    data = df
    for f in filters or []:
        column, value = f["column"], f["value"]
        if column not in data.columns:
            raise ValueError(f"filter column '{column}' not found")
        data = data[data[column].astype(str) == str(value)]

    if agg != "count":
        if not metric or metric not in data.columns:
            raise ValueError(f"metric column '{metric}' not found")
        if not pd.api.types.is_numeric_dtype(data[metric]):
            raise ValueError(f"metric column '{metric}' is text, not numbers; convert it (cast_numeric) first")

    group_by = group_by or []
    if not group_by:
        value = len(data) if agg == "count" else getattr(data[metric], agg)()
        return {"group_by": [], "metric": metric, "agg": agg, "rows_used": int(len(data)),
                "result": {"all": None if pd.isna(value) else round(float(value), 4)}}

    keys = pd.DataFrame({g: _key_column(data, g) for g in group_by}, index=data.index)
    keep = keys.notna().all(axis=1)
    keys, data = keys[keep], data[keep]
    grouped = data.groupby([keys[g] for g in group_by], dropna=True)
    series = grouped.size() if agg == "count" else getattr(grouped[metric], agg)()
    result = {}
    for key, value in series.items():
        label = " | ".join(map(str, key)) if isinstance(key, tuple) else str(key)
        result[label] = round(float(value), 4)
    return {"group_by": group_by, "metric": metric, "agg": agg, "rows_used": int(len(data)), "result": result}


def answers_match(answer: dict | None, reference: dict, rel_tol: float = 0.005) -> bool:
    """Same group keys and every value within 0.5% (or 0.01 absolute)."""
    if not answer:
        return False
    if set(answer) != set(reference):
        return False
    for key, expected in reference.items():
        got = answer[key]
        if got is None or expected is None:
            if got != expected:
                return False
            continue
        if abs(got - expected) > max(0.01, rel_tol * abs(expected)):
            return False
    return True
