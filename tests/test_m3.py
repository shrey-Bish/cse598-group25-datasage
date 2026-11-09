"""Tests for the Milestone 3 changes: spelling merges into allowed labels, the coverage check before
analyze, the repeat warning, and compact memory. No model calls."""

import json

import pandas as pd

from datasage import checks
from datasage.agent import build_messages
from datasage.approval import AutoApprover
from datasage.session import Session
from datasage.tools import Dispatcher

RULES = {"Category": {"allowed": ["Electronics", "Furniture"]}, "Quantity": {"min": 1}}


def _session(rules=RULES):
    df = pd.DataFrame({
        "Category": ["Electronics", "Furnture", "Furnture", "Furniture", "electronics ", "Electronics"],
        "Quantity": [2, 3, -1, 4, 1, 5],
    })
    return Session(df, source="t.csv", request="units by category", rules=rules)


def _call(dispatcher, name, **args):
    return dispatcher.call(name, json.dumps(args))


def test_allowed_labels_find_misspelling_even_when_common():
    # "Furnture" is more common than "Furniture", so the frequency rule alone misses it.
    df = _session().current
    assert checks.check_label_variants(df, "Category")["possible_misspellings"] == {"Furniture": "Furnture"}
    result = checks.check_label_variants(df, "Category", ["Electronics", "Furniture"])
    assert result["possible_misspellings"] == {"Furnture": "Furniture"}
    assert result["case_or_space_variants"] == {"electronics ": "Electronics"}
    assert result["suggested_fix"]["mapping"] == {"electronics ": "Electronics", "Furnture": "Furniture"}


def test_required_checks_come_from_the_rules():
    d = Dispatcher(_session(), AutoApprover(), coverage=True)
    needed = d.required_checks({"group_by": ["Category"], "metric": "Quantity", "agg": "sum", "filters": []})
    assert ("check_duplicates", {}) in needed
    assert ("check_label_variants", {"column": "Category"}) in needed
    assert ("check_out_of_range", {"column": "Quantity", "minimum": 1, "maximum": None}) in needed
    assert ("check_numeric", {"column": "Quantity"}) in needed


def test_analyze_is_refused_once_per_open_finding_then_runs():
    d = Dispatcher(_session(), AutoApprover(), coverage=True)
    out, ok = _call(d, "analyze", group_by=["Category"], metric="Quantity", agg="sum")
    assert ok and out["analyze_refused"]
    assert {f["check"] for f in out["open_findings"]} == {"check_label_variants", "check_out_of_range"}
    assert {c["tool"] for c in out["checks_run_for_you"]} >= {"check_label_variants", "check_out_of_range"}
    # The skipped checks now count as findings (detection) and as run.
    assert ("label_variant", "Category") in d.session.issues
    # Asking again without fixing anything: each finding is flagged only once, so analyze now runs.
    out, ok = _call(d, "analyze", group_by=["Category"], metric="Quantity", agg="sum")
    assert ok and "result" in out


def test_fixed_findings_let_analyze_through():
    d = Dispatcher(_session(), AutoApprover(), coverage=True)
    _call(d, "normalize_labels", column="Category", mapping={"Furnture": "Furniture", "electronics ": "Electronics"},
          reason="merge into allowed labels")
    _call(d, "exclude_rows", rows=[2], reason="Quantity below the rules minimum of 1")
    out, ok = _call(d, "analyze", group_by=["Category"], metric="Quantity", agg="sum")
    assert ok and out["result"] == {"Electronics": 8.0, "Furniture": 7.0}
    assert d.coverage_refusals == 0


def test_rejected_fix_counts_as_resolved():
    class No(AutoApprover):
        def decide(self, *a):
            return False
    d = Dispatcher(_session(), No(), coverage=True)
    _call(d, "exclude_rows", rows=[2], reason="Quantity below 1")
    _call(d, "normalize_labels", column="Category", mapping={"Furnture": "Furniture"}, reason="typo")
    _call(d, "trim_whitespace", column="Category", reason="space")
    _call(d, "normalize_labels", column="Category", mapping={"electronics": "Electronics"}, reason="case")
    out, ok = _call(d, "analyze", group_by=["Category"], metric="Quantity", agg="sum")
    assert ok and "result" in out


def test_repeat_check_gets_a_warning():
    d = Dispatcher(_session(), AutoApprover(), coverage=True)
    first, _ = _call(d, "check_duplicates")
    second, _ = _call(d, "check_duplicates")
    assert "repeat_warning" not in first and "repeat_warning" in second


def test_compact_memory_keeps_recent_turns_and_adds_state():
    session = _session()
    head = [{"role": "system", "content": "sys"}, {"role": "user", "content": "first"}]
    turns = [[{"role": "assistant", "content": "", "tool_calls": [{"id": f"c{i}"}]},
              {"role": "tool", "tool_call_id": f"c{i}", "content": "x" * 1000}] for i in range(6)]
    full = build_messages(head, turns, session, "full")
    compact = build_messages(head, turns, session, "compact", keep=3)
    assert len(full) == 2 + 12 and len(compact) == 2 + 6
    assert compact[1]["content"].startswith("first") and "State so far" in compact[1]["content"]
    assert compact[2]["tool_calls"][0]["id"] == "c3"  # whole turns kept: each tool result follows its call
    assert build_messages(head, turns[:2], session, "compact", keep=3) == head + [m for t in turns[:2] for m in t]
