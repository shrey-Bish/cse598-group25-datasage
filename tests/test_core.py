"""Unit tests for the deterministic parts of DataSage (no model calls)."""

import pandas as pd
import pytest

from datasage import checks, fixes
from datasage.analyze import answers_match, run_analysis
from datasage.session import load_table
from datasage.validator import validate
from datasage.values import comparable, iso_date, loose_number, plain_number

SALES = "baseline/examples/messy_sales.csv"


@pytest.fixture
def sales():
    return load_table(SALES)


def test_value_parsing():
    assert plain_number("12.5") == 12.5 and plain_number("$12") is None
    assert loose_number("$1,200.00") == 1200.0 and loose_number("abc") is None
    assert iso_date("2026-02-30") is None and iso_date("2026-02-28").day == 28
    assert comparable("$1,200") == comparable(1200)


def test_load_keeps_raw_text_and_row_ids(sales):
    assert list(sales.index) == list(range(8))
    assert sales.at[5, "Date"] == "not-a-date"
    assert pd.isna(sales.at[7, "Region"])
    assert pd.api.types.is_numeric_dtype(sales["Revenue"])


def test_checks_find_planted_problems(sales):
    assert checks.check_duplicates(sales)["rows"] == [4]
    variants = checks.check_label_variants(sales, "Category")
    assert variants["case_or_space_variants"] == {"electronics": "Electronics", "accessories": "Accessories"}
    assert checks.check_dates(sales, "Date")["rows"] == [5]
    assert checks.check_numeric(sales, "Quantity")["negatives"]["rows"] == [6]


def test_misspellings_are_separate_from_case_variants():
    df = pd.DataFrame({"c": ["Furniture"] * 5 + ["Furnture", "furniture"]})
    result = checks.check_label_variants(df, "c")
    assert result["case_or_space_variants"] == {"furniture": "Furniture"}
    assert result["possible_misspellings"] == {"Furnture": "Furniture"}


def test_cross_column_and_safe_expressions():
    df = pd.DataFrame({"Q": [2, 3], "P": ["$10", "5"], "R": [20, 99]})
    assert checks.check_cross_column(df, "R", "Q * P")["rows"] == [1]
    with pytest.raises(ValueError):
        checks.evaluate_expression(df, "Q.__class__")
    with pytest.raises(ValueError):
        checks.evaluate_expression(df, "__import__('os')")


def test_fix_and_validator_agree(sales):
    result = fixes.normalize_labels(sales, "Category", {"electronics": "Electronics"})
    verdict = validate(sales, "normalize_labels", {"column": "Category", "mapping": {"electronics": "Electronics"}}, result)
    assert verdict["ok"] and result.cells_changed == 1


def test_validator_rejects_invented_labels(sales):
    result = fixes.normalize_labels(sales, "Category", {"electronics": "Gadgets"})
    verdict = validate(sales, "normalize_labels", {"column": "Category", "mapping": {"electronics": "Gadgets"}}, result)
    assert not verdict["ok"]


def test_validator_catches_undeclared_changes(sales):
    result = fixes.drop_duplicates(sales)
    result.df.loc[0, "Price"] = 1  # simulate a buggy fix touching another column
    verdict = validate(sales, "drop_duplicates", {}, result)
    assert not verdict["ok"]


def test_risk_tiers_are_set_by_code(sales):
    low = fixes.normalize_labels(sales, "Category", {"electronics": "Electronics"})
    high = fixes.normalize_labels(sales, "Category", {"electronics": "Accessories"})
    assert fixes.risk_of("normalize_labels", {"mapping": {"electronics": "Electronics"}}, low) == "low"
    assert fixes.risk_of("normalize_labels", {"mapping": {"electronics": "Accessories"}}, high) == "high"
    assert fixes.risk_of("exclude_rows", {}, fixes.exclude_rows(sales, [6])) == "high"
    assert fixes.risk_of("parse_dates", {}, fixes.parse_dates(sales, "Date")) == "medium"


def test_unknown_rows_are_refused(sales):
    with pytest.raises(ValueError):
        fixes.exclude_rows(sales, [99])


def test_analysis_requires_numbers_and_matches_reference(sales):
    clean = fixes.drop_duplicates(sales).df
    clean = fixes.normalize_labels(clean, "Category", {"electronics": "Electronics", "accessories": "Accessories"}).df
    answer = run_analysis(clean, ["Category"], "Revenue", "sum")["result"]
    assert answer == {"Accessories": 830.0, "Electronics": 2185.0}
    assert answers_match(answer, {"Accessories": 830.0, "Electronics": 2185.0})
    with pytest.raises(ValueError):
        run_analysis(sales, ["Revenue"], "Date", "sum")


def test_oracle_rejects_guessing_missing_values():
    from eval.oracle import OracleApprover
    from eval.scoring import all_bundles

    bundle = next(b for b in all_bundles("sales") if any(p["type"] == "missing" for p in b.planted))
    df = load_table(bundle.messy_path)
    column = next(p["column"] for p in bundle.planted if p["type"] == "missing")
    filled = fixes.fill_missing(df, column, "North")
    oracle = OracleApprover(bundle)
    assert oracle.decide("fill_missing", {}, "high", {"before": df, "after": filled.df}) is False


def test_number_grounding_flags_invented_numbers(sales):
    from datasage.agent import RunResult
    from datasage.report import ungrounded_numbers
    from datasage.session import Session

    session = Session(sales, "x", "What was total revenue by category?")
    trace = [{"event": "tool", "name": "analyze", "args": {}, "ok": True,
              "output": {"result": {"Accessories": 830.0, "Electronics": 2185.0}}},
             {"event": "tool", "name": "finish", "args": {"summary": "37.5"}, "ok": True, "output": {}}]
    run = RunResult(session=session, model="m", finished=True, stop_reason="finish", trace=trace,
                    final_summary="Accessories 830.0 and Electronics $2,185; growth 37.5%")
    assert ungrounded_numbers(run) == ["37.5"]
