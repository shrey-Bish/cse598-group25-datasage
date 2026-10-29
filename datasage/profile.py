"""Deterministic profile of a table. The model sees this and a few sample rows, never the full table."""

from __future__ import annotations

import pandas as pd

from .values import iso_date, is_missing, loose_number, normalize_label, plain_number


def _text_column_stats(values: pd.Series) -> dict:
    texts = [str(v) for v in values]
    n = max(len(texts), 1)
    loose = sum(loose_number(t) is not None for t in texts)
    plain = sum(plain_number(t) is not None for t in texts)
    dates = sum(iso_date(t) is not None for t in texts)
    groups: dict[str, set[str]] = {}
    for t in texts:
        groups.setdefault(normalize_label(t), set()).add(t)
    stats = {
        "numeric_parse_rate": round(loose / n, 3),
        "numbers_written_as_text": loose - plain,
        "iso_date_rate": round(dates / n, 3),
        "values_with_extra_spaces": sum(t != t.strip() for t in texts),
        "case_or_space_variant_groups": sum(len(forms) > 1 for forms in groups.values()),
    }
    distinct = values.nunique()
    if distinct <= 25:
        stats["value_counts"] = {str(k): int(v) for k, v in values.value_counts().items()}
    return stats


def profile(df: pd.DataFrame) -> dict:
    columns = []
    for name in df.columns:
        series = df[name]
        values = series.dropna()
        info = {
            "column": name,
            "type": "number" if pd.api.types.is_numeric_dtype(series) else "text",
            "missing": int(series.isna().sum()),
            "distinct": int(values.nunique()),
        }
        if info["type"] == "number":
            info.update(
                min=float(values.min()) if len(values) else None,
                max=float(values.max()) if len(values) else None,
                negatives=int((values < 0).sum()),
            )
        else:
            info.update(_text_column_stats(values))
        columns.append(info)
    return {"rows": len(df), "exact_duplicate_rows": int(df.duplicated().sum()), "columns": columns}


def sample_rows(df: pd.DataFrame, limit: int = 12) -> list[dict]:
    """Pick rows that show unusual values first, then fill with ordinary rows."""
    unusual: list[int] = []
    for idx, row in df.iterrows():
        for name, value in row.items():
            if is_missing(value):
                unusual.append(idx)
                break
            if isinstance(value, str):
                if value != value.strip():
                    unusual.append(idx)
                    break
                if pd.api.types.is_numeric_dtype(df[name]) is False and loose_number(value) is not None and plain_number(value) is None:
                    unusual.append(idx)
                    break
            elif isinstance(value, (int, float)) and value < 0:
                unusual.append(idx)
                break
    picked = list(dict.fromkeys(unusual[: limit // 2] + list(df.index[:limit])))[:limit]
    out = []
    for idx in picked:
        row = {"row": int(idx)}
        row.update({k: (None if is_missing(v) else v) for k, v in df.loc[idx].items()})
        out.append(row)
    return out
