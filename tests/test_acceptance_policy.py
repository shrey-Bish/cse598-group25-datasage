"""The acceptance test's approval policy decides each kind of fix as docs/final/checks/acceptance/decision_policy.md says.

Offline: small synthetic tables and the committed rules files; no model calls, no API key. Writes only to tmp_path.
"""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
ACCEPTANCE = REPO / "docs" / "final" / "checks" / "acceptance"
_spec = importlib.util.spec_from_file_location("acceptance_policy_approver", ACCEPTANCE / "policy_approver.py")
pa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pa)

SALES_RULES = REPO / "eval" / "datasets" / "sales-test" / "salest_00" / "rules.json"
APPROVERS = {  # who -> (profile, rules file)
    "P": ("procurement", ACCEPTANCE / "procurement_ledger" / "rules.json"),
    "S": ("support", ACCEPTANCE / "support_register" / "rules.json"),
    "T": ("sales_table", SALES_RULES),
    "H": ("penguins_table", REPO / "eval" / "datasets" / "penguins-heldout" / "penguinsh_00" / "rules.json"),
}
NAN = float("nan")
FRAMES = {
    "proc": pd.DataFrame({"OrderID": [1, 2, 2, 3], "Department": ["Finanace", "finance ", "finance ", "Research"],
                          "Quantity": [2, 0, 0, 3], "UnitCost": ["$10.00", "5", "5", "4"], "LineTotal": [20, 0, 0, 99]}),
    "sup": pd.DataFrame({"TicketID": [1, 2, 3], "Team": ["Operatons", "Accounts", "Accounts"],
                         "Channel": ["Email", "Fax?", "Emial"], "OpenedDate": ["2026-10-01", "not-recorded", "2026-11-02"],
                         "ResolutionMinutes": ["1,200", "-5", "30"]}),
    "sales": pd.DataFrame({"Order_ID": [1, 2, 3], "Category": ["Electronis", "Furnitur", "Toys"], "Quantity": [2, -1, 3],
                           "Price": [10, 5, 4], "Revenue": [20, -5, 50]}),
    "peng": pd.DataFrame({"penguin_id": [1, 2], "island": ["Biscoe", "Dreem"], "bill_length_mm": [39.1, 99.0],
                          "sex": [None, "male"]}),
    "reg": pd.DataFrame({"Order_ID": [1, 2, 3], "Region": ["Wst", "Est", "Nrth"], "Quantity": [1, -1, 0],
                         "Price": [1, 1, 1], "Revenue": [1, -1, 0]}),
    "finn": pd.DataFrame({"Department": ["Finnance"]}),
    "num_b": pd.DataFrame({"UnitCost": ["$10.00", "twelve", "5", "1.2.3"]}),
    "num_a": pd.DataFrame({"UnitCost": [10.0, NAN, 5.0, NAN]}),
    "bad_b": pd.DataFrame({"UnitCost": ["5"]}),
    "bad_a": pd.DataFrame({"UnitCost": [NAN]}),
    "pdat": pd.DataFrame({"OrderID": ["A1", "A2", "A3", "A4", "A5"],
                          "OrderDate": ["2026-13-45", "09/10/2026", "2026-10-01", "soon", "2026-09-03T00:00:00"],
                          "Department": ["Xyzzy", "Finanace", "Finance", "R&D dept", "Research"],
                          "UnitCost": ["abc", "-5", "$1,200.50", "n/a", "7"]}),
    "sales2": pd.DataFrame({"Category": ["Toys", "Electronis"], "Quantity": [2, 3]}),
    "refund": pd.DataFrame({"Quantity": [2, -2], "Price": [5, 5], "Revenue": [10, 99]}),
}


def make_approver(who: str, tmp_path: Path):
    if who == "N":  # the sales rules with allow_negative_quantities set (change 3)
        rules = json.loads(SALES_RULES.read_text(encoding="utf-8"))
        rules["allow_negative_quantities"] = True
        path = tmp_path / "rules_refunds.json"
        path.write_text(json.dumps(rules), encoding="utf-8")
        profile = "sales_table"
    else:
        profile, path = APPROVERS[who]
    return pa.PolicyApprover(who, profile, path, tmp_path / "decisions.jsonl")


def preview(before: str, after: str | None = None, removed=()) -> dict:
    frame = FRAMES[before]
    return {"summary": "test", "rows_removed": list(removed), "cells_changed": 0, "before": frame,
            "after": FRAMES[after] if after else frame}


def case(id_, who, tool, args, before, expected, *, after=None, removed=()):
    return pytest.param(who, tool, args, before, after, removed, expected, id=id_)


CASES = [
    # ---- first draft (32) ----------------------------------------------------------------------------------------
    case("P-labels-named-misspelling", "P", "normalize_labels",
         {"column": "Department", "mapping": {"Finanace": "Finance", "finance ": "Finance"}}, "proc", True),
    case("P-labels-wrong-target", "P", "normalize_labels", {"column": "Department", "mapping": {"Research": "Finance"}}, "proc", False),
    case("S-labels-named-misspelling", "S", "normalize_labels", {"column": "Team", "mapping": {"Operatons": "Operations"}}, "sup", True),
    case("S-labels-unnamed-misspelling", "S", "normalize_labels", {"column": "Channel", "mapping": {"Emial": "Email"}}, "sup", False),
    case("T-labels-near", "T", "normalize_labels",
         {"column": "Category", "mapping": {"Electronis": "Electronics", "Furnitur": "Furniture"}}, "sales", True),
    case("T-labels-far", "T", "normalize_labels", {"column": "Category", "mapping": {"Toys": "Office Supplies"}}, "sales", False),
    case("H-labels-near", "H", "normalize_labels", {"column": "island", "mapping": {"Dreem": "Dream"}}, "peng", True),
    case("P-duplicates-copy", "P", "drop_duplicates", {}, "proc", True, removed=[2]),
    case("P-duplicates-not-copy", "P", "drop_duplicates", {}, "proc", False, removed=[3]),
    case("P-dates-ambiguous-order", "P", "parse_dates", {"column": "OrderDate", "date_order": "dmy"}, "proc", False),
    case("P-cast-nothing-blanked", "P", "cast_numeric", {"column": "UnitCost"}, "proc", False),
    case("P-exclude-range-break", "P", "exclude_rows", {"rows": [1]}, "proc", True, removed=[1]),
    case("P-exclude-includes-valid-row", "P", "exclude_rows", {"rows": [0, 1]}, "proc", False, removed=[0, 1]),
    case("S-exclude-where-negative-minutes", "S", "exclude_where",
         {"column": "ResolutionMinutes", "minimum": 0}, "sup", True, removed=[1]),
    case("S-exclude-negative-minutes", "S", "exclude_rows", {"rows": [1]}, "sup", True, removed=[1]),
    case("S-exclude-valid-row", "S", "exclude_rows", {"rows": [2]}, "sup", False, removed=[2]),
    case("P-recompute-broken-row", "P", "recompute_column",
         {"column": "LineTotal", "expression": "Quantity * UnitCost", "rows": [3]}, "proc", True),
    case("P-recompute-row-already-right", "P", "recompute_column",
         {"column": "LineTotal", "expression": "Quantity * UnitCost", "rows": [0]}, "proc", False),
    case("P-recompute-input-out-of-range", "P", "recompute_column",
         {"column": "LineTotal", "expression": "Quantity * UnitCost", "rows": [1]}, "proc", False),
    case("T-recompute-broken-row", "T", "recompute_column",
         {"column": "Revenue", "expression": "Quantity*Price", "rows": [2]}, "sales", True),
    case("T-recompute-negative-quantity", "T", "recompute_column",
         {"column": "Revenue", "expression": "Quantity * Price", "rows": [1]}, "sales", False),
    case("S-recompute-no-formula", "S", "recompute_column",
         {"column": "ResolutionMinutes", "expression": "1", "rows": [1]}, "sup", False),
    case("S-blank-not-recorded-date", "S", "set_missing", {"column": "OpenedDate", "rows": [1]}, "sup", True),
    case("S-blank-valid-date", "S", "set_missing", {"column": "OpenedDate", "rows": [0]}, "sup", False),
    case("S-blank-unknown-channel", "S", "set_missing", {"column": "Channel", "rows": [1]}, "sup", True),
    case("S-blank-possible-misspelling", "S", "set_missing", {"column": "Channel", "rows": [2]}, "sup", False),
    case("P-blank-allowed-label", "P", "set_missing", {"column": "Department", "rows": [3]}, "proc", False),
    case("S-fill", "S", "fill_missing", {"column": "Channel", "value": "Email"}, "sup", False),
    case("H-fill", "H", "fill_missing", {"column": "sex", "value": "male"}, "peng", False),
    case("H-exclude-range-break", "H", "exclude_rows", {"rows": [1]}, "peng", True, removed=[1]),
    case("P-trim-not-covered", "P", "trim_whitespace", {"column": "Department"}, "proc", False),
    case("P-unknown-tool", "P", "made_up_tool", {}, "proc", False),
    # ---- change 1: T/H nearest label, at most 2 edits and strictly closest; P/S strict (5) ---------------------
    case("T-labels-nearest", "T", "normalize_labels", {"column": "Region", "mapping": {"Wst": "West"}}, "reg", True),
    case("T-labels-not-nearest", "T", "normalize_labels", {"column": "Region", "mapping": {"Wst": "East"}}, "reg", False),
    case("T-labels-tie", "T", "normalize_labels", {"column": "Region", "mapping": {"Est": "East"}}, "reg", False),
    case("T-labels-nearest-2", "T", "normalize_labels", {"column": "Region", "mapping": {"Nrth": "North"}}, "reg", True),
    case("P-labels-strict", "P", "normalize_labels", {"column": "Department", "mapping": {"Finnance": "Finance"}}, "finn", False),
    # ---- change 2: blank only unreadable cells (19) --------------------------------------------------------------
    case("P-cast-unreadable", "P", "cast_numeric", {"column": "UnitCost"}, "num_b", True, after="num_a"),
    case("P-cast-readable", "P", "cast_numeric", {"column": "UnitCost"}, "bad_b", False, after="bad_a"),
    case("P-cast-removes-row", "P", "cast_numeric", {"column": "UnitCost"}, "num_b", False, after="num_a", removed=[0]),
    case("P-cast-label-column", "P", "cast_numeric", {"column": "Department"}, "pdat", False),
    case("P-blank-unreadable-number", "P", "set_missing", {"column": "UnitCost", "rows": [0]}, "pdat", True),
    case("P-blank-negative-number", "P", "set_missing", {"column": "UnitCost", "rows": [1]}, "pdat", False),
    case("P-blank-currency-number", "P", "set_missing", {"column": "UnitCost", "rows": [2]}, "pdat", False),
    case("P-blank-mixed", "P", "set_missing", {"column": "UnitCost", "rows": [0, 1]}, "pdat", False),
    case("P-blank-unreadable-dates", "P", "set_missing", {"column": "OrderDate", "rows": [0, 3]}, "pdat", True),
    case("P-blank-ambiguous-date", "P", "set_missing", {"column": "OrderDate", "rows": [1]}, "pdat", False),
    case("P-blank-timestamp", "P", "set_missing", {"column": "OrderDate", "rows": [4]}, "pdat", False),
    case("P-blank-unreadable-labels", "P", "set_missing", {"column": "Department", "rows": [0, 3]}, "pdat", True),
    case("P-blank-named-misspelling", "P", "set_missing", {"column": "Department", "rows": [1]}, "pdat", False),
    case("P-blank-untyped-column", "P", "set_missing", {"column": "OrderID", "rows": [0]}, "pdat", False),
    case("P-blank-removes-row", "P", "set_missing", {"column": "UnitCost", "rows": [0]}, "pdat", False, removed=[0]),
    case("T-blank-unreadable-label", "T", "set_missing", {"column": "Category", "rows": [0]}, "sales2", True),
    case("T-blank-possible-misspelling", "T", "set_missing", {"column": "Category", "rows": [1]}, "sales2", False),
    case("S-blank-unknown-channel-again", "S", "set_missing", {"column": "Channel", "rows": [1]}, "sup", True),
    case("S-fill-date", "S", "fill_missing", {"column": "OpenedDate", "value": "2026-10-01"}, "sup", False),
    # ---- change 3: allow_negative_quantities keeps negative quantities in range (4) -----------------------------
    case("N-exclude-refund", "N", "exclude_rows", {"rows": [1]}, "reg", False, removed=[1]),
    case("N-exclude-zero-quantity", "N", "exclude_rows", {"rows": [2]}, "reg", True, removed=[2]),
    case("T-exclude-negative-without-flag", "T", "exclude_rows", {"rows": [1]}, "reg", True, removed=[1]),
    case("N-recompute-refund-input", "N", "recompute_column",
         {"column": "Revenue", "expression": "Quantity * Price", "rows": [1]}, "refund", True),
]


def test_case_count():
    assert len(CASES) == 60


@pytest.mark.parametrize("who,tool,args,before,after,removed,expected", CASES)
def test_policy_decision(tmp_path, who, tool, args, before, after, removed, expected):
    approver = make_approver(who, tmp_path)
    decided = approver.decide(tool, {**args, "reason": "test"}, "high", preview(before, after, removed))
    assert decided == expected


def test_every_decision_is_logged(tmp_path):
    approver = make_approver("P", tmp_path)
    approver.decide("drop_duplicates", {"reason": "r"}, "medium", preview("proc", removed=[2]))
    approver.decide("fill_missing", {"column": "Quantity", "value": 1, "reason": "r"}, "high", preview("proc"))
    lines = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["decision"] for entry in lines] == ["approved", "rejected"]
    assert set(lines[0]) == {"case", "tool", "risk", "column", "rows", "cells_changed", "summary", "decision", "rule",
                             "why", "args", "agent_reason"}
    assert lines[0]["rule"] == "business_rules.md:17" and lines[0]["rows"] == [2]
    assert lines[1]["rule"] == "not covered"


def test_approver_finds_the_repo_root():
    assert pa.REPO == REPO
