"""Fix tools. Each fix takes the current version and returns a new frame plus what it changed.

Fixes never touch the original table. The returned `FixResult` is what the validator checks and what
the change log and replay script are built from.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .checks import _require_column, evaluate_expression
from .values import comparable, iso_date, loose_number, normalize_label


@dataclass
class FixResult:
    df: pd.DataFrame
    touched_columns: list[str]
    rows_removed: list[int] = field(default_factory=list)
    cells_changed: int = 0
    new_missing: int = 0
    summary: str = ""
    code: str = ""


def _count_changed(before: pd.Series, after: pd.Series) -> int:
    return int(sum(comparable(a) != comparable(b) for a, b in zip(before, after)))


def _known_rows(df: pd.DataFrame, rows: list[int]) -> list[int]:
    unknown = [r for r in rows if r not in df.index]
    if unknown:
        raise ValueError(f"rows {unknown[:10]} are not in the current table (they may already be removed)")
    return list(dict.fromkeys(int(r) for r in rows))


def trim_whitespace(df: pd.DataFrame, column: str) -> FixResult:
    _require_column(df, column)
    new = df.copy()
    new[column] = new[column].map(lambda v: v.strip() if isinstance(v, str) else v)
    changed = _count_changed(df[column], new[column])
    return FixResult(new, [column], cells_changed=changed, summary=f"{column}: trimmed {changed} values",
                     code=f"df[{column!r}] = df[{column!r}].str.strip()")


def normalize_labels(df: pd.DataFrame, column: str, mapping: dict[str, str]) -> FixResult:
    _require_column(df, column)
    present = set(df[column].dropna().astype(str))
    missing = [k for k in mapping if k not in present]
    if missing:
        raise ValueError(f"values {missing} do not appear in column '{column}'")
    new = df.copy()
    new[column] = new[column].map(lambda v: mapping.get(v, v) if isinstance(v, str) else v)
    changed = _count_changed(df[column], new[column])
    return FixResult(new, [column], cells_changed=changed,
                     summary=f"{column}: merged {len(mapping)} label variant(s), {changed} cells",
                     code=f"df[{column!r}] = df[{column!r}].replace({mapping!r})")


def drop_duplicates(df: pd.DataFrame) -> FixResult:
    mask = df.duplicated(keep="first")
    removed = [int(i) for i in df.index[mask]]
    new = df[~mask].copy()
    return FixResult(new, [], rows_removed=removed, summary=f"removed {len(removed)} exact duplicate row(s)",
                     code="df = df.drop_duplicates(keep='first')")


def parse_dates(df: pd.DataFrame, column: str) -> FixResult:
    """Keep valid YYYY-MM-DD dates; values that are not valid dates become missing."""
    _require_column(df, column)
    new = df.copy()
    new[column] = new[column].map(lambda v: iso_date(v).isoformat() if iso_date(v) else pd.NA)
    new_missing = int(new[column].isna().sum() - df[column].isna().sum())
    changed = _count_changed(df[column], new[column])
    return FixResult(new, [column], cells_changed=changed, new_missing=new_missing,
                     summary=f"{column}: {new_missing} invalid date(s) set to missing",
                     code=f"df[{column!r}] = pd.to_datetime(df[{column!r}], format='%Y-%m-%d', errors='coerce').dt.strftime('%Y-%m-%d')")


def cast_numeric(df: pd.DataFrame, column: str) -> FixResult:
    """Convert a column to numbers, reading "$1,200.00" style text; non-numbers become missing."""
    _require_column(df, column)
    new = df.copy()
    new[column] = pd.to_numeric(new[column].map(loose_number))
    new_missing = int(new[column].isna().sum() - df[column].isna().sum())
    changed = int(sum(str(a) != str(b) and comparable(a) != comparable(b) for a, b in zip(df[column], new[column])))
    rewritten = int(sum(isinstance(v, str) for v in df[column].dropna()))
    return FixResult(new, [column], cells_changed=changed, new_missing=new_missing,
                     summary=f"{column}: converted to numbers ({rewritten} text values, {new_missing} became missing)",
                     code=f"df[{column!r}] = pd.to_numeric(df[{column!r}].astype(str).str.replace(r'[$, ]', '', regex=True), errors='coerce')")


def exclude_rows(df: pd.DataFrame, rows: list[int]) -> FixResult:
    rows = _known_rows(df, rows)
    new = df.drop(index=rows).copy()
    return FixResult(new, [], rows_removed=rows, summary=f"excluded {len(rows)} row(s): {rows[:10]}",
                     code=f"df = df.drop(index={rows!r})")


def recompute_column(df: pd.DataFrame, column: str, expression: str, rows: list[int]) -> FixResult:
    """Replace `column` with `expression` on the given rows only (e.g. Revenue = Quantity * Price)."""
    _require_column(df, column)
    rows = _known_rows(df, rows)
    values = evaluate_expression(df.loc[rows], expression)
    new = df.copy()
    if not pd.api.types.is_numeric_dtype(new[column]):
        new[column] = new[column].map(loose_number)
    new.loc[rows, column] = values.round(6)
    changed = _count_changed(df[column], new[column])
    written = [float(v) for v in new.loc[rows, column]]
    return FixResult(new, [column], cells_changed=changed,
                     summary=f"{column}: recomputed as {expression} on {len(rows)} row(s)",
                     code=f"df.loc[{rows!r}, {column!r}] = {written!r}  # {column} = {expression}")


def set_missing(df: pd.DataFrame, column: str, rows: list[int]) -> FixResult:
    _require_column(df, column)
    rows = _known_rows(df, rows)
    new = df.copy()
    new.loc[rows, column] = pd.NA
    new_missing = int(new[column].isna().sum() - df[column].isna().sum())
    return FixResult(new, [column], cells_changed=new_missing, new_missing=new_missing,
                     summary=f"{column}: set {len(rows)} value(s) to missing", code=f"df.loc[{rows!r}, {column!r}] = pd.NA")


def fill_missing(df: pd.DataFrame, column: str, value) -> FixResult:
    _require_column(df, column)
    mask = df[column].isna()
    new = df.copy()
    new.loc[mask, column] = value
    return FixResult(new, [column], cells_changed=int(mask.sum()),
                     summary=f"{column}: filled {int(mask.sum())} missing value(s) with {value!r}",
                     code=f"df[{column!r}] = df[{column!r}].fillna({value!r})")


FIXES = {
    "trim_whitespace": trim_whitespace,
    "normalize_labels": normalize_labels,
    "drop_duplicates": drop_duplicates,
    "parse_dates": parse_dates,
    "cast_numeric": cast_numeric,
    "exclude_rows": exclude_rows,
    "recompute_column": recompute_column,
    "set_missing": set_missing,
    "fill_missing": fill_missing,
}


def risk_of(tool: str, args: dict, result: FixResult) -> str:
    """Risk tier decided by code from the fix type and its actual effect, never by the model."""
    if tool == "trim_whitespace":
        return "low"
    if tool == "normalize_labels":
        same = all(normalize_label(k) == normalize_label(v) for k, v in args["mapping"].items())
        return "low" if same else "high"
    if tool in ("parse_dates", "cast_numeric"):
        return "low" if result.new_missing == 0 else "medium"
    if tool == "drop_duplicates":
        return "medium"
    return "high"
