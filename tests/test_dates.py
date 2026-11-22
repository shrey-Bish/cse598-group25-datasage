"""M1: deterministic date conversion, ambiguity approval, audit log and replay."""

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.web.runner import auto_needs_person
from datasage import checks, fixes
from datasage.agent import RunResult
from datasage.approval import RejectApprover, ScriptedApprover
from datasage.report import markdown_report, replay_script
from datasage.session import Session, load_table
from datasage.tools import Dispatcher
from datasage.values import iso_date


@pytest.mark.parametrize("raw, expected", [
    ("2024-06-03", "2024-06-03"),
    ("2024-06-03T00:00:00.000", "2024-06-03"),
    ("2024-06-03 14:05", "2024-06-03"),
    ("2024-06-03T23:59:59.123456Z", "2024-06-03"),
    ("2024-06-03T00:01:00+14:00", "2024-06-03"),
    ("2024/6/3", "2024-06-03"),
    ("2024.6.3", "2024-06-03"),
    ("2024-6-3", "2024-06-03"),
    ("3 Jun 2024", "2024-06-03"),
    ("June 3, 2024", "2024-06-03"),
    ("2024-06-03T14:05:00.123456789", "2024-06-03"),
    ("13/04/2026", "2026-04-13"),
    ("04/13/2026", "2026-04-13"),
    ("03/03/2026", "2026-03-03"),
    (" 2024-02-29 ", "2024-02-29"),
    (date(2024, 6, 3), "2024-06-03"),
    (datetime(2024, 6, 3, 14, 5), "2024-06-03"),
])
def test_clear_dates_preserve_the_written_calendar_day(raw, expected):
    assert iso_date(raw).isoformat() == expected


@pytest.mark.parametrize("raw", [
    "not-a-date", "2024-02-30", "2023-02-29", "2024-06-03T25:00:00",
    "2024-06-03 14:61", "2024-06-03T14:05garbage", "31/02/2026", "03/04/26", "2024-06",
    "03/04/2026", "", None, pd.NA,
    "2024/06.03", "31 Feb 2026", "2024-06-03T14:05:00+24:00",
])
def test_invalid_and_ambiguous_values_are_never_guessed(raw):
    assert iso_date(raw) is None


def test_ambiguous_dates_have_two_explicit_interpretations():
    assert iso_date("03/04/2026", "dmy") == date(2026, 4, 3)
    assert iso_date("03/04/2026", "mdy") == date(2026, 3, 4)
    with pytest.raises(ValueError):
        iso_date("03/04/2026", "guess")


def _call(d, **args):
    out, ok = d.call("parse_dates", json.dumps({"column": "Date", "reason": "read dates", **args}))
    assert ok, out
    return out


def test_safe_work_is_automatic_but_ambiguity_stays_until_approved(tmp_path):
    path = tmp_path / "dates.csv"
    path.write_text("Date,Qty\n2024-06-03T00:00:00.000,1\n2024-06-03 14:05,2\nbad,3\n03/04/2026,4\n,5\n")
    session = Session(load_table(path), str(path), "units by month")
    original = session.original.copy()
    d = Dispatcher(session, RejectApprover())
    finding = checks.check_dates(session.current, "Date")
    assert finding["rows"] == [0, 1, 2, 3]
    assert finding["ambiguous_count"] == 1 and finding["ambiguous_rows"] == [3]
    out = _call(d)
    assert out["applied"] and out["approval"] == "auto" and out["risk"] == "low"
    assert out["validation"]["ok"] and d.approvals_asked == 0
    assert session.current["Date"].iloc[:2].tolist() == ["2024-06-03", "2024-06-03"]
    assert pd.isna(session.current.at[2, "Date"]) and pd.isna(session.current.at[4, "Date"])
    assert session.current.at[3, "Date"] == "03/04/2026"
    assert session.changes[0].cells_changed == 3
    assert [c["row"] for c in session.changes[0].cell_changes] == [0, 1, 2]
    assert session.changes[0].cell_changes[2]["after"] is None
    pd.testing.assert_frame_equal(session.original, original)
    out = _call(d, date_order="dmy")
    assert not out["applied"] and out["approval"] == "rejected" and session.version == 1
    assert session.current.at[3, "Date"] == "03/04/2026"

    approved = Dispatcher(session, ScriptedApprover([True]))
    out = _call(approved, date_order="dmy")
    assert out["applied"] and out["approval"] == "approved" and out["risk"] == "medium"
    assert session.current.at[3, "Date"] == "2026-04-03"
    run = RunResult(session, "test", True, "finish", "dates normalized")
    report = markdown_report(run)
    for row in range(4):
        assert f"Row {row}, `Date`:" in report
    assert "2024-06-03T00:00:00.000" in report and "→ missing" in report
    ns = {}
    exec(replay_script(run), ns)
    pd.testing.assert_frame_equal(ns["df"], session.current, check_dtype=False)


def test_coverage_requires_timestamp_normalization():
    df = pd.DataFrame({"Date": ["2024-06-03T00:00:00.000"], "Qty": [2]})
    session = Session(df, "t.csv", "units by month", {"Date": {"format": "YYYY-MM-DD"}})
    d = Dispatcher(session, RejectApprover(), coverage=True)
    args = json.dumps({"group_by": ["Date:month"], "metric": "Qty", "agg": "sum"})
    out, ok = d.call("analyze", args)
    assert ok and out["analyze_refused"]
    _call(d)
    out, ok = d.call("analyze", args)
    assert ok and out["result"] == {"2024-06": 2.0}


def test_auto_mode_pauses_for_ambiguous_date_conversion():
    assert auto_needs_person("parse_dates", {"ambiguous_dates": 1}, None)
    assert auto_needs_person("parse_dates", {"ambiguous_dates": 0}, None) is None


def test_chicago_timestamps_are_normalized_without_losing_rows_or_dates():
    df = load_table(Path("eval/real/chicago_inspections/inspections.csv"))
    before = df["inspection_date"].notna().sum()
    d = Dispatcher(Session(df, "inspections.csv", "count inspections"), RejectApprover())
    out, ok = d.call("parse_dates", json.dumps({"column": "inspection_date", "reason": "read city timestamps"}))
    assert ok and out["applied"] and out["approval"] == "auto"
    assert len(d.session.current) == len(df)
    assert d.session.current["inspection_date"].notna().sum() == before
    assert all(iso_date(v).isoformat() == v for v in d.session.current["inspection_date"].dropna())
    assert out["validation"]["ok"]
