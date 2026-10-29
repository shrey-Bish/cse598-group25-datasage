"""Final outputs: Markdown report, cleaned copy, replay script, and the number-grounding check."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .agent import RunResult
from .profile import profile, sample_rows

_NUMBER = re.compile(r"(?<![\w.])-?\$?\d[\d,]*(?:\.\d+)?")


def tool_numbers(result: RunResult) -> set[float]:
    """Every number that appeared in a tool result during the run."""
    found: set[float] = set()

    def walk(obj):
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            found.add(round(float(obj), 2))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                walk(v)
                walk_text(str(k))
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)
        elif isinstance(obj, str):
            walk_text(obj)

    def walk_text(text):
        for token in _NUMBER.findall(text):
            try:
                found.add(round(float(token.replace("$", "").replace(",", "")), 2))
            except ValueError:
                pass

    for event in result.trace:
        if event.get("name") == "finish":  # the summary itself is not evidence
            continue
        walk(event.get("output"))
        walk(event.get("args"))
    walk_text(result.session.request)
    # The profile and sample rows the harness showed the model at the start are also tool data.
    walk(profile(result.session.original))
    walk(sample_rows(result.session.original))
    return found


def ungrounded_numbers(result: RunResult) -> list[str]:
    """Numbers in the final summary that no tool produced (small counts 0-10 are allowed)."""
    allowed = tool_numbers(result)
    bad = []
    for token in _NUMBER.findall(result.final_summary or ""):
        value = round(float(token.replace("$", "").replace(",", "")), 2)
        if value in allowed or (value.is_integer() and 0 <= value <= 10):
            continue
        bad.append(token)
    return bad


def replay_script(result: RunResult) -> str:
    session = result.session
    lines = [
        "# Replays the DataSage cleaning steps without the agent.",
        "import pandas as pd",
        f"df = pd.read_csv({session.source!r}, dtype=str, keep_default_na=False)",
        "df = df.replace({'': pd.NA, 'NA': pd.NA, 'N/A': pd.NA, 'n/a': pd.NA, 'null': pd.NA, 'None': pd.NA})",
        "for col in df.columns:  # same rule as DataSage: convert only columns that are entirely plain numbers",
        "    as_num = pd.to_numeric(df[col], errors='coerce')",
        "    if as_num.notna().sum() == df[col].notna().sum():",
        "        df[col] = as_num",
    ]
    for change in session.changes:
        lines.append(f"# v{change.version} {change.tool} ({change.approval}): {change.reason}")
        lines.append(change.code)
    return "\n".join(lines) + "\n"


def markdown_report(result: RunResult) -> str:
    session = result.session
    out = [f"# DataSage report", "", f"- Input: `{session.source}`", f"- Question: {session.request}",
           f"- Model: `{result.model}`; stop reason: `{result.stop_reason}`; tool calls: {result.tool_calls}; "
           f"approvals asked: {result.approvals_asked}; time: {result.seconds}s", ""]
    out += ["## Problems found", "", "| Type | Column | Count | Rows (first 10) |", "|---|---|---:|---|"]
    for issue in session.issues.values():
        out.append(f"| {issue['type']} | {issue['column']} | {issue['count']} | {issue.get('rows', [])} |")
    out += ["", "## Changes", "", "| Version | Fix | Risk | Approval | What changed | Reason |", "|---|---|---|---|---|---|"]
    for c in session.changes:
        out.append(f"| v{c.version} | {c.tool} | {c.risk} | {c.approval} | {c.summary} | {c.reason} |")
    for r in session.rejected:
        out.append(f"| - | {r['tool']} | {r['risk']} | rejected | {r['summary']} (not applied) | {r['args'].get('reason', '')} |")
    out += ["", "## Answer", ""]
    if session.analyses:
        a = session.analyses[-1]
        out += [f"{a['agg']} of `{a['metric']}` by {a['group_by'] or 'all rows'} (rows used: {a['rows_used']}, version v{a['version']})", "",
                "| Group | Value |", "|---|---:|"]
        out += [f"| {k} | {v:,.2f} |" for k, v in a["result"].items()]
    else:
        out.append("No answer was produced.")
    bad = ungrounded_numbers(result)
    out += ["", "## Summary", "", result.final_summary or "(none)"]
    if bad:
        out += ["", f"Note: these numbers in the summary did not come from any tool result: {', '.join(bad)}"]
    return "\n".join(out) + "\n"


def write_outputs(result: RunResult, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(markdown_report(result))
    (out / "replay.py").write_text(replay_script(result))
    result.session.current.to_csv(out / "cleaned.csv", index_label="row")
    with open(out / "trace.jsonl", "w") as fh:
        for event in result.trace:
            fh.write(json.dumps(event, default=str) + "\n")
    return out
