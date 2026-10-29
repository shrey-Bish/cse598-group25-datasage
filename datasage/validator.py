"""Validator: after each fix, compare the new version with the previous one.

It checks that the fix changed exactly what it said it would, that totals reconcile, and that the
related check now passes. A failed validation rolls the version back and is sent to the model.
"""

from __future__ import annotations

import pandas as pd

from . import checks
from .fixes import FixResult
from .values import comparable, normalize_label


def _changed_cells(before: pd.Series, after: pd.Series) -> int:
    return int(sum(comparable(a) != comparable(b) for a, b in zip(before, after)))


def validate(before: pd.DataFrame, tool: str, args: dict, result: FixResult) -> dict:
    after = result.df
    problems: list[str] = []

    removed = set(before.index.difference(after.index))
    if removed != set(result.rows_removed):
        problems.append(f"rows removed {sorted(removed)[:10]} do not match the rows the fix declared")
    if len(after.index.difference(before.index)):
        problems.append("the fix added rows that were not in the previous version")

    common = after.index.intersection(before.index)
    for column in before.columns:
        if column in result.touched_columns:
            continue
        if _changed_cells(before.loc[common, column], after.loc[common, column]):
            problems.append(f"column '{column}' changed but the fix did not declare it")

    for column in result.touched_columns:
        actual = _changed_cells(before.loc[common, column], after.loc[common, column])
        if actual != result.cells_changed:
            problems.append(f"{actual} cells changed in '{column}' but the fix reported {result.cells_changed}")

    # Totals reconcile for numeric columns the fix did not touch: before - removed = after.
    for column in before.columns:
        if column in result.touched_columns or not pd.api.types.is_numeric_dtype(before[column]):
            continue
        expected = before[column].sum() - before.loc[list(removed), column].sum()
        if abs(expected - after[column].sum()) > 1e-6 * max(1.0, abs(expected)):
            problems.append(f"total of '{column}' does not reconcile after the fix")

    recheck = _recheck(before, after, tool, args)
    problems.extend(recheck.pop("problems", []))
    return {"ok": not problems, "problems": problems, "recheck": recheck}


def _recheck(before: pd.DataFrame, after: pd.DataFrame, tool: str, args: dict) -> dict:
    """Re-run the check related to this fix and look for side effects."""
    column = args.get("column")
    out: dict = {"problems": []}
    if tool == "drop_duplicates":
        out["duplicates_left"] = checks.check_duplicates(after)["count"]
    elif tool in ("normalize_labels", "trim_whitespace"):
        existing = set(before[column].dropna().astype(str))
        new_labels = set(after[column].dropna().astype(str)) - existing
        stripped = {normalize_label(v) for v in existing}
        invented = [v for v in new_labels if normalize_label(v) not in stripped]
        if invented:
            out["problems"].append(f"the fix created labels that did not exist before: {invented[:5]}")
        result = checks.check_label_variants(after, column)
        out["label_variants_left"] = result["case_or_space_variants"]
        out["possible_misspellings_left"] = result["possible_misspellings"]
    elif tool == "cast_numeric":
        out["column_is_numeric"] = bool(pd.api.types.is_numeric_dtype(after[column]))
        if not out["column_is_numeric"]:
            out["problems"].append(f"'{column}' is still not numeric")
    elif tool == "parse_dates":
        out["invalid_dates_left"] = checks.check_dates(after, column)["count"]
    elif tool == "recompute_column":
        result = checks.check_cross_column(after.loc[args["rows"]], column, args["expression"])
        if result["count"]:
            out["problems"].append(f"{result['count']} recomputed rows still break {column} = {args['expression']}")
    elif tool == "fill_missing":
        out["missing_left"] = int(after[column].isna().sum())
    return out
