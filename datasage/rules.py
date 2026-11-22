"""Rules shared by checks, coverage and fixes so refunds follow one policy."""

from __future__ import annotations

import pandas as pd


def allows_negative_quantities(rules: dict, column: str | None) -> bool:
    """A column setting wins; the top-level shorthand applies only to Quantity/Qty columns.

    Only JSON true enables refunds. Strings such as "false" never relax a rule, and a global
    quantity setting must not change rules for unrelated columns such as Price or Age.
    """
    rule = rules.get(column, {})
    if isinstance(rule, dict) and "allow_negative_quantities" in rule:
        return rule["allow_negative_quantities"] is True
    return (str(column).strip().casefold() in {"quantity", "qty"}
            and rules.get("allow_negative_quantities") is True)


def outside_range(values: pd.Series, minimum=None, maximum=None, *, allow_negative_quantities=False) -> pd.Series:
    """Refunds bypass the lower bound only; zero, positive values and the upper bound still count."""
    bad = pd.Series(False, index=values.index)
    if minimum is not None:
        below = values < minimum
        if allow_negative_quantities:
            below &= values >= 0
        bad |= below
    if maximum is not None:
        bad |= values > maximum
    return bad.fillna(False)
