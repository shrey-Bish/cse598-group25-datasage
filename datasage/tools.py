"""Tool schemas sent to the model, argument validation, and the dispatcher that runs each call.

Every fix goes through: argument check -> dry run on a copy -> risk tier (code) -> approval gate ->
validator -> commit or roll back. Errors come back to the model as text so it can correct itself.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import checks, fixes
from .analyze import run_analysis
from .profile import profile, sample_rows
from .session import Change, Session
from .validator import validate


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class ColumnArgs(_Args):
    column: str


class RangeArgs(_Args):
    column: str
    minimum: float | None = None
    maximum: float | None = None


class CrossColumnArgs(_Args):
    column: str
    expression: str = Field(description="arithmetic over columns, e.g. 'Quantity * Price'")


class FixColumnArgs(_Args):
    column: str
    reason: str


class FixReasonArgs(_Args):
    reason: str


class NormalizeArgs(_Args):
    column: str
    mapping: dict[str, str]
    reason: str


class RowsArgs(_Args):
    rows: list[int]
    reason: str


class RecomputeArgs(_Args):
    column: str
    expression: str
    rows: list[int]
    reason: str


class SetMissingArgs(_Args):
    column: str
    rows: list[int]
    reason: str


class FillArgs(_Args):
    column: str
    value: str | float
    reason: str


class Filter(_Args):
    column: str
    value: str | float


class AnalyzeArgs(_Args):
    group_by: list[str] = Field(default_factory=list)
    metric: str | None = None
    agg: Literal["sum", "mean", "count", "median", "min", "max"]
    filters: list[Filter] = Field(default_factory=list)


class FinishArgs(_Args):
    summary: str


def _schema(name: str, description: str, model: type[BaseModel]) -> dict:
    params = model.model_json_schema()
    params.pop("title", None)
    for prop in params.get("properties", {}).values():
        prop.pop("title", None)
    return {"type": "function", "function": {"name": name, "description": description, "parameters": params}}


CHECK_TOOLS = {
    "check_missing": (ColumnArgs, "Count missing values in a column."),
    "check_duplicates": (NoArgs, "Find exact duplicate rows."),
    "check_label_variants": (ColumnArgs, "Find labels that differ only by case/spaces, and likely misspellings of a more common label."),
    "check_dates": (ColumnArgs, "Find values in a date column that are not valid YYYY-MM-DD dates."),
    "check_numeric": (ColumnArgs, "Find numbers stored as text (e.g. '$1,200'), values that are not numbers, and negative numbers."),
    "check_out_of_range": (RangeArgs, "Find numbers outside [minimum, maximum]."),
    "check_cross_column": (CrossColumnArgs, "Find rows where a column does not equal an expression of other columns, e.g. Revenue vs 'Quantity * Price'."),
}

FIX_TOOLS = {
    "trim_whitespace": (FixColumnArgs, "Remove leading/trailing spaces from a text column. Low risk."),
    "normalize_labels": (NormalizeArgs, "Replace label variants with a canonical label, e.g. {'electronics': 'Electronics'}. Low risk if only case/spaces differ; misspelling merges need approval."),
    "drop_duplicates": (FixReasonArgs, "Remove exact duplicate rows, keeping the first. Needs approval."),
    "parse_dates": (FixColumnArgs, "Keep valid YYYY-MM-DD dates and set invalid ones to missing. Needs approval if any value becomes missing."),
    "cast_numeric": (FixColumnArgs, "Convert a column to numbers, reading text like '$1,200.00'. Needs approval if any value becomes missing."),
    "exclude_rows": (RowsArgs, "Remove specific rows (by row id) from the analysis copy. Needs approval."),
    "recompute_column": (RecomputeArgs, "Set a column to an expression on specific rows, e.g. Revenue = Quantity * Price. Needs approval."),
    "set_missing": (SetMissingArgs, "Mark specific cells as missing. Needs approval."),
    "fill_missing": (FillArgs, "Fill missing values in a column with one value. Needs approval; avoid guessing values."),
}

OTHER_TOOLS = {
    "profile_dataset": (NoArgs, "Re-profile the current version of the table."),
    "lookup_rules": (NoArgs, "Read the user's rules file (column meanings, valid ranges, formulas), if one was given."),
    "analyze": (AnalyzeArgs, "Answer the request: filter, group by (use 'Date:month' for months) and aggregate a numeric metric on the current version."),
    "finish": (FinishArgs, "End the run. Call this after analyze has produced the answer. Summarize what you found and did."),
}

ALL_TOOLS = {**CHECK_TOOLS, **FIX_TOOLS, **OTHER_TOOLS}
TOOL_SCHEMAS = [_schema(name, desc, model) for name, (model, desc) in ALL_TOOLS.items()]


class Dispatcher:
    def __init__(self, session: Session, approver, use_validator: bool = True, trace=None):
        self.session = session
        self.approver = approver
        self.use_validator = use_validator
        self.trace = trace
        self.approvals_asked = 0
        self.finished = False
        self.final_summary = ""

    def call(self, name: str, raw_args: str) -> tuple[dict, bool]:
        """Run one tool call. Returns (result for the model, ok)."""
        if name not in ALL_TOOLS:
            return {"error": f"unknown tool '{name}'; available: {', '.join(ALL_TOOLS)}"}, False
        model, _ = ALL_TOOLS[name]
        try:
            data = json.loads(raw_args or "{}")
            args = model.model_validate(data).model_dump(exclude_none=False)
        except (json.JSONDecodeError, ValidationError) as err:
            return {"error": f"invalid arguments for {name}: {str(err)[:400]}"}, False
        try:
            if name in CHECK_TOOLS:
                return self._check(name, args), True
            if name in FIX_TOOLS:
                return self._fix(name, args)
            return self._other(name, args), True
        except (ValueError, KeyError, TypeError) as err:
            return {"error": str(err)}, False

    def _check(self, name: str, args: dict) -> dict:
        df = self.session.current
        if name == "check_duplicates":
            result = checks.check_duplicates(df)
        elif name == "check_out_of_range":
            result = checks.check_out_of_range(df, args["column"], args["minimum"], args["maximum"])
        elif name == "check_cross_column":
            result = checks.check_cross_column(df, args["column"], args["expression"])
        else:
            fn = {"check_missing": checks.check_missing, "check_label_variants": checks.check_label_variants,
                  "check_dates": checks.check_dates, "check_numeric": checks.check_numeric}[name]
            result = fn(df, args["column"])
        checks.record_findings(self.session, result)
        return result

    def _fix(self, name: str, args: dict) -> tuple[dict, bool]:
        session = self.session
        before = session.current
        fix_args = {k: v for k, v in args.items() if k != "reason"}
        result = fixes.FIXES[name](before, **fix_args)
        risk = fixes.risk_of(name, args, result)
        preview = {"summary": result.summary, "rows_removed": result.rows_removed, "cells_changed": result.cells_changed,
                   "before": before, "after": result.df}

        if risk == "low":
            approval = "auto"
        else:
            self.approvals_asked += 1
            approval = "approved" if self.approver.decide(name, args, risk, preview) else "rejected"
        if approval == "rejected":
            session.rejected.append({"tool": name, "args": args, "risk": risk, "summary": result.summary})
            return {"applied": False, "risk": risk, "approval": "rejected",
                    "message": "The user rejected this fix. Do not retry it; leave the data as is and mention it as a caveat."}, True

        if self.use_validator:
            verdict = validate(before, name, args, result)
            if not verdict["ok"]:
                return {"applied": False, "risk": risk, "validation": verdict,
                        "message": "Validation failed; the change was rolled back. Try a different fix or flag the issue."}, False
        else:
            verdict = {"ok": True, "skipped": True}

        change = Change(version=session.version + 1, tool=name, args=args, reason=args.get("reason", ""), risk=risk,
                        approval=approval, rows_removed=result.rows_removed, cells_changed=result.cells_changed,
                        summary=result.summary, code=result.code)
        session.commit(result.df, change)
        return {"applied": True, "version": session.version, "risk": risk, "approval": approval,
                "summary": result.summary, "validation": verdict}, True

    def _other(self, name: str, args: dict) -> dict:
        session = self.session
        if name == "profile_dataset":
            return {"profile": profile(session.current), "sample_rows": sample_rows(session.current)}
        if name == "lookup_rules":
            return {"rules": session.rules or "no rules file was given"}
        if name == "analyze":
            result = run_analysis(session.current, args["group_by"], args["metric"], args["agg"],
                                  [{"column": f["column"], "value": f["value"]} for f in args["filters"]])
            result["version"] = session.version
            session.analyses.append(result)
            return result
        if name == "finish":
            if not session.analyses:
                raise ValueError("call analyze to answer the request before finishing")
            self.finished = True
            self.final_summary = args["summary"]
            return {"finished": True}
        raise ValueError(f"unhandled tool {name}")
