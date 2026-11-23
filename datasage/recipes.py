"""Cleaning recipes: the fixes approved in one DataSage run, saved so they can be replayed on a new file.

A recipe is a JSON file. It records the raw input the run cleaned and the rules file it used (by file
name and SHA-256, never a local path), the column schema of that raw input, and one step per fix with
the risk and approval it had in that run. Column types are recorded as "number" or "text", the two
kinds `load_table` produces.

This module only imports from datasage/; it never changes the agent, the tools or the fixes. Every call
into datasage/ goes through the adapter functions below (named `_ds_*`).

Command line (no model or API key needed):

    python -m datasage.recipes save --run RUN_DIR --input RAW.csv [--rules RULES.json | --no-rules] --out recipe.json
    python -m datasage.recipes apply --recipe recipe.json --input NEW.csv --out OUT_DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from . import checks as _ds_checks
from . import fixes as _ds_fixes
from . import session as _ds_session
from . import tools as _ds_tools
from . import validator as _ds_validator

RECIPE_VERSION = 1

# Fixes that work on whole columns, so they can run on a new file. The others use row ids from the
# original file, remove rows, or (fill_missing) add values nobody approved for the new file.
PORTABLE_FIXES = ("trim_whitespace", "normalize_labels", "parse_dates", "cast_numeric")

# What lookup_rules returns when a run had no rules file (datasage/tools.py, Dispatcher._other).
NO_RULES = "no rules file was given"

# The file a run with several inputs stacks them into; the report's Input line then names it.
STACKED_INPUT = "input_stacked.csv"


class RecipeError(ValueError):
    """A recipe cannot be built or replayed. The message says what to change."""


class RecipeWarning(UserWarning):
    """Something to check that does not stop the recipe, such as a report without an Input line."""


# Adapter: the only code in this module that calls datasage/. If a signature there changes, only these
# functions need to change.

def _ds_load_table(path: str | Path) -> pd.DataFrame:
    return _ds_session.load_table(path)


def _ds_load_rules(path: str | Path) -> dict:
    return _ds_session.load_rules(path)


def _ds_is_fix(name: str) -> bool:
    return name in _ds_fixes.FIXES


def _ds_fix_arg_names(fix: str) -> set[str]:
    """Arguments a fix takes, as the dispatcher filters a model's call, without "reason"."""
    model, _ = _ds_tools.FIX_TOOLS[fix]
    return set(model.model_fields) - {"reason"}


def _ds_run_fix(fix: str, df: pd.DataFrame, args: dict):
    """Dry run: the fix works on a copy and returns a FixResult; `df` is not changed."""
    return _ds_fixes.FIXES[fix](df, **args)


def _ds_risk_of(fix: str, args: dict, result) -> str:
    return _ds_fixes.risk_of(fix, args, result)


def _ds_validate(before: pd.DataFrame, fix: str, args: dict, result) -> dict:
    return _ds_validator.validate(before, fix, args, result)


def _ds_check_missing(df: pd.DataFrame, column: str) -> dict:
    return _ds_checks.check_missing(df, column)


def _ds_check_label_variants(df: pd.DataFrame, column: str) -> dict:
    return _ds_checks.check_label_variants(df, column)


def _ds_check_dates(df: pd.DataFrame, column: str) -> dict:
    return _ds_checks.check_dates(df, column)


def _ds_check_numeric(df: pd.DataFrame, column: str) -> dict:
    return _ds_checks.check_numeric(df, column)


def _ds_check_duplicates(df: pd.DataFrame) -> dict:
    return _ds_checks.check_duplicates(df)


@dataclass
class Source:
    name: str     # file name of the table the run cleaned (no directory, so recipes can be shared)
    sha256: str
    rows: int


@dataclass
class Schema:
    columns: list[str]       # in file order
    dtypes: dict[str, str]   # column -> "number" or "text"
    fingerprint: str         # see schema_fingerprint


@dataclass
class RulesRef:
    name: str     # file name of the rules file (no directory)
    sha256: str


@dataclass
class Step:
    fix: str           # a name in datasage.fixes.FIXES, e.g. "normalize_labels"
    args: dict         # the fix's arguments without "reason"
    risk: str          # risk in the original run: "low", "medium" or "high"
    approved_by: str   # approval in the original run's change log: "auto" (low risk) or "approved"
    portable: bool     # True if the fix works on whole columns, so it can be replayed on a new file


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(kw_only=True)
class Recipe:
    recipe_version: int = RECIPE_VERSION
    created_at: str = field(default_factory=_now)
    source: Source
    schema: Schema
    rules: RulesRef | None = None   # None when the run had no rules file
    steps: list[Step] = field(default_factory=list)


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def column_kinds(df: pd.DataFrame) -> dict[str, str]:
    return {str(c): "number" if pd.api.types.is_numeric_dtype(df[c]) else "text" for c in df.columns}


def _fingerprint(dtypes: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(sorted(dtypes.items())).encode()).hexdigest()


def schema_fingerprint(df: pd.DataFrame) -> str:
    """SHA-256 of the column names and kinds. Column order does not change it."""
    return _fingerprint(column_kinds(df))


def schema_of(df: pd.DataFrame) -> Schema:
    kinds = column_kinds(df)
    return Schema(columns=list(kinds), dtypes=kinds, fingerprint=_fingerprint(kinds))


def describe_input(path: str | Path) -> tuple[Source, Schema]:
    """Source and schema of a raw input file, read with load_table exactly as a DataSage run reads it.

    Pass the original input, never a run's cleaned.csv: the schema must describe what the next raw
    file will look like before any fix runs.
    """
    path = Path(path)
    df = _ds_load_table(path)
    return Source(name=path.name, sha256=file_sha256(path), rows=len(df)), schema_of(df)


class SchemaCheck(NamedTuple):
    """How a new table's columns compare with the recipe's schema. Unpacks as (missing, extra, type_changed)."""

    missing: list[str]                        # recipe columns the table lacks: replay refuses
    extra: list[str]                          # table columns the recipe does not know: a warning
    type_changed: dict[str, tuple[str, str]]  # column -> (kind in the recipe, kind in the table): a warning

    @property
    def ok(self) -> bool:
        """True when replay may go ahead: every recipe column is present."""
        return not self.missing

    def warnings(self) -> list[str]:
        out = [f"extra column '{c}' is not in the recipe; it is left as it is" for c in self.extra]
        out += [f"column '{c}' was {old} in the recipe's input and is {new} here" for c, (old, new) in self.type_changed.items()]
        return out


def check_schema(recipe: Recipe, df: pd.DataFrame) -> SchemaCheck:
    """Compare a table (as read by load_table) with the recipe's schema. Column order does not matter."""
    kinds = column_kinds(df)
    expected = recipe.schema.dtypes
    missing = [c for c in recipe.schema.columns if c not in kinds]
    extra = [c for c in kinds if c not in expected]
    type_changed = {c: (expected[c], kinds[c]) for c in recipe.schema.columns if c in kinds and kinds[c] != expected[c]}
    return SchemaCheck(missing, extra, type_changed)


def rules_ref(path: str | Path | None) -> RulesRef | None:
    if not path:
        return None
    path = Path(path)
    return RulesRef(name=path.name, sha256=file_sha256(path))


def save_recipe(recipe: Recipe, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(recipe), indent=2) + "\n")
    return path


def load_recipe(path: str | Path) -> Recipe:
    path = Path(path)
    data = json.loads(path.read_text())
    version = data.get("recipe_version") if isinstance(data, dict) else None
    if version != RECIPE_VERSION:
        raise ValueError(f"{path}: recipe_version {version!r} is not supported (expected {RECIPE_VERSION})")
    try:
        return Recipe(
            recipe_version=version,
            created_at=data["created_at"],
            source=Source(**data["source"]),
            schema=Schema(**data["schema"]),
            rules=RulesRef(**data["rules"]) if data["rules"] is not None else None,
            steps=[Step(**step) for step in data["steps"]],
        )
    except (KeyError, TypeError) as err:
        raise ValueError(f"{path} is not a valid recipe: {type(err).__name__}: {err}") from None


# Building a recipe from a run folder (report.md and trace.jsonl, as datasage/report.py writes them)

_INPUT_LINE = re.compile(r"^- Input: `(?P<path>[^`]*)`\s*$", re.MULTILINE)
_CHANGE_COLUMNS = ("Version", "Fix", "Risk", "Approval")


def _table_cells(line: str, width: int | None = None) -> list[str]:
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") else inner
    raw = inner.split("|")
    if width is not None and len(raw) > width:  # "|" inside the last cell: join it back
        raw = raw[:width - 1] + ["|".join(raw[width - 1:])]
    return [cell.strip() for cell in raw]


def parse_changes(report_md: str) -> list[dict[str, str]]:
    """Rows of a report's Changes table, as {header name: cell}.

    Columns are found by header name. Reason is the last column and may contain "|" (report.py does not
    escape it), so extra cells are joined back into it; a "|" in What changed shifts text into Reason
    but leaves Version, Fix, Risk and Approval intact. The table ends at its first non-table line, so
    the "Date changes in v{N}" lists below it are not rows. Rejected fixes keep Version "-".
    """
    lines = report_md.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## Changes")
    except StopIteration:
        raise RecipeError("report.md has no '## Changes' section") from None
    header_at = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("|")), None)
    if header_at is None or any(lines[i].startswith("#") for i in range(start + 1, header_at)):
        raise RecipeError("the '## Changes' section of report.md has no table")
    header = _table_cells(lines[header_at])
    absent = [name for name in (*_CHANGE_COLUMNS, "Reason") if name not in header]
    if absent or header[-1] != "Reason":
        raise RecipeError(f"the Changes table needs the columns {', '.join(_CHANGE_COLUMNS)} and Reason last; "
                          f"its header is {header}")
    rows = []
    for line in lines[header_at + 2:]:  # skip the |---| line
        if not line.lstrip().startswith("|"):
            break
        cells = _table_cells(line, width=len(header))
        if len(cells) < len(header):
            raise RecipeError(f"a Changes row has {len(cells)} cells, the header has {len(header)}: {line}")
        rows.append(dict(zip(header, cells)))
    return rows


def _read_trace(path: Path) -> list[dict]:
    events = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as err:
            raise RecipeError(f"{path.name} line {number} is not JSON: {err}") from None
        if isinstance(event, dict) and event.get("event") == "tool":
            events.append(event)
    return events


def _check_input(report_md: str, input_path: Path) -> None:
    found = _INPUT_LINE.search(report_md)
    if not found:
        warnings.warn("report.md has no Input line, so the input file's name could not be checked against the run",
                      RecipeWarning, stacklevel=3)
        return
    recorded = found.group("path").replace("\\", "/").rsplit("/", 1)[-1]
    if recorded != input_path.name:
        hint = (f" That run stacked several files; pass the {STACKED_INPUT} in its run folder."
                if recorded == STACKED_INPUT else "")
        raise RecipeError(f"input file '{input_path.name}' is not the run's input '{recorded}' "
                          f"(report.md, Input line).{hint}")


def _check_rules(events: list[dict], rules_path: str | Path | None, no_rules: bool) -> RulesRef | None:
    """Match the rules the caller names with what the run's lookup_rules returned. {} means no rules."""
    if rules_path and no_rules:
        raise RecipeError("give rules_path or no_rules=True, not both")
    recorded = [e["output"]["rules"] for e in events
                if e.get("name") == "lookup_rules" and isinstance(e.get("output"), dict) and "rules" in e["output"]]
    if any(r != recorded[0] for r in recorded):
        raise RecipeError("the trace's lookup_rules records disagree with each other")
    run_rules = None if not recorded else ({} if recorded[0] in (NO_RULES, {}) else recorded[0])

    if rules_path:
        try:
            given = _ds_load_rules(rules_path)
        except (OSError, json.JSONDecodeError) as err:
            raise RecipeError(f"cannot read rules file '{Path(rules_path).name}': {err}") from None
        if run_rules is None:
            raise RecipeError("trace.jsonl has no lookup_rules record, so the rules file cannot be checked "
                              "against the rules the run used")
        if given != run_rules:
            if not run_rules:
                raise RecipeError(f"the run had no rules file, but rules_path '{Path(rules_path).name}' has rules")
            raise RecipeError(f"rules file '{Path(rules_path).name}' differs from the rules the run used "
                              f"(lookup_rules in trace.jsonl)")
        return rules_ref(rules_path) if given else None

    if run_rules:
        raise RecipeError("the run used a rules file (lookup_rules in trace.jsonl); pass the same file as rules_path")
    if run_rules is None and not no_rules:
        raise RecipeError("trace.jsonl has no lookup_rules record, so it does not show whether the run had a rules "
                          "file. Pass rules_path with the run's rules file, or no_rules=True if it had none")
    return None


def _steps(events: list[dict], rows: list[dict[str, str]]) -> list[Step]:
    """Pair applied fixes in the trace with Changes rows v{version}; both must agree on fix, risk and approval."""
    applied: dict[int, dict] = {}
    for event in events:
        output = event.get("output")
        if not (_ds_is_fix(event.get("name", "")) and isinstance(output, dict) and output.get("applied") is True):
            continue
        version = output.get("version")
        if not isinstance(version, int):
            raise RecipeError(f"an applied {event['name']} record in trace.jsonl has no version")
        if version in applied:
            raise RecipeError(f"two applied fixes in trace.jsonl have version v{version} "
                              f"({applied[version]['name']} and {event['name']})")
        applied[version] = event

    logged: dict[int, dict[str, str]] = {}
    for row in rows:
        if row["Version"] == "-":  # a rejected fix: never a step
            continue
        match = re.fullmatch(r"v(\d+)", row["Version"])
        if not match:
            raise RecipeError(f"a Changes row has version '{row['Version']}'; expected v<number> or -")
        version = int(match.group(1))
        if version in logged:
            raise RecipeError(f"the Changes table has two rows for v{version}")
        logged[version] = row

    only_trace, only_report = sorted(set(applied) - set(logged)), sorted(set(logged) - set(applied))
    if only_trace or only_report:
        parts = ([f"applied in trace.jsonl but not in the Changes table: {', '.join(f'v{v}' for v in only_trace)}"]
                 if only_trace else [])
        parts += ([f"in the Changes table but not applied in trace.jsonl: {', '.join(f'v{v}' for v in only_report)}"]
                  if only_report else [])
        raise RecipeError("trace.jsonl and report.md do not pair up: " + "; ".join(parts))

    steps = []
    for version in sorted(applied):
        event, row = applied[version], logged[version]
        output = event["output"]
        in_trace = (event["name"], output.get("risk"), output.get("approval"))
        in_report = (row["Fix"], row["Risk"], row["Approval"])
        if in_trace != in_report:
            raise RecipeError(f"v{version}: trace.jsonl has fix, risk, approval {in_trace} but report.md has {in_report}")
        if output.get("approval") not in ("auto", "approved"):
            raise RecipeError(f"v{version}: an applied fix has approval '{output.get('approval')}'")
        args = event.get("args")
        if not isinstance(args, dict):
            raise RecipeError(f"v{version}: the trace's arguments for {event['name']} are not a JSON object")
        kept = _ds_fix_arg_names(event["name"])  # drops "reason" and any argument the tool ignored
        steps.append(Step(fix=event["name"], args={k: v for k, v in args.items() if k in kept},
                          risk=output["risk"], approved_by=output["approval"], portable=event["name"] in PORTABLE_FIXES))
    return steps


def build_recipe(run_dir: str | Path, input_path: str | Path, rules_path: str | Path | None = None,
                 no_rules: bool = False) -> Recipe:
    """Build a recipe from a DataSage run folder and the raw input that run cleaned.

    A step is a fix whose trace record has output.applied true and whose Changes row v{version} has the same
    Fix, Risk and Approval; rejected fixes never become steps. Steps are in version order. The input's
    name must match the report's Input line (a missing line only warns). rules_path must hold the rules
    the run looked up; a {} file and "no rules file was given" both mean no rules. Without rules_path the
    run must have had no rules, shown by its lookup_rules record or confirmed with no_rules=True.
    Raises RecipeError when any of this does not hold.
    """
    run_dir, input_path = Path(run_dir), Path(input_path)
    report_path, trace_path = run_dir / "report.md", run_dir / "trace.jsonl"
    for path in (report_path, trace_path):
        if not path.is_file():
            raise RecipeError(f"{path} not found; pass a DataSage run folder (it holds report.md and trace.jsonl)")
    if not input_path.is_file():
        raise RecipeError(f"input file {input_path} not found")
    report_md = report_path.read_text(encoding="utf-8")
    events = _read_trace(trace_path)
    _check_input(report_md, input_path)
    rules = _check_rules(events, rules_path, no_rules)
    steps = _steps(events, parse_changes(report_md))
    source, schema = describe_input(input_path)
    return Recipe(source=source, schema=schema, rules=rules, steps=steps)


# Replaying a recipe on a new file

APPLIED, NEEDS_REVIEW, NOT_NEEDED = "applied", "needs review", "not needed"

# Why each non-portable fix is never replayed on a new file.
_NOT_PORTABLE = {
    "drop_duplicates": "it removes rows",
    "exclude_rows": "it removes rows by row ids from the original file",
    "exclude_where": "it removes rows by a range rule",
    "set_missing": "it uses row ids from the original file",
    "recompute_column": "it uses row ids from the original file",
    "fill_missing": "it fills in values that were approved only for the original file",
}


@dataclass
class StepOutcome:
    step: int           # position in the recipe, from 1
    fix: str
    args: dict          # the arguments used here (normalize_labels keeps only labels present in this file)
    recipe_risk: str    # risk in the run the recipe came from
    risk: str | None    # risk on this file from risk_of after a dry run; None when the step was not dry-run
    status: str         # APPLIED, NEEDS_REVIEW or NOT_NEEDED
    detail: str


@dataclass
class ReplayResult:
    input_name: str
    input_sha256: str
    rows_in: int
    rows_out: int
    schema: SchemaCheck
    steps: list[StepOutcome]
    new_issues: list[dict]   # {"check", "column", "count", "rows", "detail"} for each check that still finds something
    cleaned_path: Path
    report_path: Path

    def with_status(self, status: str) -> list[StepOutcome]:
        return [s for s in self.steps if s.status == status]


def _changes_nothing(fix: str, df: pd.DataFrame, result) -> bool:
    if result.rows_removed:
        return False
    if fix == "cast_numeric":  # cells_changed counts changed numbers, so "$5.00" -> 5.0 counts as none
        return all(pd.api.types.is_numeric_dtype(df[c]) for c in result.touched_columns)
    return result.cells_changed == 0


def _replay_step(number: int, step: Step, df: pd.DataFrame) -> tuple[pd.DataFrame, StepOutcome]:
    """Dry-run one step on `df`. Returns the table after the step (unchanged unless applied) and the outcome."""
    def outcome(status, detail, args=step.args, risk=None):
        return StepOutcome(number, step.fix, dict(args), step.risk, risk, status, detail)

    if not (step.portable and step.fix in PORTABLE_FIXES):
        why = _NOT_PORTABLE.get(step.fix, "it is not a column-wide fix")
        return df, outcome(NEEDS_REVIEW, f"not replayed, because {why}; decide it on this file")

    args = dict(step.args)
    if step.fix == "normalize_labels":
        column = args.get("column")
        present = set(df[column].dropna().astype(str)) if column in df.columns else set()
        mapping = {k: v for k, v in dict(args.get("mapping") or {}).items() if k in present}
        if not mapping:
            return df, outcome(NOT_NEEDED, f"none of the labels {sorted(args.get('mapping') or {})} appear in this file")
        args["mapping"] = mapping
    try:
        result = _ds_run_fix(step.fix, df, args)
    except (ValueError, KeyError, TypeError) as err:
        return df, outcome(NEEDS_REVIEW, f"could not run on this file: {err}", args)
    if _changes_nothing(step.fix, df, result):
        return df, outcome(NOT_NEEDED, "nothing to change in this file", args)
    risk = _ds_risk_of(step.fix, args, result)
    if risk != "low":
        return df, outcome(NEEDS_REVIEW, f"risk is {risk} on this file (it was {step.risk} in the original run): "
                                         f"{result.summary}", args, risk)
    verdict = _ds_validate(df, step.fix, args, result)
    if not verdict["ok"]:
        return df, outcome(NEEDS_REVIEW, f"the validator rejected it: {'; '.join(verdict['problems'])}", args, risk)
    return result.df, outcome(APPLIED, result.summary, args, risk)


def _issue(check: str, column: str, count: int, rows: list, detail: str) -> dict:
    return {"check": check, "column": column, "count": int(count), "rows": list(rows), "detail": detail}


def _new_issues(recipe: Recipe, df: pd.DataFrame) -> list[dict]:
    """Re-run, on the replayed table, the checks for the columns the recipe's steps name.

    Only checks that need no rules file run here: a recipe names its rules file but does not contain it,
    so allowed labels, ranges and refunds are not checked.
    """
    columns: list[str] = []
    for step in recipe.steps:
        column = step.args.get("column")
        if isinstance(column, str) and column in df.columns and column not in columns:
            columns.append(column)
    issues = []
    for column in columns:
        fixes_here = {s.fix for s in recipe.steps if s.args.get("column") == column}
        found = _ds_check_missing(df, column)
        if found["count"]:
            issues.append(_issue("missing", column, found["count"], found["rows"], f"{found['count']} missing value(s)"))
        if fixes_here & {"trim_whitespace", "normalize_labels"}:
            found = _ds_check_label_variants(df, column)
            if found["count"]:
                issues.append(_issue("label_variant", column, found["count"], found["rows"],
                                     f"case or space variants {found['case_or_space_variants']}, "
                                     f"possible misspellings {found['possible_misspellings']}"))
        if "parse_dates" in fixes_here:
            found = _ds_check_dates(df, column)
            if found["count"] or found["ambiguous_count"]:
                issues.append(_issue("invalid_date", column, found["count"], found["rows"],
                                     f"{found['count']} value(s) not in YYYY-MM-DD form, {found['ambiguous_count']} of "
                                     f"them ambiguous; examples {found['examples']}"))
        if "cast_numeric" in fixes_here:
            found = _ds_check_numeric(df, column)
            text, other = found["text_numbers"], found["not_numbers"]
            if text["count"] or other["count"]:
                issues.append(_issue("numeric", column, text["count"] + other["count"], text["rows"] + other["rows"],
                                     f"{text['count']} number(s) stored as text, {other['count']} value(s) that are "
                                     f"not numbers"))
    if any(s.fix == "drop_duplicates" for s in recipe.steps):
        found = _ds_check_duplicates(df)
        if found["count"]:
            issues.append(_issue("duplicates", "*", found["count"], found["rows"], f"{found['count']} exact duplicate row(s)"))
    return issues


def _cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _replay_report(recipe: Recipe, result: ReplayResult) -> str:
    rules = f"`{recipe.rules.name}`" if recipe.rules else "none"
    out = ["# Recipe replay", "",
           f"- Recipe built from: `{recipe.source.name}` (rules file: {rules}), created {recipe.created_at}",
           f"- Input: `{result.input_name}`, {result.rows_in} rows, SHA-256 `{result.input_sha256}`. "
           f"The input file is only read; it is not changed.",
           f"- Output: `{result.cleaned_path.name}`, {result.rows_out} rows. Row ids are the input's 0-based row "
           f"positions.", "", "## Schema check", ""]
    warnings_ = result.schema.warnings()
    out += ["Every recipe column is present."] + ([""] + [f"- Warning: {w}" for w in warnings_] if warnings_ else [])
    out += ["", "## Steps", "",
            "| Step | Fix | Arguments | Risk in the run | Risk here | Result | Details |", "|---|---|---|---|---|---|---|"]
    for s in result.steps:
        out.append(f"| {s.step} | {s.fix} | `{_cell(json.dumps(s.args, ensure_ascii=False))}` | {s.recipe_risk} | "
                   f"{s.risk or '-'} | {s.status} | {_cell(s.detail)} |")
    review = result.with_status(NEEDS_REVIEW)
    out += ["", "## Needs review", ""]
    if review:
        out += ["These steps were not applied. Decide them on this file, for example in a DataSage run.", ""]
        out += [f"- Step {s.step}, {s.fix}: {s.detail}" for s in review]
    else:
        out.append("Nothing: every step was applied or not needed.")
    out += ["", "## Issues left after the replay", ""]
    if result.new_issues:
        out += ["| Check | Column | Count | Rows (first 10) | Details |", "|---|---|---:|---|---|"]
        out += [f"| {i['check']} | {_cell(i['column'])} | {i['count']} | {i['rows']} | {_cell(i['detail'])} |"
                for i in result.new_issues]
    else:
        out.append("The re-run checks found nothing on the recipe's columns.")
    out += ["", "Checks that need the rules file (allowed labels, ranges, refunds) are not re-run: a recipe names its "
                "rules file but does not contain it.", ""]
    return "\n".join(out)


def apply_recipe(recipe: Recipe | str | Path, input_path: str | Path, out_dir: str | Path) -> ReplayResult:
    """Replay a recipe on a new file with the same columns, without the model.

    The file is read with load_table and never changed. A missing recipe column stops the replay
    (RecipeError) before anything is written. Portable steps run in order: each is dry-run on the new
    file, its risk is recomputed with risk_of, and only a low-risk step that the validator accepts is
    applied. Medium- and high-risk steps and all non-portable steps go to "needs review". The checks for
    the recipe's columns are then re-run. Writes cleaned.csv and recipe_run.md to out_dir.
    """
    if not isinstance(recipe, Recipe):
        recipe = load_recipe(recipe)
    input_path, out_dir = Path(input_path), Path(out_dir)
    if not input_path.is_file():
        raise RecipeError(f"input file {input_path} not found")
    cleaned_path, report_path = out_dir / "cleaned.csv", out_dir / "recipe_run.md"
    if input_path.resolve() in (cleaned_path.resolve(), report_path.resolve()):
        raise RecipeError(f"writing to {out_dir} would overwrite the input file; choose another folder")

    sha = file_sha256(input_path)
    df = _ds_load_table(input_path)
    schema = check_schema(recipe, df)
    if not schema.ok:
        raise RecipeError(f"'{input_path.name}' lacks the recipe's column(s) {', '.join(schema.missing)}; "
                          f"the recipe was not replayed")
    current, outcomes = df, []
    for number, step in enumerate(recipe.steps, start=1):
        current, outcome = _replay_step(number, step, current)
        outcomes.append(outcome)

    out_dir.mkdir(parents=True, exist_ok=True)
    current.to_csv(cleaned_path, index_label="row")
    result = ReplayResult(input_name=input_path.name, input_sha256=sha, rows_in=len(df), rows_out=len(current),
                          schema=schema, steps=outcomes, new_issues=_new_issues(recipe, current),
                          cleaned_path=cleaned_path, report_path=report_path)
    report_path.write_text(_replay_report(recipe, result), encoding="utf-8")
    return result


# Command line

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m datasage.recipes",
                                     description="Save a cleaning recipe from a DataSage run, or replay one on a new "
                                                 "file with the same columns. No model or API key is needed.")
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("save", help="build a recipe from a run folder and the raw input that run cleaned")
    save.add_argument("--run", required=True, help="the run folder (it holds report.md and trace.jsonl)")
    save.add_argument("--input", required=True, help="the raw input file the run cleaned")
    rules = save.add_mutually_exclusive_group()
    rules.add_argument("--rules", help="the rules file the run used")
    rules.add_argument("--no-rules", action="store_true", help="confirm the run had no rules file")
    save.add_argument("--out", required=True, help="where to write the recipe (a .json file)")
    replay = commands.add_parser("apply", help="replay a recipe on a new file with the same columns")
    replay.add_argument("--recipe", required=True, help="a recipe saved with the save command")
    replay.add_argument("--input", required=True, help="the new file; it is only read")
    replay.add_argument("--out", required=True, help="folder for cleaned.csv and recipe_run.md")
    return parser


def _save_command(args) -> None:
    recipe = build_recipe(args.run, args.input, args.rules, no_rules=args.no_rules)
    path = save_recipe(recipe, args.out)
    portable = sum(s.portable for s in recipe.steps)
    rules = f"rules file {recipe.rules.name}" if recipe.rules else "no rules file"
    print(f"Saved {path}: {len(recipe.steps)} step(s) from {recipe.source.name} ({rules}); {portable} can be replayed "
          f"on a new file, the others go to review.")
    for number, step in enumerate(recipe.steps, start=1):
        note = "" if step.portable else ", not replayed"
        print(f"  {number}. {step.fix} {json.dumps(step.args, ensure_ascii=False)} ({step.risk}, {step.approved_by}{note})")


def _apply_command(args) -> None:
    result = apply_recipe(args.recipe, args.input, args.out)
    for line in result.schema.warnings():
        print(f"warning: {line}", file=sys.stderr)
    counts = ", ".join(f"{len(result.with_status(s))} {s}" for s in (APPLIED, NEEDS_REVIEW, NOT_NEEDED))
    print(f"Replayed {Path(args.recipe).name} on {result.input_name}: {counts}.")
    for step in result.steps:
        print(f"  {step.step}. {step.fix}: {step.status} ({step.detail})")
    if result.new_issues:
        print(f"{len(result.new_issues)} issue(s) left after the replay; see {result.report_path.name}.")
    print(f"Wrote {result.cleaned_path} and {result.report_path}. {result.input_name} was not changed.")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    code = 0
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RecipeWarning)
        try:
            (_save_command if args.command == "save" else _apply_command)(args)
        except (ValueError, OSError) as err:  # RecipeError is a ValueError; load_recipe raises ValueError too
            print(f"error: {err}", file=sys.stderr)
            code = 2
    for warning in caught:
        print(f"warning: {warning.message}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
