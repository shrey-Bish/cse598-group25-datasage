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


def _found(name: str, result: dict) -> str:
    """One-line result of a check for the state summary."""
    if name == "check_numeric":
        parts = [f"{k}={result[k]['count']} rows {result[k]['rows']}" for k in ("text_numbers", "not_numbers", "negatives")
                 if result[k]["count"]]
        return "; ".join(parts) or "nothing found"
    if not result.get("count"):
        return "nothing found"
    text = f"{result['count']} rows {result.get('rows', [])}"
    if result.get("suggested_fix"):
        text += f"; suggested_fix mapping {result['suggested_fix']['mapping']}"
    elif result.get("possible_misspellings") or result.get("case_or_space_variants"):
        text += f"; variants {result.get('case_or_space_variants')}, misspellings {result.get('possible_misspellings')}"
    return text


class Dispatcher:
    def __init__(self, session: Session, approver, use_validator: bool = True, trace=None, coverage: bool = False):
        self.session = session
        self.approver = approver
        self.use_validator = use_validator
        self.trace = trace
        self.coverage = coverage  # Milestone 3: coverage check and unresolved-finding check before analyze
        self.approvals_asked = 0
        self.coverage_refusals = 0
        self.quiet_checks = 0  # checks in a row by the model that found nothing new
        self.flagged: set[tuple[str, str]] = set()
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

    def _check(self, name: str, args: dict, by: str = "model") -> dict:
        session = self.session
        df = session.current
        column = args.get("column")
        # A repeat: the same check with the same arguments, already run by the model, and no fix applied since.
        repeat = any(c["tool"] == name and c.get("args") == args and c["by"] == "model" and c["version"] == session.version
                     for c in session.checks_run)
        stale = any(c["tool"] == name and c.get("args") == args and c["by"] == "model" for c in session.checks_run)
        if name == "check_duplicates":
            result = checks.check_duplicates(df)
        elif name == "check_out_of_range":
            result = checks.check_out_of_range(df, column, args["minimum"], args["maximum"])
        elif name == "check_cross_column":
            result = checks.check_cross_column(df, column, args["expression"])
        elif name == "check_label_variants":
            allowed = self._rule(column).get("allowed") if self.coverage else None
            result = checks.check_label_variants(df, column, allowed)
        else:
            fn = {"check_missing": checks.check_missing, "check_dates": checks.check_dates,
                  "check_numeric": checks.check_numeric}[name]
            result = fn(df, column)
        checks.record_findings(session, result)
        session.checks_run.append({"tool": name, "column": column, "version": session.version, "args": args, "by": by,
                                   "found": _found(name, result)})
        if by == "model":
            self.quiet_checks = 0 if (_found(name, result) != "nothing found" and not stale) else self.quiet_checks + 1
        if self.coverage and by == "model" and self.quiet_checks >= 6:
            result = {**result, "stall_warning": f"{self.quiet_checks} checks in a row found nothing new. Stop checking "
                      "and call analyze now; it runs any required check you skipped and tells you if a problem is "
                      "still open."}
        elif repeat and by == "model":
            result = {**result, "repeat_warning": "You already ran this exact check on this version and the data has "
                      "not changed since. Act on the result (propose a fix) or move on; do not run it again."}
        elif stale and by == "model":
            result = {**result, "repeat_note": "You ran this check before; see checks_done_latest_result in the state. "
                      "Re-run a check only to confirm a fix, then move on."}
        return result

    def _rule(self, column: str | None) -> dict:
        rule = self.session.rules.get(column) if column else None
        return rule if isinstance(rule, dict) else {}

    def required_checks(self, args: dict) -> list[tuple[str, dict]]:
        """Checks every column the analysis uses must have had, derived in code from the rules file."""
        used = [g.split(":")[0] for g in args["group_by"]] + [f["column"] for f in args["filters"]]
        if args.get("metric"):
            used.append(args["metric"])
        needed: list[tuple[str, dict]] = [("check_duplicates", {})]
        for column in dict.fromkeys(used):
            rule = self._rule(column)
            if rule.get("allowed"):
                needed.append(("check_label_variants", {"column": column}))
            if "min" in rule or "max" in rule:
                needed.append(("check_out_of_range", {"column": column, "minimum": rule.get("min"), "maximum": rule.get("max")}))
            if rule.get("format") or any(g == f"{column}:month" for g in args["group_by"]):
                needed.append(("check_dates", {"column": column}))
            if column == args.get("metric"):
                needed.append(("check_numeric", {"column": column}))
        return needed

    def _unresolved(self, name: str, result: dict) -> dict | None:
        """A finding on a question column that is still in the current data and no fix for it was rejected."""
        column = result.get("column")
        if name == "check_numeric":
            count, rows = result["text_numbers"]["count"], result["text_numbers"]["rows"]
        else:
            count, rows = result.get("count", 0), result.get("rows", [])
        if not count:
            return None
        for r in self.session.rejected:
            if r["args"].get("column") == column and r["tool"] != "exclude_rows":
                return None
            if r["tool"] in ("exclude_rows", "set_missing") and set(r["args"].get("rows", [])) & set(rows):
                return None
            if r["tool"] == "drop_duplicates" and name == "check_duplicates":
                return None
        finding = {"check": name, "column": column, "count": count, "rows": rows}
        if result.get("suggested_fix"):
            finding["suggested_fix"] = result["suggested_fix"]
        return finding

    def _coverage_gate(self, args: dict) -> dict | None:
        """Run any required check the model skipped, then refuse analyze once per open finding."""
        session = self.session
        if self.coverage_refusals >= 3:
            return None
        auto_run, open_findings = [], []
        for name, check_args in self.required_checks(args):
            if not session.checked(name, check_args.get("column")):
                auto_run.append({"tool": name, **check_args})
            result = self._check(name, check_args, by="coverage")
            finding = self._unresolved(name, result)
            if finding and (name, str(finding["column"])) not in self.flagged:
                open_findings.append(finding)
        if not open_findings:
            return None
        self.flagged.update((f["check"], str(f["column"])) for f in open_findings)
        self.coverage_refusals += 1
        return {"analyze_refused": True,
                "checks_run_for_you": auto_run,
                "open_findings": open_findings,
                "message": "These problems are still in the columns the question uses. Propose a fix for each "
                           "(use suggested_fix where given; exclude_rows for rows that break a rule), or if one "
                           "should stay, say why in the summary. Then call analyze again."}

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
            if self.coverage:
                refusal = self._coverage_gate(args)
                if refusal:
                    return refusal
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
