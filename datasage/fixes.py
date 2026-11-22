"""Fix tools. Each fix takes the current version and returns a new frame plus what it changed.

Fixes never touch the original table. The returned `FixResult` is what the validator checks and what
the change log and replay script are built from.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .checks import _require_column, evaluate_expression
from .rules import outside_range
from .values import comparable, date_options, iso_date, is_missing, loose_number, normalize_label


@dataclass
class FixResult:
    df: pd.DataFrame
    touched_columns: list[str]
    rows_removed: list[int] = field(default_factory=list)
    cells_changed: int = 0
    new_missing: int = 0
    summary: str = ""
    code: str = ""
    cell_changes: list[dict] = field(default_factory=list)


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


def parse_dates(df: pd.DataFrame, column: str, date_order: str | None = None) -> FixResult:
    """Normalize clear dates, blank unreadable ones, and leave ambiguity until an order is approved."""
    _require_column(df, column)
    if date_order not in (None, "dmy", "mdy"):
        raise ValueError("date_order must be dmy, mdy or None")
    new = df.copy()
    new[column] = new[column].astype(object)
    details, code = [], [f"df[{column!r}] = df[{column!r}].astype(object)"]
    ambiguous_left = 0
    for row, value in df[column].items():
        if is_missing(value):
            continue
        ambiguous = len(set(date_options(value).values())) > 1
        if ambiguous and date_order is None:
            ambiguous_left += 1
            continue
        parsed = iso_date(value, date_order)
        after = parsed.isoformat() if parsed else pd.NA
        new.at[row, column] = after
        if comparable(value) != comparable(after):
            details.append({"row": int(row), "column": column, "before": str(value),
                            "after": parsed.isoformat() if parsed else None, "ambiguous": ambiguous})
            literal = repr(after) if parsed else "pd.NA"
            code.append(f"df.at[{int(row)}, {column!r}] = {literal}")
    new_missing = int(new[column].isna().sum() - df[column].isna().sum())
    changed = _count_changed(df[column], new[column])
    converted = sum(c["after"] is not None for c in details)
    return FixResult(new, [column], cells_changed=changed, new_missing=new_missing,
                     summary=f"{column}: converted {converted} date(s), {new_missing} invalid date(s) set to missing; "
                             f"{ambiguous_left} ambiguous date(s) left unchanged" +
                             (f" (approved order: {date_order})" if any(c["ambiguous"] for c in details) else ""),
                     code="\n".join(code), cell_changes=details)


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


def exclude_where(df: pd.DataFrame, column: str, minimum: float | None = None, maximum: float | None = None,
                  *, allow_negative_quantities: bool = False) -> FixResult:
    """Remove every row whose number in `column` is below `minimum` or above `maximum`.

    Unlike exclude_rows it does not need row ids, so it covers all rule-breaking rows however many there are.
    Values that are not numbers are left alone (check_numeric / cast_numeric handle those).
    """
    _require_column(df, column)
    if minimum is None and maximum is None:
        raise ValueError("give minimum, maximum or both")
    values = df[column].map(loose_number)
    mask = outside_range(values, minimum, maximum, allow_negative_quantities=allow_negative_quantities)
    rows = [int(r) for r in df.index[mask]]
    new = df.drop(index=rows).copy()
    bound = " and ".join(p for p in (f"below {minimum:g}" if minimum is not None else "",
                                     f"above {maximum:g}" if maximum is not None else "") if p)
    lower = (f"((v >= 0) & (v < {minimum!r}))" if allow_negative_quantities else f"(v < {minimum!r})")
    cond = " | ".join(c for c in (lower if minimum is not None else "",
                                  f"(v > {maximum!r})" if maximum is not None else "") if c)
    return FixResult(new, [], rows_removed=rows, summary=f"excluded {len(rows)} row(s) where {column} is {bound}" +
                     (" (negative quantities kept as refunds)" if allow_negative_quantities else ""),
                     code=f"v = df[{column!r}].astype(str).str.strip().str.replace(r'[$, ]', '', regex=True)\n"
                          f"numeric = df[{column!r}].map(lambda x: isinstance(x, (int, float)) and not isinstance(x, bool))\n"
                          "v = pd.to_numeric(v.where(v.str.fullmatch(r'[-+]?\\d+(\\.\\d+)?') | numeric), errors='coerce')\n"
                          f"df = df[~({cond}).fillna(False)]")


def recompute_column(df: pd.DataFrame, column: str, expression: str, rows: list[int]) -> FixResult:
    """Replace `column` with `expression` on the given rows only (e.g. Revenue = Quantity * Price)."""
    _require_column(df, column)
    rows = _known_rows(df, rows)
    values = evaluate_expression(df.loc[rows], expression)
    new = df.copy()
    converted = not pd.api.types.is_numeric_dtype(new[column])
    if converted:
        new[column] = new[column].map(loose_number)
    new.loc[rows, column] = values.round(6)
    changed = _count_changed(df[column], new[column])
    written = [float(v) for v in new.loc[rows, column]]
    return FixResult(new, [column], cells_changed=changed,
                     summary=f"{column}: recomputed as {expression} on {len(rows)} row(s)",
                     code=(f"df[{column!r}] = df[{column!r}].map(loose_number)  # the column held text; read it as numbers first\n"
                           if converted else "") +
                          f"df.loc[{rows!r}, {column!r}] = pd.Series({written!r}, index={rows!r})  # {column} = {expression}")


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
    "exclude_where": exclude_where,
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
    if tool == "parse_dates":
        return "medium" if any(c["ambiguous"] for c in result.cell_changes) else "low"
    if tool == "cast_numeric":
        return "low" if result.new_missing == 0 else "medium"
    if tool == "drop_duplicates":
        return "medium"
    return "high"
