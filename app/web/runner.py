"""Runs DataSage in a worker thread for the browser app and turns its progress into events.

The agent loop itself is unchanged: `run_agent` gets a `BrowserApprover` (it waits for a click in the
page) and an `on_event` callback (it turns each tool call into an event with the table's current state).
"""

from __future__ import annotations

import math
import re
import threading
import time
import uuid
from pathlib import Path

import pandas as pd

from datasage.agent import run_agent
from datasage.analyze import run_analysis
from datasage.approval import Approver
from datasage.report import write_outputs
from datasage.session import load_table

FIRST_ROWS = 40         # rows shown when a run starts; rows with problems anywhere in the file are added as found
MAX_ROWS = 400          # most rows the page shows at once
APPROVAL_TIMEOUT = 600  # seconds; an unanswered approval (page closed) counts as rejected

LABELS = {
    "lookup_rules": "Reading the rules",
    "profile_dataset": "Profiling the table",
    "check_duplicates": "Looking for duplicate rows",
    "check_missing": "Looking for blanks in {column}",
    "check_label_variants": "Checking labels in {column}",
    "check_dates": "Checking dates in {column}",
    "check_numeric": "Checking numbers in {column}",
    "check_out_of_range": "Checking the range of {column}",
    "check_cross_column": "Checking {column} against its formula",
    "trim_whitespace": "Trimming spaces in {column}",
    "normalize_labels": "Merging labels in {column}",
    "drop_duplicates": "Removing duplicate rows",
    "parse_dates": "Reading dates in {column}",
    "cast_numeric": "Turning text into numbers in {column}",
    "exclude_rows": "Dropping rows that break a rule",
    "exclude_where": "Dropping rows outside the range in {column}",
    "recompute_column": "Recomputing {column}",
    "set_missing": "Blanking unreadable values in {column}",
    "fill_missing": "Filling blanks in {column}",
    "analyze": "Computing the answer",
    "finish": "Writing the report",
}
QUESTIONS = {
    "drop_duplicates": "Remove the duplicate rows?",
    "exclude_rows": "Drop these rows from the analysis?",
    "exclude_where": "Drop every row outside the allowed range of {column}?",
    "normalize_labels": "Merge these labels in {column}?",
    "parse_dates": "Convert the dates in {column}?",
    "set_missing": "Blank the unreadable values in {column}?",
    "fill_missing": "Fill the blanks in {column}?",
    "cast_numeric": "Turn the text in {column} into numbers?",
    "recompute_column": "Recompute {column} from its formula?",
    "trim_whitespace": "Trim the spaces in {column}?",
}


def plural(text: str) -> str:
    """'1 row(s)' -> '1 row', '3 row(s)' -> '3 rows'."""
    return re.sub(r"\b(\d+) ([\w ]*?)\(s\)", lambda m: f"{m.group(1)} {m.group(2)}{'' if m.group(1) == '1' else 's'}", text)


def future(tool: str, args: dict, preview: dict) -> str:
    """What a fix will do, said before it is approved ('Will remove 1 duplicate row')."""
    col, cells, n = args.get("column", "the column"), int(preview.get("cells_changed") or 0), len(preview.get("rows_removed") or [])
    text = {
        "drop_duplicates": f"Will remove {n} duplicate row(s)",
        "exclude_rows": f"Will drop {n} row(s) from the analysis",
        "exclude_where": f"Will drop {n} row(s) where {col} is outside the allowed range",
        "normalize_labels": f"Will merge {len(args.get('mapping') or {})} label(s) in {col}, changing {cells} cell(s)",
        "trim_whitespace": f"Will trim spaces in {cells} cell(s) of {col}",
        "parse_dates": f"Will read the dates in {col}, changing {cells} cell(s)",
        "set_missing": f"Will blank {cells} cell(s) in {col}",
        "fill_missing": f"Will fill {cells} blank cell(s) in {col}",
        "cast_numeric": f"Will turn {col} into numbers, changing {cells} cell(s)",
        "recompute_column": f"Will recompute {col} on {cells} row(s)",
    }.get(tool, preview.get("summary", ""))
    return plural(text)


def duplicate_sources(df: pd.DataFrame, rows) -> dict[int, int]:
    """For each duplicate row id, the earlier identical row it repeats."""
    first: dict[tuple, int] = {}
    wanted, found = set(int(r) for r in rows), {}
    for r, values in zip(df.index, df.astype(str).itertuples(index=False, name=None)):
        if values not in first:
            first[values] = int(r)
        elif int(r) in wanted:
            found[int(r)] = first[values]
    return found


def _row_problems(session, r: int) -> dict[str, str]:
    """Column -> problem name for the open findings on one row."""
    out = {}
    if session is None:
        return out
    for (kind, column), issue in session.issues.items():
        if column != "*" and r in set(issue.get("rows", [])):
            out.setdefault(str(column), NAMES.get(kind, kind))
    return out


def examples(preview: dict, tool: str = "", args: dict | None = None, session=None, limit: int = 5) -> dict:
    """What the approval card shows under Details: the exact rows a fix touches, with the evidence for each.

    duplicates: each copy and the earlier row it repeats; remove: the row with the cells that break a rule
    marked; change: each changed cell old -> new, plus the formula's inputs for recompute_column.
    """
    args = args or {}
    before, after = preview.get("before"), preview.get("after")
    if before is None or after is None:
        return {"kind": "none", "rows": [], "more": 0}
    cols = [str(c) for c in before.columns]
    removed = [int(r) for r in (preview.get("rows_removed") or []) if r in before.index]
    if removed and tool == "drop_duplicates":
        sources = duplicate_sources(before, removed)
        rows = [{"id": r, "same_as": sources.get(r), "cells": {c: _text(before.at[r, c]) for c in cols}} for r in removed[:limit]]
        return {"kind": "duplicates", "columns": cols, "rows": rows, "more": max(0, len(removed) - limit)}
    if removed:
        rows = []
        for r in removed[:limit]:
            problems = _row_problems(session, r)
            rows.append({"id": r, "cells": {c: _text(before.at[r, c]) for c in cols}, "problems": problems})
        return {"kind": "remove", "columns": cols, "rows": rows, "more": max(0, len(removed) - limit)}
    common = after.index.intersection(before.index)
    changed = sorted(_changed_rows(before.loc[common], after.loc[common, list(before.columns)]))
    inputs = [c for c in cols if c != args.get("column") and re.search(rf"\b{re.escape(c)}\b", str(args.get("expression", "")))]
    rows = []
    for r in changed[:limit]:
        diffs = [{"column": str(c), "before": _text(before.at[r, c]), "after": _text(after.at[r, c])}
                 for c in before.columns if not _same(before.at[r, c], after.at[r, c])]
        rows.append({"id": r, "changes": diffs, "inputs": [{"column": c, "value": _text(before.at[r, c])} for c in inputs]})
    return {"kind": "change", "rows": rows, "more": max(0, len(changed) - limit)}


def label(tool: str, args: dict) -> str:
    return LABELS.get(tool, tool).format(column=args.get("column", "a column"))


def _same(a, b) -> bool:
    if _blank(a) and _blank(b):
        return True
    if _blank(a) or _blank(b):
        return False
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _blank(v) -> bool:
    return v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)) or (not isinstance(v, str) and pd.isna(v))


def _text(v) -> str:
    if _blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _changed_rows(before: pd.DataFrame, after: pd.DataFrame) -> set[int]:
    """Rows where any cell differs; "640" and 640.0 count as the same (a whole column cast to numbers)."""
    diff = pd.Series(False, index=before.index)
    for col in before.columns:
        x, y = before[col], after[col]
        xn, yn = pd.to_numeric(x, errors="coerce"), pd.to_numeric(y, errors="coerce")
        same = (x.isna() & y.isna()) | (xn.notna() & yn.notna() & (xn == yn)) | (x.astype(str) == y.astype(str))
        diff |= ~same.fillna(False).astype(bool)
    return set(int(r) for r in before.index[diff])


def table_state(session) -> dict:
    """Per shown row: removed or not, and per cell its current text and state.

    States: "" (plain), "flag" (a check found a problem that is still open), "fixed" (a fix changed it),
    "kept" (a fix for it was rejected, so it stays as a caveat). A row can be "removed", "flag" or "kept".
    """
    original, current = session.original, session.current
    flagged: dict[int, set] = {}
    for (kind, column), issue in session.issues.items():
        for r in issue.get("rows", []):
            flagged.setdefault(int(r), set()).add(column)
    kept: dict[int, set] = {}
    for rej in session.rejected:
        args = rej["args"]
        rows = args.get("rows") or []
        if rej["tool"] in ("exclude_rows", "drop_duplicates"):
            for r in rows or [r for r, cols in flagged.items() if "*" in cols]:
                kept.setdefault(int(r), set()).add("*")
        else:
            col = args.get("column")
            for r, cols in flagged.items():
                if col in cols and (not rows or r in rows):
                    kept.setdefault(r, set()).add(col)
    removed = set(int(r) for r in original.index.difference(current.index))
    common = current.index.intersection(original.index)
    changed = _changed_rows(original.loc[common], current.loc[common, list(original.columns)])
    dup_rows = [r for r, cols in flagged.items() if "*" in cols]
    sources = set(duplicate_sources(original, dup_rows).values()) if dup_rows else set()
    extra = sorted((set(flagged) | set(kept) | removed | changed | sources) - set(range(FIRST_ROWS)))
    shown = [int(r) for r in original.index[:FIRST_ROWS]] + [r for r in extra if r in original.index]
    shown = shown[:MAX_ROWS]
    rows_out = {}
    for r in shown:
        r = int(r)
        removed = r not in current.index
        cells = {}
        for col in original.columns:
            before = original.at[r, col]
            now = before if removed else current.at[r, col]
            state = ""
            if not removed and not _same(before, now):
                state = "fixed"
            elif col in kept.get(r, ()) or ("*" in kept.get(r, ()) and col in flagged.get(r, ())):
                state = "kept"
            elif col in flagged.get(r, ()):
                state = "flag"
            cells[str(col)] = {"text": _text(now), "state": state}
        row_state = "removed" if removed else "kept" if "*" in kept.get(r, ()) else "flag" if "*" in flagged.get(r, ()) else ""
        rows_out[r] = {"state": row_state, "cells": cells}
    return {"rows": rows_out, "version": session.version, "total_rows": len(original)}


BLANK_KINDS = {"missing", "invalid_date"}  # a blank or unreadable value: not, on its own, a reason to drop a row


def auto_needs_person(tool: str, preview: dict, session) -> str | None:
    """In Auto mode, a fix that should still wait for a person, and why (None: approve as usual).

    The Auto-mode study found one bad auto-approval in 269: dropping rows whose only problem was a blanked
    date. So a row drop waits for a person when any dropped row has no recorded problem, or only blank or
    unreadable values. Rows that break a rule (negative, out of range, formula) are still dropped at once.
    """
    if tool == "parse_dates" and preview.get("ambiguous_dates"):
        return "Auto paused: these dates have more than one valid interpretation. Confirm the proposed date order."
    if tool != "exclude_rows" or session is None:
        # exclude_where removes only rows outside a range rule, so every row it drops breaks a rule. Its rows
        # cannot be matched to recorded findings anyway: a check lists at most 10 row ids, the fix can drop more.
        return None
    rows = [int(r) for r in (preview.get("rows_removed") or [])]
    weak = []
    for r in rows:
        kinds = {kind for (kind, _), issue in session.issues.items() if r in set(issue.get("rows", []))}
        if not kinds or kinds <= BLANK_KINDS:
            weak.append(r)
    if not weak:
        return None
    shown = ", ".join(str(r) for r in weak[:5]) + ("..." if len(weak) > 5 else "")
    return (f"Auto paused: row{'s' if len(weak) > 1 else ''} {shown} would be dropped although "
            f"{'their' if len(weak) > 1 else 'its'} only problem is a blank or unreadable value (or none was found).")


class BrowserApprover(Approver):
    name = "browser"

    def __init__(self, run: "Run"):
        self.run = run

    def decide(self, tool, args, risk, preview):
        if self.run.cancelled:  # stopped before this question came up: reject without asking
            self.run.refusals.append("stopped")
            return False
        approval_id = uuid.uuid4().hex[:8]
        waiter = threading.Event()
        self.run.pending[approval_id] = {"event": waiter, "answer": False}
        rows = list(preview.get("rows_removed") or args.get("rows") or [])
        paused = auto_needs_person(tool, preview, getattr(self.run, "session", None)) if self.run.mode == "auto" else None
        auto = self.run.mode == "auto" and not paused
        self.run.emit({
            "type": "approval", "id": approval_id, "tool": tool, "risk": risk, "auto": auto, "paused": paused,
            "title": QUESTIONS.get(tool, f"Apply {tool}?").format(column=args.get("column", "this column")),
            "summary": future(tool, args, preview), "reason": args.get("reason", ""),
            "rows": [int(r) for r in rows][:20], "column": args.get("column"),
            "examples": examples(preview, tool, args, getattr(self.run, "session", None)),
        })
        if auto:  # Auto mode: approve at once; the card is shown as a short notice and the change is logged
            self.run.pending[approval_id]["answer"] = True
            waiter.set()
        if self.run.cancelled:  # a stop that landed while the card was being sent
            waiter.set()
        in_time = waiter.wait(self.run.approval_timeout)
        answered = in_time and not self.run.cancelled
        answer = bool(self.run.pending.pop(approval_id)["answer"]) if answered else False
        self.run.emit({"type": "approval_closed", "id": approval_id, "answer": answer, "timed_out": not in_time})
        if not answer:  # why it was refused, in the same order as session.rejected (used by the change log)
            self.run.refusals.append("keep" if answered else "stopped" if self.run.cancelled else "timeout")
        return answer


class Run:
    def __init__(self, input_path: Path, question: str, rules_path: Path | None, out_dir: Path, model: str | None,
                 sheet: str | None = None, client_id: str = "", mode: str = "ask"):
        self.id = out_dir.name
        self.input_path, self.question, self.rules_path, self.out_dir, self.model = input_path, question, rules_path, out_dir, model
        self.sheet = sheet
        self.client_id = client_id
        self.sources = None  # set by the server when several files were stacked into one table
        self.mode = mode if mode in ("ask", "auto") else "ask"
        self.approval_timeout = APPROVAL_TIMEOUT  # the hosted app sets a shorter one
        self.created = time.time()
        self.events: list[dict] = []
        self.cond = threading.Condition()
        self.pending: dict[str, dict] = {}
        self.refusals: list[str] = []  # "keep", "stopped" or "timeout" for each refused fix, in order
        self.cancelled = False
        self.done = False
        self.counts = {"checks": 0, "fixes": 0}
        self.analyze_args: dict | None = None
        self.session = None

    def emit(self, event: dict) -> None:
        with self.cond:
            event["seq"] = len(self.events)
            self.events.append(event)
            self.cond.notify_all()

    def answer(self, approval_id: str, answer: bool) -> bool:
        item = self.pending.get(approval_id)
        if not item:
            return False
        item["answer"] = answer
        item["event"].set()
        return True

    def cancel(self) -> None:
        self.cancelled = True
        for item in list(self.pending.values()):
            item["event"].set()

    def start(self) -> None:
        threading.Thread(target=self._work, daemon=True).start()

    def _on_event(self, event: dict, session) -> None:
        if event.get("event") != "tool":
            return
        self.session = session
        name, args = event["name"], event["args"] if isinstance(event["args"], dict) else {}
        if name.startswith("check_"):
            self.counts["checks"] += 1
        output = event.get("output") or {}
        if output.get("applied"):
            self.counts["fixes"] += 1
        phase = "rules" if name in ("lookup_rules", "profile_dataset") else "check" if name.startswith("check_") \
            else "answer" if name in ("analyze", "finish") else "fix"
        refused = bool(output.get("analyze_refused"))
        if name == "analyze" and event.get("ok") and not refused and "result" in output:
            self.analyze_args = args
        self.emit({"type": "step", "tool": name, "label": label(name, args), "phase": phase, "ok": event.get("ok"),
                   "refused": refused, "counts": dict(self.counts), "table": table_state(session)})

    def _work(self) -> None:
        start = time.time()
        try:
            df = load_table(self.input_path, sheet=self.sheet)
            self.emit({"type": "start", "question": self.question, "columns": [str(c) for c in df.columns],
                       "total_rows": len(df), "rows": initial_rows(self.input_path, self.sheet),
                       "read": df.attrs.get("read", {}), "sources": self.sources})
            kwargs = {"model": self.model} if self.model else {}
            result = run_agent(self.input_path, self.question, BrowserApprover(self), rules_path=self.rules_path,
                               on_event=self._on_event, sheet=self.sheet,
                               should_stop=lambda: self.cancelled, **kwargs)
            write_outputs(result, self.out_dir)
            analysis = result.session.analyses[-1] if result.session.analyses else None
            changes = change_log(result.session, self.mode, self.refusals, self.approval_timeout)
            self.emit({
                "type": "done", "finished": result.finished, "stop_reason": result.stop_reason,
                "answer": analysis["result"] if analysis else None,
                "analysis": {k: analysis.get(k) for k in ("group_by", "metric", "agg", "rows_used")} if analysis else None,
                "summary": result.final_summary, "changes": changes, "seconds": round(time.time() - start, 1),
                "tool_calls": result.tool_calls, "approvals": result.approvals_asked, "model": result.model,
                "mode": self.mode,
                "files": ["cleaned.csv", "report.md", "replay.py", "trace.jsonl"], "table": table_state(result.session),
                "health": health(result.session, self.analyze_args),
            })
        except Exception as err:  # shown in the page; the server keeps running
            self.emit({"type": "error", "message": f"{type(err).__name__}: {err}"})
        finally:
            self.done = True
            with self.cond:
                self.cond.notify_all()


REFUSED = {"keep": "you chose Keep, so it is listed as a caveat",
           "stopped": "not applied because the run was stopped",
           "timeout": "no answer within {wait}, so it is listed as a caveat"}


def _wait_text(seconds: int) -> str:
    return f"{seconds // 60} minutes" if seconds % 60 == 0 and seconds >= 120 else f"{seconds} seconds"


def change_log(session, mode: str, refusals: list[str], wait: int = APPROVAL_TIMEOUT) -> list[dict]:
    """Every applied and refused fix for the Answer tab, with who decided it and how."""
    how = {"auto": "safe, applied without asking", "approved": "approved automatically" if mode == "auto" else "you approved"}
    changes = [{"applied": True, "text": plural(c.summary), "approval": c.approval, "how": how.get(c.approval, "")}
               for c in session.changes]
    for i, r in enumerate(session.rejected):
        reason = refusals[i] if i < len(refusals) else "keep"
        changes.append({"applied": False, "text": plural(f"Not applied: {r['summary']}"), "approval": "rejected",
                        "how": REFUSED[reason].format(wait=_wait_text(wait))})
    return changes


FIX_TOOLS = {
    "duplicates": {"drop_duplicates"}, "label_variant": {"normalize_labels", "trim_whitespace"},
    "invalid_date": {"parse_dates", "set_missing"}, "text_number": {"cast_numeric"}, "missing": {"fill_missing"},
    "negative": {"exclude_rows", "exclude_where"}, "out_of_range": {"exclude_rows", "exclude_where"},
    "cross_column": {"recompute_column", "exclude_rows"},
}
NAMES = {"duplicates": "duplicate rows", "label_variant": "label variants", "invalid_date": "unreadable dates",
         "text_number": "numbers stored as text", "missing": "blank cells", "negative": "negative values",
         "out_of_range": "values outside the rules", "cross_column": "formula mismatches", "not_number": "values that are not numbers"}


def _touches(item: dict, kind: str, column: str, rows: set) -> bool:
    if item["tool"] not in FIX_TOOLS.get(kind, set()):
        return False
    args = item["args"]
    if item["tool"] == "exclude_where":
        return args.get("column") == column
    if item["tool"] in ("exclude_rows", "drop_duplicates"):
        return column == "*" or not rows or bool(rows & set(args.get("rows") or getattr(item.get("change"), "rows_removed", []) or []))
    return args.get("column") == column


def health(session, analyze_args: dict | None) -> dict:
    """What the run found and did, column by column, and the answer before and after cleaning."""
    applied = [{"tool": c.tool, "args": c.args, "change": c} for c in session.changes]
    for item in applied:
        if item["tool"] in ("exclude_rows", "drop_duplicates"):
            item["args"] = {**item["args"], "rows": item["change"].rows_removed}
    issues = []
    for (kind, column), issue in sorted(session.issues.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        rows = set(issue.get("rows", []))
        status = "fixed" if any(_touches(i, kind, column, rows) for i in applied) else \
            "kept" if any(_touches(r, kind, column, rows) for r in session.rejected) else "not needed"
        issues.append({"type": kind, "name": NAMES.get(kind, kind.replace("_", " ")), "column": column,
                       "count": int(issue["count"]), "status": status})
    removed = {}
    for c in session.changes:
        if c.rows_removed:
            removed[c.tool] = removed.get(c.tool, 0) + len(c.rows_removed)
    raw = {"result": None, "error": None}
    if analyze_args:
        try:
            raw["result"] = run_analysis(session.original, analyze_args.get("group_by"), analyze_args.get("metric"),
                                         analyze_args.get("agg", "sum"), analyze_args.get("filters") or [])["result"]
        except Exception as err:  # e.g. the metric column was text before cleaning
            raw["error"] = str(err).split(";")[0]
    return {"rows_before": int(len(session.original)), "rows_after": int(len(session.current)),
            "removed": [{"why": {"drop_duplicates": "duplicates", "exclude_rows": "broke a rule",
                                 "exclude_where": "outside a range"}.get(k, k), "count": v}
                        for k, v in removed.items()],
            "cells_changed": int(sum(c.cells_changed for c in session.changes)), "issues": issues, "raw_answer": raw}


def initial_rows(path: Path, sheet: str | None = None) -> list[dict]:
    df = load_table(path, sheet=sheet)
    return [{"id": int(r), "cells": {str(c): _text(df.at[r, c]) for c in df.columns}} for r in df.index[:FIRST_ROWS]]
