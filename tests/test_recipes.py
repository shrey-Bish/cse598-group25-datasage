"""Tests for cleaning recipes (datasage/recipes.py). Synthetic data only; no API key or network.

Run folders are made by the real agent loop (run_agent and write_outputs) with a scripted client in place
of the model, so the parser is always tested against what report.py and the trace write today.
"""

import hashlib
import json
import shutil
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
