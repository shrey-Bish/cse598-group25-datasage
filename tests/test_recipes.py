"""Tests for cleaning recipes (datasage/recipes.py). Synthetic data only; no API key or network.

Run folders are made by the real agent loop (run_agent and write_outputs) with a scripted client in place
of the model, so the parser is always tested against what report.py and the trace write today.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from datasage import recipes
from datasage.agent import run_agent
from datasage.approval import ScriptedApprover
from datasage.report import write_outputs

FIXTURES = Path(__file__).parent / "fixtures" / "recipes"
JAN, FEB, RULES_FILE = FIXTURES / "sales_jan.csv", FIXTURES / "sales_feb.csv", FIXTURES / "sales_rules.json"

MONTH1 = (
    "Order_ID,Date,Category,Quantity,Price\n"
    "1,2026-08-01,Electronics,2,$10.00\n"
    "2,2026-08-02,electronics,1,$5.00\n"
    "3,2026-08-03,Accessories,3,$7.50\n"
)
RULES = '{"Category": {"allowed": ["Electronics", "Accessories"]}}\n'


@pytest.fixture
def month1(tmp_path):
    path = tmp_path / "month1.csv"
    path.write_text(MONTH1)
    return path


@pytest.fixture
def rules(tmp_path):
    path = tmp_path / "rules" / "sales_rules.json"
    path.parent.mkdir()
    path.write_text(RULES)
    return path


def _recipe(path, rules_path=None):
    source, schema = recipes.describe_input(path)
    return recipes.Recipe(
        source=source,
        schema=schema,
        rules=recipes.rules_ref(rules_path),
        steps=[
            recipes.Step(fix="normalize_labels", args={"column": "Category", "mapping": {"electronics": "Electronics"}},
                         risk="low", approved_by="auto", portable=True),
            recipes.Step(fix="exclude_rows", args={"rows": [2]}, risk="high", approved_by="approved", portable=False),
        ],
    )


def test_save_and_load_round_trip(tmp_path, month1, rules):
    recipe = _recipe(month1, rules)
    path = recipes.save_recipe(recipe, tmp_path / "recipe.json")

    assert recipes.load_recipe(path) == recipe
    data = json.loads(path.read_text())
    assert data["recipe_version"] == 1
    assert data["source"] == {"name": "month1.csv", "sha256": hashlib.sha256(MONTH1.encode()).hexdigest(), "rows": 3}
    assert data["rules"] == {"name": "sales_rules.json", "sha256": hashlib.sha256(RULES.encode()).hexdigest()}
    assert str(tmp_path) not in path.read_text()  # file names only, no local folders
    # Schema of the raw input as load_table reads it: "$10.00" keeps Price as text.
    assert data["schema"]["columns"] == ["Order_ID", "Date", "Category", "Quantity", "Price"]
    assert data["schema"]["dtypes"] == {"Order_ID": "number", "Date": "text", "Category": "text",
                                        "Quantity": "number", "Price": "text"}


def test_recipe_without_rules_file(tmp_path, month1):
    path = recipes.save_recipe(_recipe(month1), tmp_path / "recipe.json")
    assert json.loads(path.read_text())["rules"] is None
    assert recipes.load_recipe(path).rules is None


def test_fingerprint_ignores_column_order_but_not_names_or_kinds():
    df = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
    assert recipes.schema_fingerprint(df) == recipes.schema_fingerprint(df[["y", "x"]])
    assert recipes.schema_fingerprint(df) != recipes.schema_fingerprint(df.rename(columns={"x": "z"}))
    assert recipes.schema_fingerprint(df) != recipes.schema_fingerprint(df.astype({"x": str}))


def test_load_refuses_unknown_version_and_broken_files(tmp_path, month1):
    path = recipes.save_recipe(_recipe(month1), tmp_path / "recipe.json")
    data = json.loads(path.read_text())

    path.write_text(json.dumps({**data, "recipe_version": 2}))
    with pytest.raises(ValueError, match="recipe_version 2"):
        recipes.load_recipe(path)

    del data["schema"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="not a valid recipe"):
        recipes.load_recipe(path)


# R6: schema check before a replay

def test_check_schema_accepts_the_same_columns_in_any_order(month1):
    recipe = _recipe(month1)
    df = recipes._ds_load_table(month1)
    result = recipes.check_schema(recipe, df[list(reversed(df.columns))])
    assert result == ([], [], {})
    assert result.ok and result.warnings() == []


def test_check_schema_missing_column_blocks_replay(month1):
    result = recipes.check_schema(_recipe(month1), recipes._ds_load_table(month1).drop(columns=["Category"]))
    missing, extra, type_changed = result
    assert (missing, extra, type_changed) == (["Category"], [], {})
    assert not result.ok


def test_check_schema_extra_column_and_type_change_are_warnings(tmp_path, month1):
    recipe = _recipe(month1)
    feb = tmp_path / "month2.csv"
    # Quantity now holds text ("two"), and a new Region column appears.
    feb.write_text("Order_ID,Date,Category,Quantity,Price,Region\n4,2026-09-01,Electronics,two,$1.00,West\n")
    result = recipes.check_schema(recipe, recipes._ds_load_table(feb))
    assert result.missing == []
    assert result.extra == ["Region"]
    assert result.type_changed == {"Quantity": ("number", "text")}
    assert result.ok
    assert result.warnings() == ["extra column 'Region' is not in the recipe; it is left as it is",
                                 "column 'Quantity' was number in the recipe's input and is text here"]


# R7: building a recipe from a run folder

class _ToolCall:
    def __init__(self, number, name, args):
        self.id = f"call_{number}"
        self.function = types.SimpleNamespace(name=name, arguments=json.dumps(args))

    def model_dump(self):
        return {"id": self.id, "type": "function",
                "function": {"name": self.function.name, "arguments": self.function.arguments}}


class _ScriptedClient:
    """Stands in for the model: answers each turn with the next tool call from the plan."""

    def __init__(self, calls):
        self.calls = list(enumerate(calls))
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        number, (name, args) = self.calls.pop(0)
        message = types.SimpleNamespace(content="", tool_calls=[_ToolCall(number, name, args)])
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=None)


def _plan(**changes):
    plan = json.loads((FIXTURES / "sales_run.json").read_text())
    return {**plan, **changes}


def _make_run(run_dir, input_path=JAN, rules_path=RULES_FILE, plan=None):
    plan = plan or _plan()
    result = run_agent(input_path, plan["request"], ScriptedApprover(plan["approvals"]), rules_path=rules_path,
                       client=_ScriptedClient(plan["calls"]), coverage=False)
    assert result.stop_reason == "finish" and result.tool_errors == 0
    return write_outputs(result, run_dir)


@pytest.fixture
def sales_run(tmp_path):
    return _make_run(tmp_path / "run")


def _edit(path, old, new):
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def _edit_trace(run_dir, change):
    path = run_dir / "trace.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    change(events)
    path.write_text("".join(json.dumps(e) + "\n" for e in events))


def test_build_recipe_keeps_applied_fixes_in_version_order(tmp_path, sales_run):
    recipe = recipes.build_recipe(sales_run, JAN, RULES_FILE)

    assert [(s.fix, s.risk, s.approved_by, s.portable) for s in recipe.steps] == [
        ("trim_whitespace", "low", "auto", True),
        ("normalize_labels", "low", "auto", True),
        ("normalize_labels", "high", "approved", True),
        ("parse_dates", "low", "auto", True),
        ("parse_dates", "medium", "approved", True),
        ("cast_numeric", "low", "auto", True),
        ("drop_duplicates", "medium", "approved", False),
        ("fill_missing", "high", "approved", False),
    ]  # the rejected exclude_rows is not a step
    assert recipe.steps[0].args == {"column": "Region"}  # no "reason", and the ignored "note" is dropped
    assert recipe.steps[3].args == {"column": "Date"}
    assert recipe.steps[4].args == {"column": "Date", "date_order": "dmy"}  # kept as recorded
    assert recipe.source == recipes.Source(name="sales_jan.csv", sha256=recipes.file_sha256(JAN), rows=7)
    assert recipe.schema.columns == ["Order_ID", "Date", "Category", "Region", "Quantity", "Price"]
    assert recipe.rules == recipes.RulesRef(name="sales_rules.json", sha256=recipes.file_sha256(RULES_FILE))
    assert recipes.load_recipe(recipes.save_recipe(recipe, tmp_path / "recipe.json")) == recipe


def test_changes_table_ends_before_the_date_change_lists(sales_run):
    report = (sales_run / "report.md").read_text()
    assert "### Date changes in v4" in report and "### Date changes in v5" in report

    rows = recipes.parse_changes(report)
    assert [r["Version"] for r in rows] == ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "-"]
    assert rows[2]["Reason"] == "Misspelling | the allowed label is Accessories."  # "|" joined back
    assert rows[-1]["Fix"] == "exclude_rows" and rows[-1]["Approval"] == "rejected"


def test_escaped_pipes_are_read_back_in_changes_cells(sales_run):
    report = "\n".join([
        "## Changes", "",
        "| Version | Fix | Risk | Approval | What changed | Reason |",
        "|---|---|---|---|---|---|",
        r"| v1 | normalize_labels | low | auto | Category: a \| b merged | Merge \| case variants |",
        "| v2 | trim_whitespace | low | auto | Region: trimmed 1 values | Unescaped | stays in Reason |",
        r"| - | exclude_rows | high | rejected | excluded 1 row(s): [6] (not applied) | Ends with a pipe \| |",
    ])
    rows = recipes.parse_changes(report)
    assert rows[0]["What changed"] == "Category: a | b merged" and rows[0]["Reason"] == "Merge | case variants"
    assert rows[1]["Reason"] == "Unescaped | stays in Reason"
    assert rows[2]["Version"] == "-" and rows[2]["Reason"] == "Ends with a pipe |"

    # A run's report with escaped pipes still pairs with its trace.
    _edit(sales_run / "report.md", "Misspelling | the allowed label", r"Misspelling \| the allowed label")
    _edit(sales_run / "report.md", "Category: merged 1 label variant(s), 1 cells | Misspelling",
          r"Category: merged 1 label variant(s)\|1 cells | Misspelling")
    rows = recipes.parse_changes((sales_run / "report.md").read_text())
    assert rows[2]["What changed"] == "Category: merged 1 label variant(s)|1 cells"
    assert rows[2]["Reason"] == "Misspelling | the allowed label is Accessories."
    assert len(recipes.build_recipe(sales_run, JAN, RULES_FILE).steps) == 8


def test_unpaired_records_are_an_error(tmp_path, sales_run):
    other = shutil.copytree(sales_run, tmp_path / "copy")
    report = sales_run / "report.md"
    row = next(line for line in report.read_text().splitlines() if line.startswith("| v6 |"))
    _edit(report, row + "\n", "")
    with pytest.raises(recipes.RecipeError, match="not in the Changes table: v6"):
        recipes.build_recipe(sales_run, JAN, RULES_FILE)

    _edit_trace(other, lambda events: events.remove(next(e for e in events if e.get("name") == "cast_numeric")))
    with pytest.raises(recipes.RecipeError, match="not applied in trace.jsonl: v6"):
        recipes.build_recipe(other, JAN, RULES_FILE)


def test_disagreeing_records_are_an_error(sales_run):
    _edit(sales_run / "report.md", "| v2 | normalize_labels | low | auto |", "| v2 | normalize_labels | high | approved |")
    with pytest.raises(recipes.RecipeError, match="v2: trace.jsonl has fix, risk, approval"):
        recipes.build_recipe(sales_run, JAN, RULES_FILE)


def test_two_applied_records_with_one_version_are_an_error(sales_run):
    def same_version(events):
        next(e for e in events if e.get("output", {}).get("version") == 3 and e["name"] == "normalize_labels")["output"]["version"] = 2
    _edit_trace(sales_run, same_version)
    with pytest.raises(recipes.RecipeError, match="two applied fixes in trace.jsonl have version v2"):
        recipes.build_recipe(sales_run, JAN, RULES_FILE)


def test_input_must_be_the_runs_input(tmp_path, sales_run):
    renamed = tmp_path / "sales_january.csv"
    shutil.copy(JAN, renamed)
    with pytest.raises(recipes.RecipeError, match="'sales_january.csv' is not the run's input 'sales_jan.csv'"):
        recipes.build_recipe(sales_run, renamed, RULES_FILE)

    report = sales_run / "report.md"
    line = next(line for line in report.read_text().splitlines() if line.startswith("- Input:"))
    _edit(report, line + "\n", "")
    with pytest.warns(recipes.RecipeWarning, match="no Input line"):
        recipe = recipes.build_recipe(sales_run, renamed, RULES_FILE)
    assert recipe.source.name == "sales_january.csv"


def test_stacked_input_file_is_accepted(sales_run):
    stacked = shutil.copy(JAN, sales_run / "input_stacked.csv")
    line = next(line for line in (sales_run / "report.md").read_text().splitlines() if line.startswith("- Input:"))
    _edit(sales_run / "report.md", line, f"- Input: `{stacked}`")

    assert recipes.build_recipe(sales_run, stacked, RULES_FILE).source.name == "input_stacked.csv"
    with pytest.raises(recipes.RecipeError, match="pass the input_stacked.csv in its run folder"):
        recipes.build_recipe(sales_run, JAN, RULES_FILE)


def test_rules_must_match_what_the_run_looked_up(tmp_path, sales_run):
    other = tmp_path / "other_rules.json"
    other.write_text('{"Category": {"allowed": ["Electronics"]}}')
    empty = tmp_path / "empty.json"
    empty.write_text("{}")

    with pytest.raises(recipes.RecipeError, match="differs from the rules the run used"):
        recipes.build_recipe(sales_run, JAN, other)
    with pytest.raises(recipes.RecipeError, match="differs from the rules the run used"):
        recipes.build_recipe(sales_run, JAN, empty)
    with pytest.raises(recipes.RecipeError, match="pass the same file as rules_path"):
        recipes.build_recipe(sales_run, JAN)
    with pytest.raises(recipes.RecipeError, match="pass the same file as rules_path"):
        recipes.build_recipe(sales_run, JAN, no_rules=True)
    with pytest.raises(recipes.RecipeError, match="not both"):
        recipes.build_recipe(sales_run, JAN, RULES_FILE, no_rules=True)


def test_run_without_rules(tmp_path):
    run = _make_run(tmp_path / "run", rules_path=None)
    trace = (run / "trace.jsonl").read_text()
    assert recipes.NO_RULES in trace

    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    assert recipes.build_recipe(run, JAN).rules is None
    assert recipes.build_recipe(run, JAN, empty).rules is None  # {} means no rules
    with pytest.raises(recipes.RecipeError, match="the run had no rules file"):
        recipes.build_recipe(run, JAN, RULES_FILE)


def test_run_without_a_lookup_rules_record(tmp_path):
    plan = _plan()
    run = _make_run(tmp_path / "run", rules_path=None, plan={**plan, "calls": plan["calls"][1:]})
    assert "lookup_rules" not in (run / "trace.jsonl").read_text()

    with pytest.raises(recipes.RecipeError, match="Pass rules_path with the run's rules file, or no_rules=True"):
        recipes.build_recipe(run, JAN)
    with pytest.raises(recipes.RecipeError, match="no lookup_rules record"):
        recipes.build_recipe(run, JAN, RULES_FILE)
    assert recipes.build_recipe(run, JAN, no_rules=True).rules is None


# R8: replaying a recipe on a new file

def _statuses(result):
    return [(s.step, s.fix, s.status) for s in result.steps]


def _single_step_recipe(path, fix, args, risk="low", approved_by="auto", portable=True):
    source, schema = recipes.describe_input(path)
    step = recipes.Step(fix=fix, args=args, risk=risk, approved_by=approved_by, portable=portable)
    return recipes.Recipe(source=source, schema=schema, steps=[step])


def test_recipe_from_one_month_replays_on_the_next(tmp_path, sales_run):
    recipe = recipes.build_recipe(sales_run, JAN, RULES_FILE)
    before = FEB.read_bytes()

    result = recipes.apply_recipe(recipe, FEB, tmp_path / "out")

    assert FEB.read_bytes() == before and result.input_sha256 == hashlib.sha256(before).hexdigest()
    assert _statuses(result) == [
        (1, "trim_whitespace", "applied"),
        (2, "normalize_labels", "applied"),
        (3, "normalize_labels", "needs review"),  # a misspelling merge is high risk on any file
        (4, "parse_dates", "applied"),            # 05/02/2026 is ambiguous, so it is left unchanged
        (5, "parse_dates", "needs review"),       # date_order dmy would change it: medium risk
        (6, "cast_numeric", "applied"),
        (7, "drop_duplicates", "needs review"),   # removes rows
        (8, "fill_missing", "needs review"),      # values approved only for January
    ]
    cleaned = pd.read_csv(result.cleaned_path, index_col="row", keep_default_na=False)
    assert cleaned["Region"].tolist() == ["West", "East", "North", "South", "South"]
    assert cleaned["Category"].tolist() == ["Electronics", "Accessories", "Acessories", "ELECTRONICS", "ELECTRONICS"]
    assert cleaned["Date"].tolist() == ["2026-02-01", "05/02/2026", "2026-02-06", "2026-02-07", "2026-02-07"]
    assert cleaned["Price"].tolist() == [12.0, 6.0, 3.5, 8.0, 8.0]
    assert (result.rows_in, result.rows_out) == (5, 5)

    left = {(i["check"], i["column"]): i["count"] for i in result.new_issues}
    assert left == {("label_variant", "Category"): 1, ("invalid_date", "Date"): 1,
                    ("missing", "Quantity"): 2, ("duplicates", "*"): 1}

    report = result.report_path.read_text()
    assert report.startswith("# Recipe replay")
    assert "The input file is only read; it is not changed." in report
    assert "- Step 5, parse_dates: risk is medium on this file" in report
    assert "| invalid_date | Date | 1 | [1] |" in report


def test_ambiguous_date_sends_parse_dates_with_a_date_order_to_review(tmp_path):
    jan = tmp_path / "jan.csv"
    jan.write_text("Date,Amount\n2026-01-02T00:00:00.000,1\n13/01/2026,2\n")
    recipe = _single_step_recipe(jan, "parse_dates", {"column": "Date", "date_order": "dmy"}, "medium", "approved")

    ambiguous = tmp_path / "feb.csv"
    ambiguous.write_text("Date,Amount\n2026-02-01T00:00:00.000,1\n03/04/2026,2\n")
    result = recipes.apply_recipe(recipe, ambiguous, tmp_path / "out1")
    assert [(s.status, s.risk) for s in result.steps] == [("needs review", "medium")]
    assert pd.read_csv(result.cleaned_path)["Date"].tolist() == ["2026-02-01T00:00:00.000", "03/04/2026"]

    clear = tmp_path / "mar.csv"
    clear.write_text("Date,Amount\n2026-03-01T00:00:00.000,1\n25/03/2026,2\n")
    result = recipes.apply_recipe(recipe, clear, tmp_path / "out2")
    assert [(s.status, s.risk) for s in result.steps] == [("applied", "low")]
    assert pd.read_csv(result.cleaned_path)["Date"].tolist() == ["2026-03-01", "2026-03-25"]


def test_normalize_labels_uses_only_labels_present(tmp_path):
    jan = tmp_path / "jan.csv"
    jan.write_text("Category\nelectronics\naccessories\nElectronics\nAccessories\n")
    recipe = _single_step_recipe(jan, "normalize_labels", {
        "column": "Category", "mapping": {"electronics": "Electronics", "accessories": "Accessories"}})

    feb = tmp_path / "feb.csv"
    feb.write_text("Category\nelectronics\nAccessories\n")
    result = recipes.apply_recipe(recipe, feb, tmp_path / "out1")
    assert result.steps[0].status == "applied"
    assert result.steps[0].args == {"column": "Category", "mapping": {"electronics": "Electronics"}}

    mar = tmp_path / "mar.csv"
    mar.write_text("Category\nElectronics\nAccessories\n")
    assert recipes.apply_recipe(recipe, mar, tmp_path / "out2").steps[0].status == "not needed"


def test_risk_is_recomputed_on_the_new_file(tmp_path):
    jan = tmp_path / "jan.csv"
    jan.write_text("Price\n$1.00\n$2.50\n")
    recipe = _single_step_recipe(jan, "cast_numeric", {"column": "Price"})

    feb = tmp_path / "feb.csv"
    feb.write_text("Price\n$3.00\nfive\n")  # "five" would become missing: medium risk
    result = recipes.apply_recipe(recipe, feb, tmp_path / "out")
    assert [(s.status, s.recipe_risk, s.risk) for s in result.steps] == [("needs review", "low", "medium")]
    assert result.new_issues[0]["check"] == "numeric"


def test_row_level_fixes_and_fill_missing_are_never_replayed(tmp_path):
    jan = tmp_path / "jan.csv"
    jan.write_text("Name,Qty,Total\na,1,1\na,1,1\nb,-2,4\nc,,3\n")
    source, schema = recipes.describe_input(jan)
    steps = [
        recipes.Step(fix="drop_duplicates", args={}, risk="medium", approved_by="approved", portable=False),
        recipes.Step(fix="exclude_rows", args={"rows": [2]}, risk="high", approved_by="approved", portable=True),
        recipes.Step(fix="exclude_where", args={"column": "Qty", "minimum": 0}, risk="high", approved_by="approved",
                     portable=False),
        recipes.Step(fix="set_missing", args={"column": "Total", "rows": [2]}, risk="high", approved_by="approved",
                     portable=False),
        recipes.Step(fix="recompute_column", args={"column": "Total", "expression": "Qty", "rows": [0]}, risk="high",
                     approved_by="approved", portable=False),
        recipes.Step(fix="fill_missing", args={"column": "Qty", "value": 1}, risk="high", approved_by="approved",
                     portable=False),
    ]
    recipe = recipes.Recipe(source=source, schema=schema, steps=steps)

    result = recipes.apply_recipe(recipe, jan, tmp_path / "out")
    assert [s.status for s in result.steps] == ["needs review"] * 6  # even exclude_rows marked portable by hand
    assert all(s.risk is None for s in result.steps)
    assert result.rows_out == 4
    assert pd.read_csv(result.cleaned_path, index_col="row").equals(pd.read_csv(jan))


def test_missing_column_refuses_and_writes_nothing(tmp_path, month1):
    recipe = _recipe(month1)
    feb = tmp_path / "month2.csv"
    feb.write_text("Order_ID,Date,Quantity,Price\n4,2026-09-01,1,$1.00\n")
    with pytest.raises(recipes.RecipeError, match="lacks the recipe's column\\(s\\) Category"):
        recipes.apply_recipe(recipe, feb, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_apply_reads_a_saved_recipe_and_never_overwrites_the_input(tmp_path, month1):
    path = recipes.save_recipe(_recipe(month1), tmp_path / "recipe.json")
    result = recipes.apply_recipe(path, month1, tmp_path / "out")
    assert [s.status for s in result.steps] == ["applied", "needs review"]

    inside = tmp_path / "out" / "cleaned.csv"
    with pytest.raises(recipes.RecipeError, match="would overwrite the input file"):
        recipes.apply_recipe(path, inside, tmp_path / "out")


# End to end: the handoff's "done when" for R1, on files already in the repository (read only)

ROOT = Path(__file__).resolve().parents[1]
DEMO_RUN = ROOT / "docs" / "final" / "demo"            # a recorded DataSage run on messy_sales.csv
DEMO_INPUT = ROOT / "baseline" / "examples" / "messy_sales.csv"
DEMO_RULES = ROOT / "examples" / "messy_sales_rules.json"
NEXT_TABLE = ROOT / "examples" / "demo" / "monthly" / "orders_2026-09.csv"  # same columns, another month


def _hashes(paths):
    return {p: recipes.file_sha256(p) for p in paths}


def test_recipe_from_the_demo_run_replays_on_another_table_with_the_same_columns(tmp_path):
    read_only = [*sorted(p for p in DEMO_RUN.iterdir() if p.is_file()), DEMO_INPUT, DEMO_RULES, NEXT_TABLE]
    before = _hashes(read_only)

    recipe = recipes.build_recipe(DEMO_RUN, DEMO_INPUT, DEMO_RULES)
    assert [(s.fix, s.risk, s.approved_by, s.portable) for s in recipe.steps] == [
        ("drop_duplicates", "medium", "approved", False),
        ("normalize_labels", "low", "auto", True),
    ]  # the run's rejected exclude_rows and set_missing are not steps
    assert recipe.rules.name == "messy_sales_rules.json"
    saved = recipes.save_recipe(recipe, tmp_path / "recipe.json")

    result = recipes.apply_recipe(saved, NEXT_TABLE, tmp_path / "replay")

    assert result.schema == ([], [], {})  # the same columns and kinds as messy_sales.csv
    assert _statuses(result) == [(1, "drop_duplicates", "needs review"), (2, "normalize_labels", "applied")]
    assert result.steps[1].args["mapping"] == {"accessories": "Accessories"}  # "electronics" is not in this file
    cleaned = pd.read_csv(result.cleaned_path, index_col="row")
    assert "accessories" not in set(cleaned["Category"]) and len(cleaned) == result.rows_in
    assert {i["check"] for i in result.new_issues} == {"label_variant", "duplicates"}  # left for review
    assert _hashes(read_only) == before  # nothing in the repository was changed


# R9: command line

def test_cli_save_then_apply(tmp_path, sales_run, capsys):
    recipe = tmp_path / "recipe.json"
    assert recipes.main(["save", "--run", str(sales_run), "--input", str(JAN), "--rules", str(RULES_FILE),
                         "--out", str(recipe)]) == 0
    assert "8 step(s) from sales_jan.csv (rules file sales_rules.json); 6 can be replayed" in capsys.readouterr().out
    assert recipes.load_recipe(recipe).steps[0].fix == "trim_whitespace"

    out_dir = tmp_path / "out"
    assert recipes.main(["apply", "--recipe", str(recipe), "--input", str(FEB), "--out", str(out_dir)]) == 0
    printed = capsys.readouterr().out
    assert "Replayed recipe.json on sales_feb.csv: 4 applied, 4 needs review, 0 not needed." in printed
    assert "sales_feb.csv was not changed." in printed
    assert (out_dir / "cleaned.csv").is_file() and (out_dir / "recipe_run.md").is_file()


def test_cli_prints_errors_and_warnings(tmp_path, sales_run, capsys):
    recipe = tmp_path / "recipe.json"
    assert recipes.main(["save", "--run", str(sales_run), "--input", str(JAN), "--out", str(recipe)]) == 2
    assert "error: the run used a rules file" in capsys.readouterr().err
    assert not recipe.exists()

    with pytest.raises(SystemExit):  # --rules and --no-rules exclude each other
        recipes.main(["save", "--run", str(sales_run), "--input", str(JAN), "--rules", str(RULES_FILE), "--no-rules",
                      "--out", str(recipe)])
    capsys.readouterr()

    line = next(line for line in (sales_run / "report.md").read_text().splitlines() if line.startswith("- Input:"))
    _edit(sales_run / "report.md", line + "\n", "")
    assert recipes.main(["save", "--run", str(sales_run), "--input", str(JAN), "--rules", str(RULES_FILE),
                         "--out", str(recipe)]) == 0
    assert "warning: report.md has no Input line" in capsys.readouterr().err

    narrow = tmp_path / "narrow.csv"
    narrow.write_text("Order_ID,Date\n1,2026-03-01\n")
    assert recipes.main(["apply", "--recipe", str(recipe), "--input", str(narrow), "--out", str(tmp_path / "out")]) == 2
    assert "lacks the recipe's column(s) Category, Region, Quantity, Price" in capsys.readouterr().err


def test_cli_runs_as_a_module():
    done = subprocess.run([sys.executable, "-m", "datasage.recipes", "--help"], capture_output=True, text=True, cwd=ROOT)
    assert done.returncode == 0 and "{save,apply}" in done.stdout
