"""M2: refund rules govern model checks, coverage checks, bulk fixes and replay alike."""

import json

import pandas as pd
import pytest

from datasage.approval import AutoApprover, RejectApprover
from datasage.fixes import exclude_where
from datasage.rules import allows_negative_quantities
from datasage.session import Session
from datasage.tools import Dispatcher
from datasage.validator import validate


def _dispatcher(setting=None, *, approver=None, values=None, rules=None):
    df = pd.DataFrame({"Id": range(len(values or [-3, 2, 4])), "Quantity": values or [-3, 2, 4]})
    if rules is None:
        rule = {"min": 1, "max": 10}
        if setting is not None:
            rule["allow_negative_quantities"] = setting
        rules = {"Quantity": rule}
    return Dispatcher(Session(df, "t.csv", "net quantity", rules), approver or AutoApprover(), coverage=True)


def _call(d, name, **args):
    out, ok = d.call(name, json.dumps(args))
    assert ok, out
    return out


@pytest.mark.parametrize("setting", [None, False, "false", "true", 1])
def test_missing_false_or_nonboolean_settings_keep_existing_policy(setting):
    d = _dispatcher(setting)
    numeric = _call(d, "check_numeric", column="Quantity")
    assert numeric["negatives"]["rows"] == [0]
    result = _call(d, "analyze", metric="Quantity", agg="sum")
    assert result["analyze_refused"]
    assert any(f["check"] == "check_out_of_range" for f in result["open_findings"])
    _call(d, "exclude_where", column="Quantity", minimum=1, reason="minimum rule")
    assert d.session.current["Quantity"].tolist() == [2, 4]
    assert d.approvals_asked == 1


def test_refunds_stay_without_checks_flagging_them_or_asking_for_approval():
    d = _dispatcher(True, approver=RejectApprover())
    numeric = _call(d, "check_numeric", column="Quantity")
    assert numeric["negatives"]["count"] == 0 and numeric["refunds"]["rows"] == [0]
    bounds = _call(d, "check_out_of_range", column="Quantity", minimum=1, maximum=10)
    assert bounds["count"] == 0
    result = _call(d, "analyze", metric="Quantity", agg="sum")
    assert result["result"] == {"all": 3.0} and d.coverage_refusals == 0
    unchanged = _call(d, "exclude_where", column="Quantity", minimum=1, reason="model tried the old minimum rule")
    assert unchanged["no_change"] and unchanged["approval"] == "auto"
    assert d.approvals_asked == 0 and d.session.version == 0
    assert d.session.current["Quantity"].tolist() == [-3, 2, 4]
    assert ("negative", "Quantity") not in d.session.issues


def test_refund_rule_applies_even_without_coverage_and_cannot_be_overridden_by_model():
    d = _dispatcher(True, approver=RejectApprover())
    d.coverage = False
    result = _call(d, "check_numeric", column="Quantity")
    assert result["negatives"]["count"] == 0
    result = _call(d, "exclude_where", column="Quantity", minimum=1, allow_negative_quantities=False, reason="min")
    assert result["no_change"] and "allow_negative_quantities" in result["ignored_arguments"]
    assert d.approvals_asked == 0


def test_range_fix_keeps_many_refunds_but_still_removes_zero_and_excess_stock():
    values = [-i for i in range(1, 26)] + [0, 2, 11]
    d = _dispatcher(True, values=values)
    result = _call(d, "check_out_of_range", column="Quantity", minimum=1, maximum=10)
    assert result["rows"] == [25, 27] and result["count"] == 2
    out = _call(d, "exclude_where", column="Quantity", minimum=1, maximum=10, reason="non-refund violations")
    assert out["applied"] and out["validation"]["ok"]
    change = d.session.changes[-1]
    assert change.rows_removed == [25, 27] and change.args["allow_negative_quantities"] is True
    assert len(d.session.current) == 26 and d.session.current.at[0, "Quantity"] == -1
    ns = {"pd": pd, "df": d.session.original.copy()}
    exec(change.code, ns)
    pd.testing.assert_frame_equal(ns["df"], d.session.current)
    result = _call(d, "analyze", metric="Quantity", agg="sum")
    assert result["result"] == {"all": -323.0}


def test_text_refunds_and_missing_values_use_the_same_check_and_fix_policy():
    d = _dispatcher(True, values=["-1,200", "-2", "0", "5", "bad", None, "1e3", 1e20])
    result = _call(d, "check_out_of_range", column="Quantity", minimum=1, maximum=10)
    assert result["rows"] == [2, 7]
    out = _call(d, "exclude_where", column="Quantity", minimum=1, maximum=10, reason="zero is invalid")
    assert out["validation"]["ok"] and d.session.changes[-1].rows_removed == [2, 7]
    assert d.session.current.loc[[0, 1], "Quantity"].tolist() == ["-1,200", "-2"]
    ns = {"pd": pd, "df": d.session.original.copy()}
    exec(d.session.changes[-1].code, ns)
    pd.testing.assert_frame_equal(ns["df"], d.session.current)


def test_refund_option_does_not_disable_positive_minima_or_upper_bounds():
    d = _dispatcher(True, values=[-2, 0, 2, 5, 11],
                    rules={"Quantity": {"min": 3, "max": 10, "allow_negative_quantities": True}})
    result = _call(d, "check_out_of_range", column="Quantity", minimum=3, maximum=10)
    assert result["rows"] == [1, 2, 4]
    required = _call(d, "analyze", metric="Quantity", agg="sum")
    assert required["open_findings"][0]["rows"] == [1, 2, 4]


def test_top_level_shorthand_is_scoped_and_column_overrides_are_explicit():
    rules = {"allow_negative_quantities": True, "Quantity": {"min": 1}, "Price": {"min": 0},
             "Qty": {"min": 1, "allow_negative_quantities": False}}
    assert allows_negative_quantities(rules, "Quantity")
    assert not allows_negative_quantities(rules, "Price")
    assert not allows_negative_quantities(rules, "Qty")
    assert allows_negative_quantities({"allow_negative_quantities": True}, " quantity ")
    assert allows_negative_quantities({"Units": {"allow_negative_quantities": True}}, "Units")
    d = _dispatcher(rules=rules, approver=RejectApprover())
    assert _call(d, "analyze", metric="Quantity", agg="sum")["result"] == {"all": 3.0}


def test_low_level_fix_and_validator_agree_about_refunds():
    df = pd.DataFrame({"Quantity": [-2, 0, 4]})
    result = exclude_where(df, "Quantity", minimum=1, allow_negative_quantities=True)
    assert result.rows_removed == [1]
    assert validate(df, "exclude_where", {"column": "Quantity", "minimum": 1,
                                          "allow_negative_quantities": True}, result)["ok"]
