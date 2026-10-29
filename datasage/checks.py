"""Check tools. Each check reads the current version and returns a short, model-facing result.

Issue types: missing, duplicates, label_variant, invalid_date, text_number, negative,
out_of_range, cross_column.
"""

from __future__ import annotations

import ast
import difflib
import operator

import pandas as pd

from .values import iso_date, loose_number, normalize_label, plain_number

MAX_ROWS_SHOWN = 10


def _rows(index) -> list[int]:
    return [int(i) for i in list(index)[:MAX_ROWS_SHOWN]]


def _require_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise ValueError(f"column '{column}' not found; columns are {', '.join(map(str, df.columns))}")


def check_missing(df: pd.DataFrame, column: str) -> dict:
    _require_column(df, column)
    mask = df[column].isna()
    return {"type": "missing", "column": column, "count": int(mask.sum()), "rows": _rows(df.index[mask])}


def check_duplicates(df: pd.DataFrame) -> dict:
    mask = df.duplicated(keep="first")
    return {
        "type": "duplicates",
        "column": "*",
        "count": int(mask.sum()),
        "rows": _rows(df.index[mask]),
        "note": "rows listed are later copies of an earlier identical row",
    }


def check_label_variants(df: pd.DataFrame, column: str) -> dict:
    """Case/space variants (safe to merge) and close spellings of a more common label (risky)."""
    _require_column(df, column)
    values = df[column].dropna().astype(str)
    counts = values.value_counts()
    groups: dict[str, list[str]] = {}
    for value in counts.index:
        groups.setdefault(normalize_label(value), []).append(value)

    case_space = {}
    for forms in groups.values():
        if len(forms) > 1:
            canonical = max(forms, key=lambda f: (f == f.strip(), counts[f]))
            for f in forms:
                if f != canonical:
                    case_space[f] = canonical

    canonical_labels = [max(forms, key=lambda f: (f == f.strip(), counts[f])) for forms in groups.values()]
    close = {}
    for label in canonical_labels:
        others = [o for o in canonical_labels if o != label and counts.get(o, 0) > counts.get(label, 0)]
        match = difflib.get_close_matches(normalize_label(label), [normalize_label(o) for o in others], n=1, cutoff=0.8)
        if match:
            target = next(o for o in others if normalize_label(o) == match[0])
            close[label] = target

    affected = values[values.isin(list(case_space) + list(close))]
    return {
        "type": "label_variant",
        "column": column,
        "count": int(len(affected)),
        "rows": _rows(affected.index),
        "case_or_space_variants": case_space,
        "possible_misspellings": close,
        "note": "case/space variants are low risk to merge; misspellings need approval",
    }


def check_dates(df: pd.DataFrame, column: str) -> dict:
    _require_column(df, column)
    values = df[column].dropna()
    bad = values[[iso_date(v) is None for v in values]]
    return {
        "type": "invalid_date",
        "column": column,
        "count": int(len(bad)),
        "rows": _rows(bad.index),
        "examples": [str(v) for v in bad.head(5)],
        "valid_iso_dates": int(len(values) - len(bad)),
    }


def check_numeric(df: pd.DataFrame, column: str) -> dict:
    """Numbers stored as text, values that are not numbers at all, and negative numbers."""
    _require_column(df, column)
    values = df[column].dropna()
    text_numbers = values[[plain_number(v) is None and loose_number(v) is not None for v in values]]
    not_numbers = values[[loose_number(v) is None for v in values]]
    parsed = values.map(loose_number).dropna()
    negatives = parsed[parsed < 0]
    return {
        "type": "numeric",
        "column": column,
        "text_numbers": {"count": int(len(text_numbers)), "rows": _rows(text_numbers.index), "examples": [str(v) for v in text_numbers.head(3)]},
        "not_numbers": {"count": int(len(not_numbers)), "rows": _rows(not_numbers.index), "examples": [str(v) for v in not_numbers.head(3)]},
        "negatives": {"count": int(len(negatives)), "rows": _rows(negatives.index)},
        "column_is_numeric": bool(pd.api.types.is_numeric_dtype(df[column])),
    }


def check_out_of_range(df: pd.DataFrame, column: str, minimum: float | None, maximum: float | None) -> dict:
    _require_column(df, column)
    parsed = df[column].map(loose_number).dropna()
    mask = pd.Series(False, index=parsed.index)
    if minimum is not None:
        mask |= parsed < minimum
    if maximum is not None:
        mask |= parsed > maximum
    bad = parsed[mask]
    return {
        "type": "out_of_range",
        "column": column,
        "range": [minimum, maximum],
        "count": int(len(bad)),
        "rows": _rows(bad.index),
        "examples": [float(v) for v in bad.head(5)],
    }


_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def evaluate_expression(df: pd.DataFrame, expression: str) -> pd.Series:
    """Evaluate arithmetic over columns (e.g. "Quantity * Price"), reading numbers written as text.

    Only column names, numbers and + - * / are accepted; the model writes these expressions, so
    nothing else from Python is reachable.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as err:
        raise ValueError(f"could not parse expression {expression!r}: {err.msg}") from None

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _BINARY[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            _require_column(df, node.id)
            return df[node.id].map(loose_number).astype(float)
        raise ValueError("expression may only use column names, numbers and + - * /")

    result = walk(tree)
    if not isinstance(result, pd.Series):
        result = pd.Series(float(result), index=df.index)
    return result


def check_cross_column(df: pd.DataFrame, column: str, expression: str) -> dict:
    """Rows where `column` does not equal `expression` (e.g. Revenue vs Quantity * Price)."""
    _require_column(df, column)
    expected = evaluate_expression(df, expression)
    actual = df[column].map(loose_number)
    both = actual.notna() & expected.notna()
    tolerance = 0.005 * expected.abs() + 1e-6
    mask = both & ((actual - expected).abs() > tolerance)
    bad = df.index[mask]
    return {
        "type": "cross_column",
        "column": column,
        "rule": f"{column} = {expression}",
        "count": int(mask.sum()),
        "rows": _rows(bad),
        "examples": [{"row": int(i), "actual": float(actual[i]), "expected": float(expected[i])} for i in list(bad)[:5]],
    }


def record_findings(session, result: dict) -> None:
    """Store non-empty findings so the final report (and the detection metric) can list them."""
    if result["type"] == "numeric":
        col = result["column"]
        session.record_issue("text_number", col, result["text_numbers"]["count"], {"rows": result["text_numbers"]["rows"]})
        session.record_issue("negative", col, result["negatives"]["count"], {"rows": result["negatives"]["rows"]})
        return
    session.record_issue(result["type"], result["column"], result["count"], {"rows": result.get("rows", [])})
